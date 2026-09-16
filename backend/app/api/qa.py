import json
from pathlib import Path
import re
from typing import Any, AsyncGenerator, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from jinja2 import Template
from pydantic import BaseModel
from sqlalchemy.orm import Session
import httpx

from app.db.session import get_db
from app.db.models import Clause, Coverage, Document, Member, Page, Policy, PolicyParty
from app.llm.manager import ModelManager
from app.llm.ark import extract_json_from_text
from app.settings import settings
from app.utils.verify import verify_quote

router = APIRouter(prefix="/qa", tags=["qa"])
model_manager = ModelManager()


class QARequest(BaseModel):
    question: str
    scope: Literal["all", "member", "policy"] = "all"
    member_id: str | None = None
    policy_id: str | None = None
    stream: bool = True


class CitationDto(BaseModel):
    document_id: str | None = None
    policy_id: str | None = None
    policy_name: str | None = None
    page: int
    quote: str
    status: str  # verified / unverified / not_found
    rects: list[dict[str, float]] = []


class QAAnswerDto(BaseModel):
    verdict: Literal["likely_covered", "likely_not_covered", "depends", "no_basis"]
    verdict_label: str
    reasoning: list[str]
    citations: list[CitationDto]
    confirm_with_insurer: list[str]
    disclaimer: str = "保单簿根据你上传的合同文本整理信息，帮助你理解条款和估算大致范围。所有结论以保险公司的核定和合同原文为准，本工具不构成投保建议、核保意见或理赔承诺。"


VERDICT_LABELS = {
    "likely_covered": "可能赔付",
    "likely_not_covered": "可能不赔",
    "depends": "视具体情况而定",
    "no_basis": "条款中未找到依据",
}


def search_clauses_fts(
    db: Session,
    query_str: str,
    policy_id: str | None = None,
    member_id: str | None = None,
    limit: int = 15,
) -> list[tuple[Clause, Policy]]:
    """
    根据 DEV-GUIDE 1220：
    FTS 检索（少于 3 字或特殊字符回退 LIKE）→ 组装条款上下文。
    """
    # 预处理检索词
    clean_kw = re.sub(r"[^\w\u4e00-\u9fa5]", " ", query_str).strip()
    words = [w for w in clean_kw.split() if w]

    base_query = (
        db.query(Clause, Policy)
        .join(Document, Clause.document_id == Document.id)
        .join(Policy, Policy.document_id == Document.id)
    )

    if policy_id:
        base_query = base_query.filter(Policy.id == policy_id)
    elif member_id:
        base_query = (
            base_query.join(PolicyParty, PolicyParty.policy_id == Policy.id)
            .filter(PolicyParty.member_id == member_id)
        )

    # 1. 检查是否可以使用 FTS5 (trigram 需要至少 3 个字符)
    use_fts = any(len(w) >= 3 for w in words)
    results: list[tuple[Clause, Policy]] = []

    if use_fts:
        # 尝试 FTS5 trigram MATCH
        try:
            # 挑选前几个有效词
            fts_term = " ".join(f'"{w}"' for w in words if len(w) >= 3)
            sql = """
                SELECT c.id
                FROM clause_fts fts
                JOIN clause c ON c.rowid = fts.rowid
                WHERE clause_fts MATCH :match_term
                LIMIT :limit
            """
            rows = db.connection().exec_driver_sql(sql, {"match_term": fts_term, "limit": limit}).fetchall()
            matched_clause_ids = [r[0] for r in rows]
            if matched_clause_ids:
                results = base_query.filter(Clause.id.in_(matched_clause_ids)).limit(limit).all()
        except Exception:
            results = []

    # 2. 若 FTS 无结果或词长 < 3，回退到 LIKE
    if not results:
        like_term = words[0] if words else query_str.strip()[:10]
        if like_term:
            results = (
                base_query.filter(
                    (Clause.text_masked.like(f"%{like_term}%")) | (Clause.title.like(f"%{like_term}%"))
                )
                .limit(limit)
                .all()
            )

    # 3. 若仍无结果，返回前几条通用条款作为兜底保单上下文
    if not results:
        results = base_query.limit(limit).all()

    return results


def load_qa_prompt() -> str:
    prompt_path = settings.project_root / "backend" / "app" / "llm" / "prompts" / "qa_answer.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return "{{ question }}"


async def execute_qa_logic(
    db: Session,
    request: QARequest,
) -> tuple[dict[str, Any], list[dict[str, Any]], QAAnswerDto]:
    """
    执行问答逻辑、模型调用、子串校验与自动降级。
    """
    matched_clauses = search_clauses_fts(
        db,
        request.question,
        policy_id=request.policy_id if request.scope == "policy" else None,
        member_id=request.member_id if request.scope == "member" else None,
    )

    if not matched_clauses:
        # 全库无保单或无条款
        answer_dto = QAAnswerDto(
            verdict="no_basis",
            verdict_label=VERDICT_LABELS["no_basis"],
            reasoning=["当前检索范围内未找到任何已入库的有效保单条款。"],
            citations=[],
            confirm_with_insurer=["请先上传并核对保单合同，以获得准确依据。"],
        )
        return {}, [], answer_dto

    # 按保单聚合
    policies_map: dict[str, dict[str, Any]] = {}
    for clause, policy in matched_clauses:
        if policy.id not in policies_map:
            covs = db.query(Coverage).filter(Coverage.policy_id == policy.id).all()
            policies_map[policy.id] = {
                "id": policy.id,
                "name": policy.product_name,
                "category": policy.category,
                "insurer": policy.insurer,
                "document_id": policy.document_id,
                "coverages": [
                    {
                        "name": c.name,
                        "kind": c.kind,
                        "limit": f"{c.limit_cents/100:.2f}元" if c.limit_cents else None,
                        "deductible": f"{c.deductible_cents/100:.2f}元" if c.deductible_cents else None,
                        "ratio": f"{c.ratio_with_si/10:.0f}%" if c.ratio_with_si else None,
                    }
                    for c in covs
                ],
                "clauses": [],
            }
        policies_map[policy.id]["clauses"].append(
            {
                "page_no": clause.page_no,
                "title": clause.title,
                "text_masked": clause.text_masked,
            }
        )

    context_policies = list(policies_map.values())

    # 渲染提示词
    tmpl_content = load_qa_prompt()
    template = Template(tmpl_content)
    rendered_prompt = template.render(
        question=request.question,
        context_policies=context_policies,
    )

    # 调用模型
    provider = model_manager.get_provider()
    headers = {
        "Authorization": f"Bearer {settings.ark_api_key}",
        "Content-Type": "application/json",
    }
    endpoint = f"{provider.base_url}/chat/completions"
    payload = {
        "model": provider.model_id,
        "messages": [
            {
                "role": "system",
                "content": "你是家庭保单问答助手。必须以纯 JSON 格式输出 QAAnswer 结构。",
            },
            {"role": "user", "content": rendered_prompt},
        ],
        "temperature": 0.1,
    }

    raw_content = ""
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(endpoint, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                raw_content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as exc:
        raw_content = ""

    parsed = extract_json_from_text(raw_content) if raw_content else None
    if not parsed or not isinstance(parsed, dict):
        parsed = {
            "verdict": "no_basis",
            "reasoning": ["模型响应解析失败，无法提取有效结论。"],
            "citations": [],
            "confirm_with_insurer": ["建议直接查阅纸质合同原文。"],
        }

    # 缓存各文档页面的文本与坐标字典
    docs_pages_text: dict[str, dict[int, str]] = {}
    docs_char_maps: dict[str, dict[int, list]] = {}

    for p_info in context_policies:
        doc_id = p_info["document_id"]
        if doc_id and doc_id not in docs_pages_text:
            pages = db.query(Page).filter(Page.document_id == doc_id).all()
            docs_pages_text[doc_id] = {p.page_no: p.text_masked or "" for p in pages}
            docs_char_maps[doc_id] = {}
            for p in pages:
                cmap = []
                if p.char_map_path and Path(p.char_map_path).exists():
                    try:
                        with open(p.char_map_path, "r", encoding="utf-8") as f:
                            raw_cmap = json.load(f)
                            cmap = raw_cmap.get("chars", raw_cmap) if isinstance(raw_cmap, dict) else raw_cmap
                    except Exception:
                        cmap = []
                docs_char_maps[doc_id][p.page_no] = cmap

    # 引用校验
    citations_in = parsed.get("citations", [])
    verified_citations: list[CitationDto] = []
    has_valid_citation = False

    for c in citations_in:
        quote = c.get("quote")
        p_no = c.get("page") or 1
        pol_id = c.get("policy_id")
        doc_id = c.get("document_id")

        if not doc_id and pol_id in policies_map:
            doc_id = policies_map[pol_id]["document_id"]
        elif not doc_id and context_policies:
            doc_id = context_policies[0]["document_id"]

        pol_name = c.get("policy_name")
        if not pol_name and pol_id in policies_map:
            pol_name = policies_map[pol_id]["name"]

        pg_text = docs_pages_text.get(doc_id, {})
        ch_maps = docs_char_maps.get(doc_id, {})

        vres = verify_quote(
            pages_text=pg_text,
            target_page=p_no,
            quote=quote,
            char_maps=ch_maps,
        )

        if vres.status == "verified":
            has_valid_citation = True
            verified_citations.append(
                CitationDto(
                    document_id=doc_id,
                    policy_id=pol_id,
                    policy_name=pol_name,
                    page=vres.page_no,
                    quote=quote,
                    status="verified",
                    rects=vres.rects,
                )
            )

    verdict = parsed.get("verdict", "no_basis")
    # 红线要求：若全部引用校验失败，强制降级为 no_basis
    if not has_valid_citation and verdict != "no_basis":
        verdict = "no_basis"
        reasoning = parsed.get("reasoning", [])
        reasoning.append("（系统降级说明：模型引用的所有条款依据均未通过原文逐字校验，结论已自动降级为未找到依据）")
        parsed["reasoning"] = reasoning

    answer_dto = QAAnswerDto(
        verdict=verdict,
        verdict_label=VERDICT_LABELS.get(verdict, "条款中未找到依据"),
        reasoning=parsed.get("reasoning", []),
        citations=verified_citations,
        confirm_with_insurer=parsed.get("confirm_with_insurer", []),
    )

    return policies_map, context_policies, answer_dto


@router.post("/ask")
async def ask_question(
    request: QARequest,
    db: Session = Depends(get_db),
):
    """
    条款问答端点：支持普通 JSON 返回或 SSE 流式输出。
    """
    if not request.stream:
        _, _, answer_dto = await execute_qa_logic(db, request)
        return answer_dto

    # SSE 流式生成器
    async def event_generator() -> AsyncGenerator[str, None]:
        yield f"data: {json.dumps({'type': 'start', 'message': '正在检索条款并分析依据...'}, ensure_ascii=False)}\n\n"

        _, _, answer_dto = await execute_qa_logic(db, request)

        # 模拟逐步输出推理理由
        for step in answer_dto.reasoning:
            yield f"data: {json.dumps({'type': 'reasoning_chunk', 'text': step}, ensure_ascii=False)}\n\n"

        # 发送最终完整结构体
        yield f"data: {json.dumps({'type': 'final', 'data': answer_dto.model_dump()}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
