from typing import Any, Literal
from pydantic import BaseModel, Field


class CreateRenewalSessionRequest(BaseModel):
    policy_id: str = Field(..., description="基线保单 ID")


class RenewalQuestion(BaseModel):
    dimension: str
    label: str
    question: str
    why: str
    options: list[str] = Field(default_factory=list)
    affects: list[str] = Field(default_factory=list)


class RenewalProfileItem(BaseModel):
    key: str
    label: str
    value: str
    source_message_id: str | None = None


class RenewalMessageRequest(BaseModel):
    content: str = ""
    answers: dict[str, str] | None = None  # {dimension_key: selected_option}
    skip: bool = False  # 是否明确跳过后续追问直接对比


class ComparisonCell(BaseModel):
    value: str
    status: Literal["covered", "missing", "partial", "not_found"] = "not_found"
    quote: str | None = None
    source_url: str | None = None


class ComparisonRow(BaseModel):
    dimension_key: str
    dimension_label: str
    baseline_cell: ComparisonCell
    candidate_cells: dict[str, ComparisonCell] = Field(default_factory=dict)


class ProductColumn(BaseModel):
    id: str
    name: str
    is_baseline: bool = False
    premium_text: str | None = None
    url: str | None = None


class ComparisonMatrix(BaseModel):
    products: list[ProductColumn]
    rows: list[ComparisonRow]


class SourceRecordDto(BaseModel):
    id: str | None = None
    url: str
    domain: str
    title: str | None = None
    via: str = "search"
    retrieved_at: str | None = None


class RenewalReport(BaseModel):
    session_id: str
    status: Literal["complete", "partial", "search_failed"] = "complete"
    search_failure_reason: str | None = None
    comparison_matrix: ComparisonMatrix | None = None
    difference_narrative: str = ""
    removed_unverified_count: int = 0
    customer_service_questions: list[str] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
    source_records: list[SourceRecordDto] = Field(default_factory=list)
    disclaimer: str = "保单簿根据你上传的合同文本与官方公开条款整理信息，帮助你理解条款和估算大致范围。所有结论以保险公司的核定和合同原文为准，本工具不构成投保建议、核保意见或理赔承诺。"


class ChatMessageDto(BaseModel):
    id: str
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    structured_json: str | None = None
    created_at: str


class RenewalSessionResponse(BaseModel):
    id: str
    kind: str = "renewal"
    policy_id: str | None = None
    policy_name: str | None = None
    insured_name: str | None = None
    state: str
    profile: dict[str, Any] = Field(default_factory=dict)
    current_questions: list[RenewalQuestion] = Field(default_factory=list)
    report: RenewalReport | None = None
    messages: list[ChatMessageDto] = Field(default_factory=list)
    created_at: str
    updated_at: str
