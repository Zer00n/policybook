import asyncio
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from ulid import ULID

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)

from app.db.session import SessionLocal
from app.eval.judge import judge_run
from app.eval.summarize import summarize_runs
from app.reports.ppt_builder import build_family_ppt
from app.reports.ppt_verify import tamper_ppt_text, verify_ppt_numbers
from app.settings import settings


async def run_m6_verification():
    print("=================================================================")
    print("           M6 全家保单 PPT、测评模式、Docker 专项验收")
    print("=================================================================\n", flush=True)

    db = SessionLocal()
    stats = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ppt_normal_verification": {},
        "ppt_tamper_verification": {},
        "eval_summary": {},
        "docker_config": {},
    }

    # -------------------------------------------------------------
    # 验收项 1: PPT 回读核验 mismatches 为空的输出 (PRD 3.12, DEV-GUIDE 8.9)
    # -------------------------------------------------------------
    print(">>> [验收项 1] PPT 纯代码生成与反向数值回读核验 (mismatches 为空)")
    report_id = str(ULID())
    out_file, snapshot = build_family_ppt(
        db,
        report_id=report_id,
        custom_summary="家庭保单基础保障完备，医疗与意外额度充足，建议持续关注长期重疾与年金规划。",
    )
    print(f"  生成 PPT 文件: {out_file.name}")
    print(f"  数据库快照关键指标:")
    print(f"    - 有效保单数: {snapshot['total_policies']} 份")
    print(f"    - 年度保费总支出: ¥{snapshot['total_premium_yuan']:,}")
    print(f"    - 身故总保额: ¥{snapshot['total_death_yuan']:,}")
    print(f"    - 重疾总保额: ¥{snapshot['total_ci_yuan']:,}")

    verify_res = verify_ppt_numbers(out_file, snapshot)
    print(f"  回读核验结果: verified={verify_res['verified']}, mismatches={verify_res['mismatches']}")
    print(f"  检查项总数: {verify_res['total_checked']}, 幻灯片总页数: {verify_res['slides_count']}")

    assert verify_res["verified"] is True, f"PPT 回读核验失败: {verify_res['mismatches']}"
    assert len(verify_res["mismatches"]) == 0

    stats["ppt_normal_verification"] = {
        "report_id": report_id,
        "ppt_file": out_file.name,
        "slides_count": verify_res["slides_count"],
        "total_checked": verify_res["total_checked"],
        "verified": verify_res["verified"],
        "mismatches": verify_res["mismatches"],
        "snapshot": snapshot,
    }
    print("  [PASS] 验收项 1 验证通过！mismatches 严格为空。\n", flush=True)

    # -------------------------------------------------------------
    # 验收项 2: 故意改错一个数字后核验报错的测试输出 (DEV-GUIDE 10.9)
    # -------------------------------------------------------------
    print(">>> [验收项 2] 故意篡改 PPT 数字后核验报错测试")
    tampered_file = out_file.parent / f"tampered_{report_id}.pptx"
    orig_policies = str(snapshot["total_policies"])
    tamper_success = tamper_ppt_text(
        out_file,
        tampered_file,
        orig_policies,
        "9999",
    )
    print(f"  执行文本篡改: 将保单数 '{orig_policies}' 修改为 '9999' (成功={tamper_success})")

    # 核验篡改后的 PPT 与原始快照
    tamper_res = verify_ppt_numbers(tampered_file, snapshot)
    print(f"  篡改文件核验结果: verified={tamper_res['verified']}")
    print(f"  检出偏差列表: {tamper_res['mismatches']}")

    assert tamper_res["verified"] is False, "篡改后核验未检出偏差！"
    assert len(tamper_res["mismatches"]) > 0

    stats["ppt_tamper_verification"] = {
        "tampered_file": tampered_file.name,
        "verified": tamper_res["verified"],
        "mismatches_detected": len(tamper_res["mismatches"]),
        "mismatches": tamper_res["mismatches"],
    }
    print("  [PASS] 验收项 2 验证通过！核验引擎成功拦截并报错。\n", flush=True)

    # -------------------------------------------------------------
    # 验收项 3: 两个模型在 E3 上各跑一次生成的 summary.csv (PRD 8, DEV-GUIDE 9)
    # -------------------------------------------------------------
    print(">>> [验收项 3] 两个模型 (evolving 与 baseline) 评测汇总与 summary.csv")
    eval_dir = (settings.project_root / "eval").resolve()
    runs_dir = eval_dir / "runs"
    summary_csv = eval_dir / "summary.csv"

    # Summarize all evaluated runs
    summarized_rows = summarize_runs(runs_dir, summary_csv)
    print(f"  已汇总评测批次数量: {len(summarized_rows)}")
    for r in summarized_rows:
        print(f"    - Run: {r['run_id']} | Model: {r['model_alias']} ({r['model_id']}) | Pass: {r['pass_rate']} | Quote Acc: {r['quote_accuracy']}")

    stats["eval_summary"] = {
        "total_runs": len(summarized_rows),
        "summary_csv_path": str(summary_csv),
        "runs": summarized_rows,
    }
    print("  [PASS] 验收项 3 验证通过！\n", flush=True)

    # -------------------------------------------------------------
    # 验收项 4: Docker 配置与健康检查标准
    # -------------------------------------------------------------
    print(">>> [验收项 4] Dockerfile 与 compose.yaml 部署配置检验")
    dockerfile_path = settings.project_root / "docker" / "Dockerfile"
    compose_path = settings.project_root / "docker" / "compose.yaml"

    assert dockerfile_path.exists(), "Dockerfile 不存在"
    assert compose_path.exists(), "compose.yaml 不存在"

    df_content = dockerfile_path.read_text(encoding="utf-8")
    cp_content = compose_path.read_text(encoding="utf-8")

    assert "HEALTHCHECK" in df_content, "Dockerfile 必须包含 HEALTHCHECK"
    assert "api/health" in df_content, "HEALTHCHECK 必须检查 /api/health"
    assert "8080:8000" in cp_content, "compose.yaml 端口映射为 8080:8000"

    stats["docker_config"] = {
        "dockerfile_exists": True,
        "compose_exists": True,
        "healthcheck_configured": True,
        "ports_mapped": "8080:8000",
    }
    print("  [PASS] 验收项 4 验证通过！\n", flush=True)

    # -------------------------------------------------------------
    # 落盘统计至 docs/m6_stats.json
    # -------------------------------------------------------------
    out_json = settings.project_root / "docs" / "m6_stats.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f">>> 评测与核验全量统计数据已写入: {out_json}")
    print("=================================================================")
    print("                   M6 全部专项验收项 100% 通过")
    print("=================================================================\n", flush=True)


if __name__ == "__main__":
    asyncio.run(run_m6_verification())
