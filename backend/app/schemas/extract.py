from typing import Any, Literal
from pydantic import BaseModel, Field


class Evidence(BaseModel):
    page: int
    quote: str | None = None


class FieldValue(BaseModel):
    value: str | None = None
    evidence: Evidence | None = None


class PageClassification(BaseModel):
    page_no: int
    page_type: Literal[
        "contract",
        "application",
        "first_page",
        "clause",
        "invoice",
        "endorsement",
        "other",
    ] = "clause"
    confidence: float = 1.0


class PageTypes(BaseModel):
    pages: list[PageClassification] = Field(default_factory=list)


class PolicyExtraction(BaseModel):
    insurer: FieldValue = Field(default_factory=FieldValue)
    product_name: FieldValue = Field(default_factory=FieldValue)
    category: Literal[
        "critical_illness",
        "medical",
        "accident",
        "term_life",
        "whole_life",
        "annuity",
        "endowment_whole_life",
        "property",
        "auto",
        "other",
    ] = "accident"
    subcategory: FieldValue = Field(default_factory=FieldValue)
    term_type: FieldValue = Field(default_factory=lambda: FieldValue(value="long_term"))
    applicant: FieldValue = Field(default_factory=FieldValue)
    insureds: list[FieldValue] = Field(default_factory=list)
    beneficiaries: list[FieldValue] = Field(default_factory=list)
    sum_insured: FieldValue = Field(default_factory=FieldValue)
    premium: FieldValue = Field(default_factory=FieldValue)
    pay_mode: FieldValue = Field(default_factory=FieldValue)
    pay_years: FieldValue = Field(default_factory=FieldValue)
    apply_date: FieldValue = Field(default_factory=FieldValue)
    effective_date: FieldValue = Field(default_factory=FieldValue)
    expiry_date: FieldValue = Field(default_factory=FieldValue)
    cooling_days: FieldValue = Field(default_factory=FieldValue)
    waiting_days: FieldValue = Field(default_factory=FieldValue)
    guaranteed_renewal: FieldValue = Field(default_factory=FieldValue)


class CoverageItem(BaseModel):
    name: str
    kind: Literal[
        "death",
        "disability",
        "critical_illness",
        "medical",
        "accident_medical",
        "hospital_allowance",
        "transport_extra",
        "sudden_death",
        "other",
    ] = "other"
    limit: FieldValue = Field(default_factory=FieldValue)
    deductible: FieldValue = Field(default_factory=FieldValue)
    deductible_scope: Literal["annual", "per_claim", "none", "unknown"] = "none"
    ratio_with_si: FieldValue = Field(default_factory=FieldValue)
    ratio_without_si: FieldValue = Field(default_factory=FieldValue)
    waiting_days: FieldValue = Field(default_factory=FieldValue)
    conditions: list[Evidence] = Field(default_factory=list)
    is_rider: bool = False


class Exclusion(BaseModel):
    evidence: Evidence
    plain_explanation: str = Field(..., max_length=120)


class CoverageExtraction(BaseModel):
    coverages: list[CoverageItem] = Field(default_factory=list)
    exclusions: list[Exclusion] = Field(default_factory=list)
