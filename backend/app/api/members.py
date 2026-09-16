from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.crypto import decrypt_str, encrypt_str
from app.db.models import Member
from app.db.session import get_db
from app.schemas.member import MemberCreate, MemberResponse, MemberUpdate

router = APIRouter(prefix="/members", tags=["Members"])

PLACEHOLDER_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def get_next_placeholder(db: Session) -> str:
    count = db.query(Member).count()
    if count < len(PLACEHOLDER_LETTERS):
        letter = PLACEHOLDER_LETTERS[count]
    else:
        letter = f"M{count + 1}"
    return f"〔成员{letter}〕"


@router.get("", response_model=list[MemberResponse])
def list_members(db: Session = Depends(get_db)):
    members = db.query(Member).order_by(Member.created_at.asc()).all()
    results = []
    for m in members:
        results.append(
            MemberResponse(
                id=m.id,
                display_name=m.display_name,
                relation=m.relation,
                birth_year=m.birth_year,
                gender=m.gender,
                occupation=m.occupation,
                city=m.city,
                social_insurance=m.social_insurance,
                color=m.color,
                placeholder=m.placeholder,
                real_name=decrypt_str(m.real_name_enc),
                created_at=m.created_at,
            )
        )
    return results


@router.post("", response_model=MemberResponse, status_code=201)
def create_member(req: MemberCreate, db: Session = Depends(get_db)):
    placeholder = get_next_placeholder(db)
    member = Member(
        display_name=req.display_name,
        relation=req.relation,
        birth_year=req.birth_year,
        gender=req.gender,
        occupation=req.occupation,
        city=req.city,
        social_insurance=req.social_insurance,
        color=req.color,
        placeholder=placeholder,
        real_name_enc=encrypt_str(req.real_name),
    )
    db.add(member)
    db.commit()
    db.refresh(member)

    return MemberResponse(
        id=member.id,
        display_name=member.display_name,
        relation=member.relation,
        birth_year=member.birth_year,
        gender=member.gender,
        occupation=member.occupation,
        city=member.city,
        social_insurance=member.social_insurance,
        color=member.color,
        placeholder=member.placeholder,
        real_name=req.real_name,
        created_at=member.created_at,
    )


@router.patch("/{member_id}", response_model=MemberResponse)
def update_member(member_id: str, req: MemberUpdate, db: Session = Depends(get_db)):
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    if req.display_name is not None:
        member.display_name = req.display_name
    if req.relation is not None:
        member.relation = req.relation
    if req.birth_year is not None:
        member.birth_year = req.birth_year
    if req.gender is not None:
        member.gender = req.gender
    if req.occupation is not None:
        member.occupation = req.occupation
    if req.city is not None:
        member.city = req.city
    if req.social_insurance is not None:
        member.social_insurance = req.social_insurance
    if req.color is not None:
        member.color = req.color
    if req.real_name is not None:
        member.real_name_enc = encrypt_str(req.real_name)

    db.commit()
    db.refresh(member)

    return MemberResponse(
        id=member.id,
        display_name=member.display_name,
        relation=member.relation,
        birth_year=member.birth_year,
        gender=member.gender,
        occupation=member.occupation,
        city=member.city,
        social_insurance=member.social_insurance,
        color=member.color,
        placeholder=member.placeholder,
        real_name=decrypt_str(member.real_name_enc),
        created_at=member.created_at,
    )


@router.delete("/{member_id}")
def delete_member(member_id: str, db: Session = Depends(get_db)):
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    db.delete(member)
    db.commit()
    return {"ok": True}
