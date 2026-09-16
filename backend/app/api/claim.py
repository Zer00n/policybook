from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from jinja2 import Template
from sqlalchemy.orm import Session
import httpx

from app.claim.engine import (
    ClaimInput,
    MatchedCoverage,
    simulate,
)
from app.claim.schemas import (
    ClaimSimulateRequest,
    ClaimSimulateResponse,
    ExcludedCoverageDto,
    LumpSumDto,
    WaterfallStepDto,
)
from app.db.session import get_db
from app.db.models import Clause, Coverage, Document, Member, Page, Policy, PolicyParty
from app.llm.manager import ModelManager
from app.llm.ark import extract_json_from_text
from app.settings import settings
from app.utils.verify import verify_quote

router = APIRouter(prefix="/claim", tags=["claim"])
model_manager = ModelManager()


def load_claim_prompt() -> str:
    prompt_path = settings.project_root / "backend" / "app" / "llm" / "prompts" / "claim_facts.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return "{{ description }}"


@router.post("/simulate", response_model=ClaimSimulateResponse)
async def simulate_claim(
    request: ClaimSimulateRequest,
    db: Session = Depends(get_db),
):
    """
    理赔情景模拟：模型提取事实与责任项匹配 -> 纯函数引擎 Decimal 计算 -> 费用瀑布图
    """
    member = db.query(Member).filter(Member.id == request.member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="家庭成员不存在")

    # 查询该成员名下的有效保单
    party_query = (
        db.query(PolicyParty, Policy)
        .join(Policy, PolicyParty.policy_id == Policy.id)
        .filter(PolicyParty.member_id == member.id)
        .filter(Policy.status == "active")
    )
    if request.selected_policy_ids:
        party_query = party_query.filter(Policy.id.in_(request.selected_policy_ids))

    parties = party_query.all()
    policies = [p for _, p in parties]

    if not policies:
        return ClaimSimulateResponse(
            member_id=member.id,
            member_name=member.placeholder,
            event_kind=request.event_kind,
            event_date=request.event_date,
            extracted_facts=["该家庭成员名下暂无已生效的保单"],
            waterfall_steps=[
                WaterfallStepDto(
                    label="总费用",
                    amount_low=request.total_cost,
                    amount_high=request.total_cost,
                    remaining_low=request.total_cost,
                    remaining_high=request.total_cost,
                    note="无有效商业保单抵扣",
                )
            ],
            lump_sums=[],
            excluded=[],
            out_of_pocket_low=request.total_cost,
            out_of_pocket_high=request.total_cost,
            confirm_with_insurer=["暂无有效保单"],
            materials_needed=["建议先录入该成员的商业保险合同"],
        )

    # 构造候选责任项与条款
    candidate_policies: list[dict[str, Any]] = []
    coverage_dict: dict[str, Coverage] = {}
    policy_dict: dict[str, Policy] = {}

    for pol in policies:
        policy_dict[pol.id] = pol
        covs = db.query(Coverage).filter(Coverage.policy_id == pol.id).all()
        for c in covs:
            coverage_dict[c.id] = c

        clauses = db.query(Clause).filter(Clause.document_id == pol.document_id).limit(10).all()

        candidate_policies.append({
            "id": pol.id,
            "name": pol.product_name,
            "category": pol.category,
            "effective_date": pol.effective_date,
            "waiting_days": pol.waiting_days or 0,
            "coverages": [
                {
                    "id": c.id,
                    "name": c.name,
                    "kind": c.kind,
                    "limit": f"{c.limit_cents/100:.2f}元" if c.limit_cents else None,
                    "deductible": f"{c.deductible_cents/100:.2f}元" if c.deductible_cents else "0",
                }
                for c in covs
            ],
            "clauses": [
                {
                    "page_no": cl.page_no,
                    "title": cl.title,
                    "text_masked": cl.text_masked,
                }
                for cl in clauses
            ],
        })

    # 调用大模型提取事实并匹配责任项
    tmpl_content = load_claim_prompt()
    template = Template(tmpl_content)
    rendered_prompt = template.render(
        event_kind=request.event_kind,
        event_date=request.event_date,
        description=request.description,
        total_cost=request.total_cost,
        si_covered_cost=request.si_covered_cost,
        si_reimbursed=request.si_reimbursed,
        has_si=request.has_si,
        city=request.city,
        candidate_policies=candidate_policies,
    )

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
                "content": "你是保险理赔分析专家。必须以纯 JSON 格式输出 ClaimFacts 结构，不包含多余描述。",
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
    except Exception:
        raw_content = ""

    parsed = extract_json_from_text(raw_content) if raw_content else None
    if not parsed or not isinstance(parsed, dict):
        # 兜底：将候选的所有医疗/疾病责任项作为默认匹配项
        parsed = {
            "extracted_facts": [f"用户自述：{request.description}"],
            "matched_coverage_ids": [
                {"coverage_id": cid, "reason": "根据险种类型默认匹配", "quote": None, "page_no": 1}
                for cid in coverage_dict.keys()
            ],
            "confirm_with_insurer": ["需与保险公司核实本次出险是否属于免责范围"],
            "materials_needed": ["病历本、住院发票、费用清单、身份证"],
        }

    matched_ids_info = parsed.get("matched_coverage_ids", [])

    # 缓存文档页面文本与字符坐标
    docs_pages_text: dict[str, dict[int, str]] = {}
    docs_char_maps: dict[str, dict[int, list]] = {}

    def get_doc_cache(doc_id: str):
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

    # 组装 MatchedCoverage
    matched_coverages: list[MatchedCoverage] = []
    coverage_evidence_map: dict[str, dict[str, Any]] = {}

    for item in matched_ids_info:
        cid = item.get("coverage_id")
        if cid not in coverage_dict:
            continue
        cov = coverage_dict[cid]
        pol = policy_dict.get(cov.policy_id)

        eff_d: date | None = None
        if pol and pol.effective_date:
            try:
                eff_d = datetime.strptime(pol.effective_date, "%Y-%m-%d").date()
            except Exception:
                eff_d = None

        limit_dec = Decimal(str(cov.limit_cents / 100)) if cov.limit_cents else None
        ded_dec = Decimal(str(cov.deductible_cents / 100)) if cov.deductible_cents else Decimal(0)
        ratio_si_dec = Decimal(str(cov.ratio_with_si / 1000)) if cov.ratio_with_si else None
        ratio_no_si_dec = Decimal(str(cov.ratio_without_si / 1000)) if cov.ratio_without_si else None

        # 校验 quote
        quote = item.get("quote")
        p_no = item.get("page_no") or 1
        rects: list[dict[str, float]] = []

        if quote and pol and pol.document_id:
            get_doc_cache(pol.document_id)
            vres = verify_quote(
                pages_text=docs_pages_text[pol.document_id],
                target_page=p_no,
                quote=quote,
                char_maps=docs_char_maps[pol.document_id],
            )
            if vres.status == "verified":
                rects = vres.rects
                p_no = vres.page_no

        coverage_evidence_map[cid] = {
            "quote": quote,
            "page_no": p_no,
            "rects": rects,
        }

        matched_coverages.append(
            MatchedCoverage(
                id=cov.id,
                policy_id=cov.policy_id,
                policy_name=pol.product_name if pol else "未知保单",
                name=cov.name,
                kind=cov.kind,
                limit=limit_dec,
                deductible=ded_dec,
                deductible_scope=cov.deductible_scope or "none",
                ratio_with_si=ratio_si_dec,
                ratio_without_si=ratio_no_si_dec,
                effective_date=eff_d,
                waiting_days=cov.waiting_days or (pol.waiting_days if pol else None),
                reason=item.get("reason"),
            )
        )

    # 出险日期转换
    try:
        ev_date = datetime.strptime(request.event_date, "%Y-%m-%d").date()
    except Exception:
        ev_date = date.today()

    si_reimb_dec = Decimal(str(request.si_reimbursed)) if request.si_reimbursed is not None else (
        Decimal(0) if not request.has_si else None
    )
    si_cov_dec = Decimal(str(request.si_covered_cost)) if request.si_covered_cost is not None else None

    # 调用纯函数计算引擎模拟
    claim_input = ClaimInput(
        event_date=ev_date,
        event_kind=request.event_kind,
        total_cost=Decimal(str(request.total_cost)),
        si_covered_cost=si_cov_dec,
        si_reimbursed=si_reimb_dec,
        matched=matched_coverages,
    )

    result = simulate(claim_input)

    # 转换响应模型
    step_dtos: list[WaterfallStepDto] = []
    for s in result.steps:
        ev_info = coverage_evidence_map.get(s.coverage_id, {}) if s.coverage_id else {}
        pol_name = None
        if s.coverage_id and s.coverage_id in coverage_dict:
            cov = coverage_dict[s.coverage_id]
            pol = policy_dict.get(cov.policy_id)
            if pol:
                pol_name = pol.product_name

        step_dtos.append(
            WaterfallStepDto(
                label=s.label,
                amount_low=float(s.amount[0]),
                amount_high=float(s.amount[1]),
                remaining_low=float(s.remaining[0]),
                remaining_high=float(s.remaining[1]),
                coverage_id=s.coverage_id,
                policy_name=pol_name,
                note=s.note,
                evidence_quote=ev_info.get("quote"),
                evidence_page_no=ev_info.get("page_no"),
                evidence_rects=ev_info.get("rects", []),
            )
        )

    lump_dtos: list[LumpSumDto] = []
    for l in result.lump_sums:
        ev_info = coverage_evidence_map.get(l.coverage_id, {})
        lump_dtos.append(
            LumpSumDto(
                coverage_id=l.coverage_id,
                coverage_name=l.coverage_name,
                policy_name=l.policy_name,
                amount=float(l.amount[0]),
                note=l.note,
                evidence_quote=ev_info.get("quote"),
                evidence_page_no=ev_info.get("page_no"),
                evidence_rects=ev_info.get("rects", []),
            )
        )

    excluded_dtos = [
        ExcludedCoverageDto(
            coverage_id=e.coverage_id,
            coverage_name=e.coverage_name,
            policy_name=e.policy_name,
            reason=e.reason,
        )
        for e in result.excluded
    ]

    return ClaimSimulateResponse(
        member_id=member.id,
        member_name=member.placeholder,
        event_kind=request.event_kind,
        event_date=request.event_date,
        extracted_facts=parsed.get("extracted_facts", []),
        waterfall_steps=step_dtos,
        lump_sums=lump_dtos,
        excluded=excluded_dtos,
        out_of_pocket_low=float(result.out_of_pocket[0]),
        out_of_pocket_high=float(result.out_of_pocket[1]),
        confirm_with_insurer=parsed.get("confirm_with_insurer", []),
        materials_needed=parsed.get("materials_needed", []),
    )
