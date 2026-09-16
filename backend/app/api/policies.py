import json
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.crypto import decrypt_str
from app.db.models import (
    Clause,
    Coverage,
    Document,
    Evidence,
    Job,
    Member,
    Page,
    Policy,
    PolicyParty,
)
from app.db.session import get_db

router = APIRouter(prefix="/policies", tags=["policies"])


@router.get("")
def list_policies(
    member_id: str | None = Query(None),
    category: str | None = Query(None),
    insurer: str | None = Query(None),
    status: str | None = Query(None),
    q: str | None = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Policy)

    if category:
        query = query.filter(Policy.category == category)
    if insurer:
        query = query.filter(Policy.insurer == insurer)
    if status and status != "all":
        query = query.filter(Policy.status == status)
    if member_id:
        query = query.join(PolicyParty).filter(PolicyParty.member_id == member_id)

    # 全文检索 (FTS5 trigram 或 LIKE)
    if q and q.strip():
        search_kw = q.strip()
        matched_doc_ids = set()

        # 1. 尝试使用 clause_fts 全文检索
        try:
            fts_rows = db.connection().exec_driver_sql(
                "SELECT rowid FROM clause_fts WHERE clause_fts MATCH ?", (search_kw,)
            ).fetchall()
            if fts_rows:
                rowids = [r[0] for r in fts_rows]
                clauses = db.query(Clause.document_id).filter(Clause.__table__.c.rowid.in_(rowids)).all()
                for c in clauses:
                    if c[0]:
                        matched_doc_ids.add(c[0])
        except Exception:
            pass

        # 2. 结合产品名、公司名模糊匹配
        query = query.filter(
            or_(
                Policy.product_name.ilike(f"%{search_kw}%"),
                Policy.insurer.ilike(f"%{search_kw}%"),
                Policy.document_id.in_(list(matched_doc_ids)) if matched_doc_ids else False,
            )
        )

    policies = query.order_by(Policy.created_at.desc()).all()

    result = []
    for p in policies:
        # 获取被保人列表
        insured_parties = (
            db.query(PolicyParty)
            .filter(PolicyParty.policy_id == p.id, PolicyParty.role == "insured")
            .all()
        )
        insured_members = []
        for ip in insured_parties:
            if ip.member:
                insured_members.append({
                    "id": ip.member.id,
                    "display_name": ip.member.display_name,
                    "color": ip.member.color,
                    "placeholder": ip.member.placeholder,
                })

        result.append({
            "id": p.id,
            "document_id": p.document_id,
            "product_name": p.product_name,
            "insurer": p.insurer,
            "category": p.category,
            "subcategory": p.subcategory,
            "term_type": p.term_type,
            "premium_cents": p.premium_cents,
            "sum_insured_cents": p.sum_insured_cents,
            "status": p.status,
            "effective_date": p.effective_date,
            "expiry_date": p.expiry_date,
            "insured_members": insured_members,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })

    return {"items": result, "total": len(result)}


@router.get("/{policy_id}")
def get_policy_detail(policy_id: str, db: Session = Depends(get_db)):
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    # 关联人员信息
    parties = db.query(PolicyParty).filter(PolicyParty.policy_id == policy.id).all()
    party_list = []
    for pt in parties:
        m = pt.member
        party_list.append({
            "id": pt.id,
            "role": pt.role,
            "share": pt.share,
            "member_id": m.id if m else None,
            "display_name": m.display_name if m else "未关联",
            "placeholder": m.placeholder if m else None,
            "color": m.color if m else "#2A8F82",
        })

    # 关联责任项
    coverages = db.query(Coverage).filter(Coverage.policy_id == policy.id).all()
    cov_list = []
    for c in coverages:
        # 获取该责任项的 evidence
        evs = db.query(Evidence).filter(Evidence.owner_id == c.id).all()
        cov_evs = []
        for ev in evs:
            rects = []
            if ev.rects_json:
                try:
                    rects = json.loads(ev.rects_json)
                except Exception:
                    pass
            cov_evs.append({
                "id": ev.id,
                "field": ev.field,
                "page_no": ev.page_no,
                "quote": ev.quote,
                "status": ev.status,
                "rects": rects,
            })

        cov_list.append({
            "id": c.id,
            "name": c.name,
            "kind": c.kind,
            "limit_cents": c.limit_cents,
            "deductible_cents": c.deductible_cents,
            "deductible_scope": c.deductible_scope,
            "ratio_with_si": c.ratio_with_si,
            "ratio_without_si": c.ratio_without_si,
            "waiting_days": c.waiting_days,
            "is_rider": c.is_rider,
            "evidences": cov_evs,
        })

    # 获取保单级别 evidence
    policy_evs = db.query(Evidence).filter(Evidence.owner_id == policy.id).all()
    field_evs = {}
    for pev in policy_evs:
        rects = []
        if pev.rects_json:
            try:
                rects = json.loads(pev.rects_json)
            except Exception:
                pass
        field_evs[pev.field] = {
            "id": pev.id,
            "page_no": pev.page_no,
            "quote": pev.quote,
            "status": pev.status,
            "rects": rects,
            "human_value": pev.human_value,
        }

    # 获取关联文档页面
    pages_data = []
    if policy.document_id:
        pages = (
            db.query(Page)
            .filter(Page.document_id == policy.document_id)
            .order_by(Page.page_no.asc())
            .all()
        )
        for p in pages:
            pages_data.append({
                "page_no": p.page_no,
                "width": p.width,
                "height": p.height,
                "image_url": f"/api/documents/{policy.document_id}/pages/{p.page_no}/image?masked=0",
                "masked_image_url": f"/api/documents/{policy.document_id}/pages/{p.page_no}/image?masked=1",
            })

    # 获取免责条款
    clauses = (
        db.query(Clause)
        .filter(Clause.document_id == policy.document_id, Clause.category == "exclusion")
        .all()
    )
    exclusions_list = []
    for cl in clauses:
        ev = db.query(Evidence).filter(Evidence.owner_id == cl.id).first()
        rects = []
        if ev and ev.rects_json:
            try:
                rects = json.loads(ev.rects_json)
            except Exception:
                pass
        exclusions_list.append({
            "id": cl.id,
            "clause_no": cl.clause_no,
            "title": cl.title,
            "plain_explanation": cl.title,
            "quote": cl.text_masked,
            "page_no": cl.page_no,
            "rects": rects,
            "status": ev.status if ev else "verified",
        })

    # 如果没有单独的 exclusion 记录，检查最近关联的 Job payload_json 是否有 exclusions（测试或过渡数据兜底）
    if not exclusions_list and policy.document_id:
        job = (
            db.query(Job)
            .filter(Job.payload_json.like(f"%{policy.document_id}%"))
            .order_by(Job.created_at.desc())
            .first()
        )
        if job and job.payload_json:
            try:
                jpayload = json.loads(job.payload_json)
                for ex_idx, ex_item in enumerate(jpayload.get("exclusions", [])):
                    exclusions_list.append({
                        "id": ex_item.get("id") or f"excl_{ex_idx+1}",
                        "clause_no": f"EXCL-{ex_idx+1}",
                        "title": ex_item.get("plain_explanation"),
                        "plain_explanation": ex_item.get("plain_explanation"),
                        "quote": ex_item.get("quote"),
                        "page_no": ex_item.get("page_no", 1),
                        "rects": ex_item.get("rects", []),
                        "status": ex_item.get("status", "verified"),
                    })
            except Exception:
                pass

    # 读取真实保单号解密（本地内网查看）
    policy_no_plain = decrypt_str(policy.policy_no_enc) if policy.policy_no_enc else None

    return {
        "id": policy.id,
        "document_id": policy.document_id,
        "insurer": policy.insurer,
        "product_name": policy.product_name,
        "policy_no": policy_no_plain,
        "category": policy.category,
        "subcategory": policy.subcategory,
        "term_type": policy.term_type,
        "premium_cents": policy.premium_cents,
        "pay_mode": policy.pay_mode,
        "pay_years": policy.pay_years,
        "sum_insured_cents": policy.sum_insured_cents,
        "apply_date": policy.apply_date,
        "effective_date": policy.effective_date,
        "expiry_date": policy.expiry_date,
        "cooling_days": policy.cooling_days,
        "waiting_days": policy.waiting_days,
        "guaranteed_renewal": policy.guaranteed_renewal,
        "renewal_years": policy.renewal_years,
        "status": policy.status,
        "confirmed_at": policy.confirmed_at.isoformat() if policy.confirmed_at else None,
        "parties": party_list,
        "coverages": cov_list,
        "exclusions": exclusions_list,
        "evidences": field_evs,
        "pages": pages_data,
    }


@router.delete("/{policy_id}")
def delete_policy(policy_id: str, db: Session = Depends(get_db)):
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    db.delete(policy)
    db.commit()
    return {"ok": True, "deleted_id": policy_id}
