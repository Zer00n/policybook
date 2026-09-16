import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from sqlalchemy.orm import Session
from ulid import ULID

from app.db.session import SessionLocal
from app.db.models import Coverage, Document, Policy, ChatSession, SourceRecord
from app.renewal.comparator import verify_url_provenance
from app.renewal.fetcher import fetch_candidate_document
from app.renewal.search import (
    FaultInjectionSearchProvider,
    MockSearchProvider,
    execute_search_and_record,
)
from app.renewal.security import (
    DomainNotAllowedError,
    InvalidURLError,
    SSRFSecurityError,
    validate_fetch_url,
)
from app.renewal.state_machine import RenewalStateMachine
from app.settings import settings


async def run_m5_verification():
    print("=================================================================")
    print("               M5 续保顾问 Agent 专项验收验证脚本")
    print("=================================================================\n")

    db = SessionLocal()
    stats = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "security_tests": {},
        "search_timeout_disclosure": {},
        "full_session_flow": {},
        "url_provenance_check": {},
    }

    # -------------------------------------------------------------
    # 验收项 1: fetch_document 拒绝内网地址与非白名单域名的测试输出
    # -------------------------------------------------------------
    print(">>> [验收项 1] fetch_document 拒绝内网地址与非白名单域名验证")
    allowed_domains = ["pingan.com", "cpic.com.cn", "cbirc.gov.cn"]
    test_urls = [
        ("http://127.0.0.1:8080/internal.pdf", "拦截回环地址 127.0.0.1 (SSRF)"),
        ("http://192.168.1.100/admin.pdf", "拦截私有局域网地址 192.168.1.100 (SSRF)"),
        ("http://169.254.169.254/latest/meta-data/", "拦截云主机元数据地址 (SSRF)"),
        ("https://malicious-scam.com/fake_policy.pdf", "拦截非白名单外部域名"),
        ("ftp://pingan.com/doc.pdf", "拦截非 http/https 协议"),
    ]

    security_results = []
    for url, label in test_urls:
        try:
            validate_fetch_url(url, allowed_domains)
            print(f"  [FAIL] 未拦截: {url}")
            security_results.append({"url": url, "passed": False, "error": None})
        except (SSRFSecurityError, DomainNotAllowedError, InvalidURLError) as e:
            print(f"  [PASS] 成功拦截: {url} -> 异常类型: {type(e).__name__} ({e})")
            security_results.append({
                "url": url,
                "label": label,
                "passed": True,
                "exception": type(e).__name__,
                "detail": str(e),
            })

    stats["security_tests"] = {
        "total_probes": len(test_urls),
        "all_blocked": all(r["passed"] for r in security_results),
        "results": security_results,
    }

    # -------------------------------------------------------------
    # 验收项 2: 模拟 search_web 超时后报告中披露失败的接口响应
    # -------------------------------------------------------------
    print("\n>>> [验收项 2] 模拟 search_web 超时后报告中披露失败的接口响应")
    # Find or create a base accident policy
    base_policy = db.query(Policy).filter(Policy.category == "accident").first()
    if not base_policy:
        base_policy = Policy(
            id=str(ULID()),
            product_name="平安安心综合意外险（测试）",
            insurer="中国平安财产保险股份有限公司",
            category="accident",
            premium_cents=29900,
        )
        db.add(base_policy)
        db.commit()

    timeout_session = ChatSession(
        id=str(ULID()),
        kind="renewal",
        policy_id=base_policy.id,
        state="START",
    )
    db.add(timeout_session)
    db.commit()

    fault_provider = FaultInjectionSearchProvider(
        base_provider=MockSearchProvider(),
        fault_type="timeout",
        on_call=1,
    )

    sm_timeout = RenewalStateMachine(timeout_session, db, search_provider=fault_provider)
    await sm_timeout.initialize()
    timeout_result = await sm_timeout.process_user_turn(user_text="直接对比", skip=True)

    report_timeout = timeout_result.get("report")
    print(f"  状态机最终状态: {timeout_result.get('state')}")
    print(f"  报告状态: {report_timeout.status if report_timeout else None}")
    print(f"  未完成原因: {report_timeout.search_failure_reason if report_timeout else None}")
    print(f"  报告叙述披露片段: {report_timeout.difference_narrative[:120] if report_timeout else ''}...")

    stats["search_timeout_disclosure"] = {
        "session_id": timeout_session.id,
        "final_state": timeout_result.get("state"),
        "report_status": report_timeout.status if report_timeout else None,
        "search_failure_reason": report_timeout.search_failure_reason if report_timeout else None,
        "narrative_disclosure": report_timeout.difference_narrative if report_timeout else None,
    }

    # -------------------------------------------------------------
    # 验收项 3 & 4: 一次完整会话从追问到报告 & 每个 URL 在 source_record 查到的核对
    # -------------------------------------------------------------
    print("\n>>> [验收项 3 & 4] 一次完整会话流转与 URL 溯源核验脚本")
    full_session = ChatSession(
        id=str(ULID()),
        kind="renewal",
        policy_id=base_policy.id,
        state="START",
    )
    db.add(full_session)
    db.commit()

    sm_full = RenewalStateMachine(full_session, db, search_provider=MockSearchProvider())
    
    # Step 1: Init (START -> LOAD_BASELINE -> COLLECT_NEEDS)
    welcome = await sm_full.initialize()
    print(f"  1. 初始化欢迎语: {welcome[:60]}...")

    # Step 2: User states changes (COLLECT_NEEDS -> GAP_CHECK -> ASK_USER)
    turn1 = await sm_full.process_user_turn(user_text="今年坐高铁飞机出差多，希望有猝死责任")
    print(f"  2. 澄清后流转至: {turn1.get('state')}，提出追问: {[q.label for q in turn1.get('questions', [])]}")

    # Step 3: User answers and finishes (ASK_USER -> GAP_CHECK -> SEARCH -> FETCH_DOCS -> EXTRACT_CANDIDATES -> COMPARE -> REPORT -> END)
    first_q = turn1.get("questions", [])[0] if turn1.get("questions") else None
    answers = {first_q.dimension: first_q.options[0]} if first_q and first_q.options else {}
    turn2 = await sm_full.process_user_turn(user_text="已选择", answers=answers, skip=True)
    print(f"  3. 答复后流转至: {turn2.get('state')}，报告生成状态: {turn2.get('report').status if turn2.get('report') else None}")

    report_full = turn2.get("report")
    matrix = report_full.comparison_matrix if report_full else None

    # Check comparison matrix products and rows
    products_count = len(matrix.products) if matrix else 0
    rows_count = len(matrix.rows) if matrix else 0
    print(f"  对比矩阵: 产品数={products_count}, 维度行数={rows_count}")

    # Check URL Provenance against source_record
    print("\n  [URL 溯源深度核验]")
    source_records = db.query(SourceRecord).filter(SourceRecord.session_id == full_session.id).all()
    recorded_urls_set = {r.url.strip() for r in source_records}
    print(f"  本会话在 source_record 中有效登记的白名单来源条数: {len(source_records)}")
    for r in source_records:
        print(f"    - [{r.via.upper()}] 域名: {r.domain} | URL: {r.url}")

    urls_in_narrative = re.findall(r"https?://[^\s()\[\]{}<>'\"`“”‘’（）【】《》]+", report_full.difference_narrative if report_full else "")
    clean_narrative_urls = [u.rstrip(".,;:!?，。；：！？）)]}>\"'") for u in urls_in_narrative]

    url_check_results = []
    all_urls_verified = True
    for u in clean_narrative_urls:
        in_record = u in recorded_urls_set
        print(f"    溯源核对: {u} -> {'[已登记通过]' if in_record else '[未登记拦截]'}")
        url_check_results.append({"url": u, "in_source_record": in_record})
        if not in_record:
            all_urls_verified = False

    stats["full_session_flow"] = {
        "session_id": full_session.id,
        "final_state": turn2.get("state"),
        "matrix_products": products_count,
        "matrix_rows": rows_count,
        "customer_service_questions_count": len(report_full.customer_service_questions) if report_full else 0,
        "missing_info_count": len(report_full.missing_info) if report_full else 0,
    }

    stats["url_provenance_check"] = {
        "recorded_sources_count": len(source_records),
        "urls_in_narrative_count": len(clean_narrative_urls),
        "all_urls_verified": all_urls_verified,
        "details": url_check_results,
    }

    # Save to docs/m5_stats.json (Red Line 13)
    out_path = settings.project_root / "docs" / "m5_stats.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"\n>>> 统计数据已写入: {out_path}")
    print("=================================================================")
    print("                      M5 专项验收全部完成")
    print("=================================================================")
    db.close()


if __name__ == "__main__":
    asyncio.run(run_m5_verification())
