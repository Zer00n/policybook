from typing import Literal
from pydantic import BaseModel, Field


class ClaimSimulateRequest(BaseModel):
    member_id: str
    event_kind: Literal["illness", "accident", "death", "other"] = "illness"
    event_date: str  # YYYY-MM-DD
    description: str
    total_cost: float = Field(..., ge=0)
    si_covered_cost: float | None = None
    si_reimbursed: float | None = None
    has_si: bool = True
    city: str | None = None
    selected_policy_ids: list[str] | None = None


class WaterfallStepDto(BaseModel):
    label: str
    amount_low: float
    amount_high: float
    remaining_low: float
    remaining_high: float
    coverage_id: str | None = None
    policy_name: str | None = None
    note: str | None = None
    evidence_quote: str | None = None
    evidence_page_no: int | None = None
    evidence_rects: list[dict[str, float]] = []


class LumpSumDto(BaseModel):
    coverage_id: str
    coverage_name: str
    policy_name: str
    amount: float
    note: str | None = None
    evidence_quote: str | None = None
    evidence_page_no: int | None = None
    evidence_rects: list[dict[str, float]] = []


class ExcludedCoverageDto(BaseModel):
    coverage_id: str
    coverage_name: str
    policy_name: str
    reason: str


class ClaimSimulateResponse(BaseModel):
    member_id: str
    member_name: str
    event_kind: str
    event_date: str
    extracted_facts: list[str] = []
    waterfall_steps: list[WaterfallStepDto] = []
    lump_sums: list[LumpSumDto] = []
    excluded: list[ExcludedCoverageDto] = []
    out_of_pocket_low: float
    out_of_pocket_high: float
    confirm_with_insurer: list[str] = []
    materials_needed: list[str] = []
    disclaimer: str = "保单簿根据你上传的合同文本整理信息，帮助你理解条款和估算大致范围。所有结论以保险公司的核定和合同原文为准，本工具不构成投保建议、核保意见或理赔承诺。"
