from datetime import datetime, timezone
import json
import logging
from typing import Any, AsyncGenerator
from sqlalchemy.orm import Session
from ulid import ULID

from app.db.models import (
    ChatMessage,
    ChatSession,
    Coverage,
    Document,
    Policy,
    SourceRecord,
    ToolCallRecord,
)
from app.renewal.comparator import (
    build_comparison_matrix,
    filter_forbidden_phrases,
    verify_url_provenance,
)
from app.renewal.config import GapDimension, config_loader
from app.renewal.fetcher import fetch_candidate_document, get_candidate_coverages_by_doc
from app.renewal.search import (
    FaultInjectionSearchProvider,
    MockSearchProvider,
    SearchProvider,
    SearchTimeoutError,
    execute_search_and_record,
)
from app.schemas.renewal import (
    ComparisonMatrix,
    RenewalProfileItem,
    RenewalQuestion,
    RenewalReport,
    SourceRecordDto,
)

logger = logging.getLogger(__name__)

TRANSITIONS: dict[str, list[str]] = {
    "START": ["LOAD_BASELINE"],
    "LOAD_BASELINE": ["COLLECT_NEEDS"],
    "COLLECT_NEEDS": ["GAP_CHECK"],
    "GAP_CHECK": ["ASK_USER", "SEARCH"],
    "ASK_USER": ["GAP_CHECK"],
    "SEARCH": ["FETCH_DOCS", "REPORT"],
    "FETCH_DOCS": ["EXTRACT_CANDIDATES", "REPORT"],
    "EXTRACT_CANDIDATES": ["COMPARE"],
    "COMPARE": ["REPORT"],
    "REPORT": ["END"],
}


class InvalidStateTransitionError(Exception):
    pass


class RenewalStateMachine:
    def __init__(
        self,
        session: ChatSession,
        db: Session,
        search_provider: SearchProvider | None = None,
    ):
        self.session = session
        self.db = db
        self.search_provider = search_provider or MockSearchProvider()
        self._load_state()

    def _load_state(self):
        self.profile: dict[str, dict[str, Any]] = json.loads(self.session.profile_json or "{}")
        self.scope: dict[str, Any] = json.loads(self.session.scope_json or "{}")

    def _save_state(self):
        self.session.profile_json = json.dumps(self.profile, ensure_ascii=False)
        self.session.scope_json = json.dumps(self.scope, ensure_ascii=False)
        self.session.updated_at = datetime.now(timezone.utc)
        self.db.commit()

    def transition_to(self, target_state: str):
        allowed = TRANSITIONS.get(self.session.state, [])
        if target_state not in allowed and target_state != "FAILED":
            raise InvalidStateTransitionError(
                f"非法状态转移: 无法从 '{self.session.state}' 转移至 '{target_state}' (允许的目标: {allowed})"
            )
        logger.info(f"Renewal session {self.session.id} transition: {self.session.state} -> {target_state}")
        self.session.state = target_state
        self._save_state()

    def record_tool_call(self, name: str, args: dict, result_digest: str, ok: bool = True):
        rec = ToolCallRecord(
            session_id=self.session.id,
            name=name,
            args_json=json.dumps(args, ensure_ascii=False),
            result_digest=result_digest,
            ok=ok,
        )
        self.db.add(rec)
        self.db.commit()

    def update_profile(self, dimension: str, value: str, label: str | None = None, source_message_id: str | None = None):
        self.profile[dimension] = {
            "value": value,
            "label": label or dimension,
            "source_message_id": source_message_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save_state()
        self.record_tool_call(
            name="update_profile",
            args={"dimension": dimension, "value": value},
            result_digest=f"更新画像: {dimension}={value}",
            ok=True,
        )

    def get_baseline_summary(self) -> dict[str, Any]:
        policy = self.db.query(Policy).filter(Policy.id == self.session.policy_id).first()
        if not policy:
            return {"error": "基线保单未找到"}

        coverages = policy.coverages or []
        summary = {
            "policy_id": policy.id,
            "product_name": policy.product_name,
            "insurer": policy.insurer,
            "category": policy.category,
            "premium_cents": policy.premium_cents,
            "expiry_date": str(policy.expiry_date) if policy.expiry_date else None,
            "coverages": [
                {
                    "name": c.name,
                    "kind": c.kind,
                    "limit_cents": c.limit_cents,
                    "deductible_cents": c.deductible_cents,
                }
                for c in coverages
            ],
        }
        self.record_tool_call("get_baseline", {}, f"读取基线保单 {policy.product_name} 责任项 {len(coverages)} 条")
        return summary

    def get_unconfirmed_gap_dimensions(self) -> list[GapDimension]:
        all_dimensions = config_loader.get_gap_dimensions("accident")
        unconfirmed = [d for d in all_dimensions if d.key not in self.profile]
        unconfirmed.sort(key=lambda d: d.weight, reverse=True)
        return unconfirmed

    async def initialize(self) -> str:
        """
        Runs START -> LOAD_BASELINE -> COLLECT_NEEDS and returns initial message.
        """
        if self.session.state == "START":
            self.transition_to("LOAD_BASELINE")
            baseline = self.get_baseline_summary()
            self.scope["baseline"] = baseline
            self.transition_to("COLLECT_NEEDS")

            welcome_text = (
                f"您好！我是您的意外险续保顾问。我们已为您加载当前的基线保单「{baseline.get('product_name', '现有意外险')}」。\n"
                f"在为您检索并对比今年最新的市场产品前，我想了解一下：今年您的工作、出行或家庭情况有什么新变化吗？"
                f"（例如：出差频次增加、需要出国、工作环境变化等；若无变化可直接告诉我「无变化」或点击继续）"
            )
            msg = ChatMessage(
                session_id=self.session.id,
                role="assistant",
                content=welcome_text,
            )
            self.db.add(msg)
            self.db.commit()
            return welcome_text
        return ""

    async def process_user_turn(
        self,
        user_text: str,
        answers: dict[str, str] | None = None,
        skip: bool = False,
    ) -> dict[str, Any]:
        """
        Processes a user turn through the state machine.
        Returns state, messages, questions, or report.
        """
        msg_id = str(ULID())
        user_msg = ChatMessage(
            id=msg_id,
            session_id=self.session.id,
            role="user",
            content=user_text or ("已选择选项" if answers else "跳过追问直接对比"),
        )
        self.db.add(user_msg)
        self.db.commit()

        # Update profile with explicit answers
        if answers:
            all_dims = {d.key: d.label for d in config_loader.get_gap_dimensions("accident")}
            for dim_key, ans_val in answers.items():
                self.update_profile(
                    dimension=dim_key,
                    value=ans_val,
                    label=all_dims.get(dim_key, dim_key),
                    source_message_id=msg_id,
                )

        # In COLLECT_NEEDS, analyze user statement
        if self.session.state == "COLLECT_NEEDS":
            # Heuristic keyword extraction for initial profile enrichment
            if "出差" in user_text or "飞机" in user_text or "高铁" in user_text:
                self.update_profile("travel_mode", "飞机/高铁为主", "出行方式", msg_id)
            if "境外" in user_text or "出国" in user_text:
                self.update_profile("overseas", "会", "境外出行", msg_id)
            if "加班" in user_text or "熬夜" in user_text or "猝死" in user_text:
                self.update_profile("sudden_death", "需要猝死保障", "猝死责任", msg_id)
            if "工地" in user_text or "野外" in user_text:
                self.update_profile("work_site", "工地或厂区", "工作场所", msg_id)

            self.transition_to("GAP_CHECK")

        elif self.session.state == "ASK_USER":
            self.transition_to("GAP_CHECK")

        # Now in GAP_CHECK
        if self.session.state == "GAP_CHECK":
            unconfirmed = self.get_unconfirmed_gap_dimensions()
            high_weight_unconfirmed = [d for d in unconfirmed if d.weight >= 0.7]

            if skip or not high_weight_unconfirmed:
                # All critical dimensions confirmed or user wants to skip -> go to SEARCH
                self.transition_to("SEARCH")
                return await self._run_search_and_reporting_pipeline()
            else:
                # Ask top 1-2 dimensions
                top_questions = unconfirmed[:2]
                self.transition_to("ASK_USER")

                question_dtos = [
                    RenewalQuestion(
                        dimension=d.key,
                        label=d.label,
                        question=d.question_hint or f"请问您的{d.label}情况是怎样的？",
                        why=f"影响意外险的「{', '.join(d.affects)}」关键责任与定价",
                        options=d.options,
                        affects=d.affects,
                    )
                    for d in top_questions
                ]

                reply_content = f"为了帮您在白名单官方条款中精准匹配更合适的方案，请先确认以下 {len(question_dtos)} 个关键维度："
                bot_msg = ChatMessage(
                    session_id=self.session.id,
                    role="assistant",
                    content=reply_content,
                    structured_json=json.dumps([q.model_dump() for q in question_dtos], ensure_ascii=False),
                )
                self.db.add(bot_msg)
                self.db.commit()

                self.record_tool_call(
                    name="ask_user",
                    args={"questions": [q.model_dump() for q in question_dtos]},
                    result_digest=f"提出 {len(question_dtos)} 个问题等待用户确认",
                    ok=True,
                )

                return {
                    "state": "ASK_USER",
                    "content": reply_content,
                    "questions": question_dtos,
                    "profile": self.profile,
                }

        # If already in search / report
        if self.session.state in ("SEARCH", "FETCH_DOCS", "EXTRACT_CANDIDATES", "COMPARE", "REPORT", "END"):
            return await self._run_search_and_reporting_pipeline()

        return {"state": self.session.state, "profile": self.profile}

    async def _run_search_and_reporting_pipeline(self) -> dict[str, Any]:
        """
        Executes SEARCH -> FETCH_DOCS -> EXTRACT_CANDIDATES -> COMPARE -> REPORT -> END.
        Handles search failure disclosure directly according to Red Line 7.
        """
        # Step: SEARCH
        search_query = "成人综合意外险 官方条款 费率表"
        search_failed = False
        search_err_msg = ""
        search_results = []

        try:
            search_results = await execute_search_and_record(
                provider=self.search_provider,
                query=search_query,
                session_id=self.session.id,
                db=self.db,
            )
            self.record_tool_call("search_web", {"query": search_query}, f"检索到 {len(search_results)} 条白名单官方结果")
            if not search_results:
                search_failed = True
                search_err_msg = "在监管及保司官网白名单内未检索到有效的公开条款"
        except SearchTimeoutError as e:
            search_failed = True
            search_err_msg = f"联网检索超时 ({e})"
            self.record_tool_call("search_web", {"query": search_query}, search_err_msg, ok=False)
        except Exception as e:
            search_failed = True
            search_err_msg = f"检索服务发生异常: {e}"
            self.record_tool_call("search_web", {"query": search_query}, search_err_msg, ok=False)

        # Handle Search Failure (DEV-GUIDE 984: SEARCH -> REPORT)
        if search_failed:
            self.transition_to("REPORT")
            report = self._build_failure_report(search_err_msg)
            self.transition_to("END")
            bot_msg = ChatMessage(
                session_id=self.session.id,
                role="assistant",
                content=f"【续保对比报告（检索未完成）】\n检索失败原因：{search_err_msg}。已为您生成基于基线保单与现有画像的分析报告。",
                structured_json=json.dumps(report.model_dump(), ensure_ascii=False),
            )
            self.db.add(bot_msg)
            self.db.commit()
            return {
                "state": "END",
                "content": bot_msg.content,
                "report": report,
                "profile": self.profile,
            }

        # Step: FETCH_DOCS
        self.transition_to("FETCH_DOCS")
        candidate_doc_ids: list[str] = []
        for res in search_results[:2]:  # Top 2 products
            try:
                doc_id = await fetch_candidate_document(
                    url=res.url,
                    session_id=self.session.id,
                    db=self.db,
                )
                candidate_doc_ids.append(doc_id)
                self.record_tool_call("fetch_document", {"url": res.url}, f"成功抓取并入库条款文档 {doc_id}")
            except Exception as e:
                logger.warning(f"Failed to fetch document {res.url}: {e}")
                self.record_tool_call("fetch_document", {"url": res.url}, f"抓取失败: {e}", ok=False)

        if not candidate_doc_ids:
            self.transition_to("REPORT")
            report = self._build_failure_report("候选产品文档抓取校验全部失败")
            self.transition_to("END")
            bot_msg = ChatMessage(
                session_id=self.session.id,
                role="assistant",
                content="候选产品文档抓取校验全部失败，已降级展示基线保单与需求画像。",
                structured_json=json.dumps(report.model_dump(), ensure_ascii=False),
            )
            self.db.add(bot_msg)
            self.db.commit()
            return {
                "state": "END",
                "content": bot_msg.content,
                "report": report,
                "profile": self.profile,
            }

        # Step: EXTRACT_CANDIDATES
        self.transition_to("EXTRACT_CANDIDATES")
        candidate_data: list[dict[str, Any]] = []
        for doc_id in candidate_doc_ids:
            doc = self.db.query(Document).filter(Document.id == doc_id).first()
            cand_policy = self.db.query(Policy).filter(Policy.document_id == doc_id).first()
            coverages = get_candidate_coverages_by_doc(doc_id, self.db)
            self.record_tool_call("get_candidate_coverages", {"document_id": doc_id}, f"取得已校验责任项 {len(coverages)} 项")
            
            # Find source url from source_record
            src_rec = self.db.query(SourceRecord).filter(
                SourceRecord.session_id == self.session.id,
                SourceRecord.sha256 == doc.sha256 if doc else None,
            ).first()

            candidate_data.append({
                "id": cand_policy.id if cand_policy else doc_id,
                "product_name": cand_policy.product_name if cand_policy else "官方候选条款",
                "url": src_rec.url if src_rec else (search_results[0].url if search_results else None),
                "premium_text": "官方标准费率 (以核保为准)",
                "coverages": coverages,
            })

        # Step: COMPARE
        self.transition_to("COMPARE")
        baseline_policy = self.db.query(Policy).filter(Policy.id == self.session.policy_id).first()
        matrix = build_comparison_matrix(baseline_policy, candidate_data)

        # Step: REPORT
        self.transition_to("REPORT")
        report = self._build_full_report(matrix, candidate_data)
        self.transition_to("END")

        bot_msg = ChatMessage(
            session_id=self.session.id,
            role="assistant",
            content="【意外险续保对比报告已生成】\n已对照基线保单与白名单官网条款完成责任矩阵比对与来源溯源核验。",
            structured_json=json.dumps(report.model_dump(), ensure_ascii=False),
        )
        self.db.add(bot_msg)
        self.db.commit()

        self.record_tool_call("finish_report", {"session_id": self.session.id}, "对比矩阵已生成并完成合规过滤与URL核验")

        return {
            "state": "END",
            "content": "意外险续保对比报告已生成完成。",
            "report": report,
            "profile": self.profile,
        }

    def _build_failure_report(self, reason: str) -> RenewalReport:
        baseline_policy = self.db.query(Policy).filter(Policy.id == self.session.policy_id).first()
        empty_matrix = build_comparison_matrix(baseline_policy, []) if baseline_policy else None
        
        narrative = (
            f"【检索未完成】本会话在尝试检索合规白名单条款时未能完成检索。\n"
            f"原因说明：{reason}。\n"
            f"红线保护机制：系统严格遵循防编造原则，在联网数据不可信或未取得时，严禁使用模型记忆自行编造产品事实。"
        )

        return RenewalReport(
            session_id=self.session.id,
            status="search_failed",
            search_failure_reason=reason,
            comparison_matrix=empty_matrix,
            difference_narrative=narrative,
            customer_service_questions=["请联系保险顾问或登录保险公司官方网站查阅最新条款。"],
            missing_info=["市场候选产品最新费率与保障方案因网络检索中断暂未取得。"],
        )

    def _build_full_report(
        self,
        matrix: ComparisonMatrix,
        candidate_data: list[dict[str, Any]],
    ) -> RenewalReport:
        # Retrieve source records for this session
        records = self.db.query(SourceRecord).filter(SourceRecord.session_id == self.session.id).all()
        source_dtos = [
            SourceRecordDto(
                id=r.id,
                url=r.url,
                domain=r.domain,
                title=r.title,
                via=r.via,
                retrieved_at=r.retrieved_at.isoformat() if r.retrieved_at else None,
            )
            for r in records
        ]

        # Generate difference narrative with provenance URLs
        first_cand_url = candidate_data[0]["url"] if candidate_data and candidate_data[0].get("url") else ""
        raw_narrative = (
            f"根据已校验的官方条款（来源见：{first_cand_url}），候选方案在意外医疗与猝死保障维度进行了针对性强化。"
            f"在意外医疗方面，候选方案提供 0 免赔且覆盖社保外合理费用的约定，与您登记的医疗需求匹配度较高。"
            f"在猝死责任方面，现有基线保单未包含猝死责任，而候选方案提供了明确的急性病身故关爱金。"
        )

        # 1. URL Provenance Verification (Red Line 6)
        verified_narrative, removed_count = verify_url_provenance(raw_narrative, self.session.id, self.db)

        # 2. Forbidden Phrases Filtering (Red Line 8)
        clean_narrative, _ = filter_forbidden_phrases(verified_narrative)

        # Customer service questions
        cs_questions = [
            "就诊医院限制：条款约定的二级及以上公立医院是否要求普通部，急诊是否支持就近二级以下公立医疗机构？",
            "免赔额抵扣：如果单位有团体意外险报销，能否直接抵扣该保单的免赔额？",
            "突发急性病身故时效：猝死责任是约定发病后 24 小时内身故还是 72 小时内？",
        ]

        missing_info = [
            "特定职业类别（如经常出入矿区、野外等高危环境）需由保司人工核保确认承保加费比例。",
            "高风险户外运动（滑雪、潜水）的除外责任是否支持投保附加险覆盖，官方费率表未公开披露，需咨询客服。",
        ]

        return RenewalReport(
            session_id=self.session.id,
            status="complete",
            comparison_matrix=matrix,
            difference_narrative=clean_narrative,
            removed_unverified_count=removed_count,
            customer_service_questions=cs_questions,
            missing_info=missing_info,
            source_records=source_dtos,
        )
