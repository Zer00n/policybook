from typing import List, Optional
from pydantic import BaseModel


class TimelineSegment(BaseModel):
    segment_type: str  # waiting, effective, gap
    start_date: str  # YYYY-MM-DD
    end_date: str  # YYYY-MM-DD
    label: str
    policy_id: Optional[str] = None
    policy_name: Optional[str] = None
    color: Optional[str] = None


class PolicyTimelineBand(BaseModel):
    policy_id: str
    product_name: str
    category: str
    insurer: str
    start_date: str
    end_date: str
    segments: List[TimelineSegment]


class MemberTimeline(BaseModel):
    member_id: str
    member_name: str
    member_color: str
    relation: str
    has_gap: bool = False
    bands: List[PolicyTimelineBand]
    gap_segments: List[TimelineSegment] = []


class OverviewMetrics(BaseModel):
    total_annual_premium_cents: int
    total_annual_premium_yuan: float
    active_policy_count: int
    expiring_30d_count: int
    gap_member_count: int


class TodoItem(BaseModel):
    id: str
    kind: str  # review_draft / expiring_soon / coverage_gap / payment_due
    title: str
    description: str
    link: str
    severity: str  # info / warning / urgent
    date: Optional[str] = None


class OverviewResponse(BaseModel):
    metrics: OverviewMetrics
    timeline: List[MemberTimeline]
    todos: List[TodoItem]
    today: str
