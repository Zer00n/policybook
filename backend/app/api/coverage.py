import json
from typing import Optional, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Member, Policy, PolicyParty, AppSetting
from app.schemas.coverage import (
    RadarResponse,
    MemberRadar,
    RadarDimension,
    HeatmapResponse,
    HeatmapCategory,
    HeatmapMemberRow,
    HeatmapCell,
)
from app.coverage.calculator import (
    DIMENSIONS,
    DEFAULT_REFERENCES,
    calculate_effective_coverages,
    compute_radar_data,
    compute_heatmap_cell,
)

router = APIRouter(prefix="/coverage", tags=["Coverage"])


def get_stored_references(db: Session) -> dict:
    setting = db.query(AppSetting).filter(AppSetting.key == "coverage_references").first()
    if setting and setting.value:
        try:
            return json.loads(setting.value)
        except Exception:
            pass
    return {"default": DEFAULT_REFERENCES}


@router.get("/radar", response_model=RadarResponse)
def get_coverage_radar(member_ids: Optional[str] = None, db: Session = Depends(get_db)):
    all_members = db.query(Member).order_by(Member.created_at.asc()).all()
    if not all_members:
        return RadarResponse(members=[], dimension_names=[d["name"] for d in DIMENSIONS])

    target_ids = []
    if member_ids:
        target_ids = [m.strip() for m in member_ids.split(",") if m.strip()]

    if target_ids:
        selected_members = [m for m in all_members if m.id in target_ids][:3]
    else:
        selected_members = all_members[:3]

    references_all = get_stored_references(db)
    default_ref = references_all.get("default", DEFAULT_REFERENCES)

    radar_members = []
    for m in selected_members:
        # Fetch policies for this member
        parties = db.query(PolicyParty).filter(
            PolicyParty.member_id == m.id,
            PolicyParty.role == "insured"
        ).all()
        policy_ids = [p.policy_id for p in parties]
        policies = db.query(Policy).filter(Policy.id.in_(policy_ids)).all() if policy_ids else []

        effective_map = calculate_effective_coverages(policies)
        member_ref = references_all.get(m.id, default_ref)
        dims_data = compute_radar_data(effective_map, member_ref)

        radar_members.append(
            MemberRadar(
                member_id=m.id,
                member_name=m.display_name,
                member_color=m.color or "#2A8F82",
                dimensions=[RadarDimension(**d) for d in dims_data]
            )
        )

    return RadarResponse(
        members=radar_members,
        dimension_names=[d["name"] for d in DIMENSIONS]
    )


@router.get("/heatmap", response_model=HeatmapResponse)
def get_coverage_heatmap(db: Session = Depends(get_db)):
    members = db.query(Member).order_by(Member.created_at.asc()).all()
    references_all = get_stored_references(db)
    default_ref = references_all.get("default", DEFAULT_REFERENCES)

    categories = [HeatmapCategory(key=d["key"], name=d["name"]) for d in DIMENSIONS]
    rows: List[HeatmapMemberRow] = []

    for m in members:
        parties = db.query(PolicyParty).filter(
            PolicyParty.member_id == m.id,
            PolicyParty.role == "insured"
        ).all()
        policy_ids = [p.policy_id for p in parties]
        policies = db.query(Policy).filter(Policy.id.in_(policy_ids)).all() if policy_ids else []

        effective_map = calculate_effective_coverages(policies)
        member_ref = references_all.get(m.id, default_ref)

        cells = {}
        for d in DIMENSIONS:
            k = d["key"]
            eff = effective_map.get(k, {"effective_cents": 0, "effective_yuan": 0.0, "policies": []})
            ref_yuan = member_ref.get(k)
            cell_dict = compute_heatmap_cell(eff["effective_cents"], ref_yuan, eff.get("policies", []))
            cells[k] = HeatmapCell(**cell_dict)

        rows.append(
            HeatmapMemberRow(
                member_id=m.id,
                member_name=m.display_name,
                member_color=m.color or "#2A8F82",
                relation=m.relation or "本人",
                cells=cells
            )
        )

    return HeatmapResponse(
        categories=categories,
        rows=rows
    )
