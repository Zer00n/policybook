from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Member, Policy, PolicyParty, Job
from app.schemas.overview import (
    OverviewResponse,
    MemberTimeline,
)
from app.coverage.timeline import (
    build_member_timeline,
    compute_overview_metrics,
    build_overview_todos,
    format_date,
)

router = APIRouter(prefix="/overview", tags=["Overview"])


@router.get("", response_model=OverviewResponse)
def get_overview(db: Session = Depends(get_db)):
    today = date.today()
    members = db.query(Member).order_by(Member.created_at.asc()).all()
    all_policies = db.query(Policy).all()
    review_jobs = db.query(Job).filter(
        Job.kind == "import",
        Job.status == "review_ready"
    ).all()

    # Build member timelines
    member_timelines = []
    for m in members:
        # Policies where member is insured
        parties = db.query(PolicyParty).filter(
            PolicyParty.member_id == m.id,
            PolicyParty.role == "insured"
        ).all()
        policy_ids = [p.policy_id for p in parties]
        m_policies = [pol for pol in all_policies if pol.id in policy_ids]
        mt = build_member_timeline(m, m_policies, today)
        member_timelines.append(mt)

    metrics = compute_overview_metrics(all_policies, member_timelines, today)
    todos = build_overview_todos(all_policies, review_jobs, member_timelines, today)

    return OverviewResponse(
        metrics=metrics,
        timeline=member_timelines,
        todos=todos,
        today=format_date(today)
    )
