from typing import List, Dict, Optional
from pydantic import BaseModel


class RadarDimension(BaseModel):
    key: str  # death / critical_illness / medical / accident / income_loss / pension
    name: str  # 身故 / 重疾 / 医疗 / 意外 / 收入中断 / 养老
    effective_cents: int
    effective_yuan: float
    effective_display: str
    reference_cents: Optional[int] = None
    reference_yuan: Optional[float] = None
    reference_display: Optional[str] = None
    ratio: float  # capped at 1.20
    score_pct: int  # 0 - 120
    has_reference: bool


class MemberRadar(BaseModel):
    member_id: str
    member_name: str
    member_color: str
    dimensions: List[RadarDimension]


class RadarResponse(BaseModel):
    members: List[MemberRadar]
    dimension_names: List[str]


class HeatmapCell(BaseModel):
    status: str  # none / partial / full
    effective_yuan: float
    effective_display: str
    ratio: float
    policy_ids: List[str]
    policy_names: List[str]


class HeatmapMemberRow(BaseModel):
    member_id: str
    member_name: str
    member_color: str
    relation: str
    cells: Dict[str, HeatmapCell]


class HeatmapCategory(BaseModel):
    key: str
    name: str


class HeatmapResponse(BaseModel):
    categories: List[HeatmapCategory]
    rows: List[HeatmapMemberRow]
