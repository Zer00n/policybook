import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.crypto import encrypt_str
from app.db.models import (
    Clause,
    Coverage,
    Document,
    Evidence,
    Job,
    Member,
    Page,
    PiiMapping,
    Policy,
    PolicyParty,
    now_utc,
)
from app.db.session import get_db
from app.utils.cn_money import parse_cn_money
from app.utils.cn_ratio import parse_cn_ratio
from app.utils.verify import verify_quote

router = APIRouter(prefix="/imports", tags=["review"])


class FieldUpdatePayload(BaseModel):
    value: str | None = None
    status: str = "verified"
    member_id: str | None = None


@router.get("/{job_id}/review")
def get_review_data(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.payload_json:
        raise HTTPException(status_code=400, detail="Job has no review payload")

    data = json.loads(job.payload_json)
    review_data = data.get("review_data", data)
    return {
        "job_id": job.id,
        "job_status": job.status,
        "job_step": job.step,
        "review_data": review_data,
    }


@router.patch("/{job_id}/review/fields/{field_key}")
def update_review_field(
    job_id: str,
    field_key: str,
    payload: FieldUpdatePayload,
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job or not job.payload_json:
        raise HTTPException(status_code=404, detail="Job not found or invalid")

    payload_dict = json.loads(job.payload_json)
    has_nested = "review_data" in payload_dict
    review_data = payload_dict.get("review_data", payload_dict)
    fields = review_data.get("fields", {})

    target_field = None
    if field_key in fields:
        target_field = fields[field_key]
    else:
        # 检查是否为 parties 或 coverages
        for p_key in ("applicant", "insureds", "beneficiaries"):
            part = review_data.get("parties", {}).get(p_key)
            if isinstance(part, dict) and part.get("key") == field_key:
                target_field = part
                break
            elif isinstance(part, list):
                for p_item in part:
                    if p_item.get("key") == field_key:
                        target_field = p_item
                        break

    if not target_field:
        raise HTTPException(status_code=404, detail=f"Field {field_key} not found in review draft")

    # 红线5：不得信任客户端声称的核验状态，必须由服务端自行判定。
    old_value = target_field.get("value")
    new_value = payload.value
    if new_value != old_value:
        # 值确实被人工修改：按 DEV-GUIDE 3.5，人工修改即标记人工值，视为已核验
        resolved_status = "verified"
        target_field["conflict_reason"] = None
    else:
        # 值未发生变化：不能仅凭客户端传入的 status 判定，需重新核验原文引用
        quote = target_field.get("quote")
        if quote:
            document_id = review_data.get("document_id")
            pages = db.query(Page).filter(Page.document_id == document_id).all()
            pages_text = {p.page_no: p.text_masked or "" for p in pages}
            char_maps: dict[int, list] = {}
            for p in pages:
                cmap: list = []
                if p.char_map_path and Path(p.char_map_path).exists():
                    try:
                        with open(p.char_map_path, "r", encoding="utf-8") as f:
                            raw_cmap = json.load(f)
                            cmap = raw_cmap.get("chars", raw_cmap) if isinstance(raw_cmap, dict) else raw_cmap
                    except Exception:
                        cmap = []
                char_maps[p.page_no] = cmap

            v_res = verify_quote(
                pages_text=pages_text,
                target_page=target_field.get("page_no", 1),
                quote=quote,
                field_name=field_key,
                model_value=new_value,
                char_maps=char_maps,
            )
            resolved_status = v_res.status
            target_field["rects"] = v_res.rects
            target_field["conflict_reason"] = v_res.conflict_reason
        else:
            resolved_status = target_field.get("status", "unverified")

    target_field["value"] = new_value
    target_field["status"] = resolved_status
    if payload.member_id is not None:
        target_field["member_id"] = payload.member_id if payload.member_id != "" else None
    target_field["is_human_modified"] = True
    target_field["conflict_reason"] = None  # 人工确认后清除冲突原因

    # 重新统计 summary
    summary = review_data.get("summary", {})
    all_status_list = []
    for f in fields.values():
        all_status_list.append(f.get("status"))
    for cov in review_data.get("coverages", []):
        for cfield in ("limit", "deductible", "ratio_with_si", "ratio_without_si"):
            if cfield in cov:
                all_status_list.append(cov[cfield].get("status"))

    summary["verified_count"] = sum(1 for s in all_status_list if s == "verified")
    summary["conflict_count"] = sum(1 for s in all_status_list if s == "conflict")
    summary["unverified_count"] = sum(1 for s in all_status_list if s == "unverified")
    summary["not_found_count"] = sum(1 for s in all_status_list if s == "not_found")
    review_data["summary"] = summary

    if has_nested:
        payload_dict["review_data"] = review_data
        job.payload_json = json.dumps(payload_dict, ensure_ascii=False)
    else:
        job.payload_json = json.dumps(review_data, ensure_ascii=False)
    db.commit()

    return {"ok": True, "field": target_field, "summary": summary}


@router.post("/{job_id}/confirm")
def confirm_review(job_id: str, db: Session = Depends(get_db)):
    """
    确认入库：检查若无 conflict，正式写入 policy, policy_party, coverage, clause, evidence 表并建立 FTS 索引
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job or not job.payload_json:
        raise HTTPException(status_code=404, detail="Job not found or invalid")

    payload_dict = json.loads(job.payload_json)
    review_data = payload_dict.get("review_data", payload_dict)
    summary = review_data.get("summary", {})

    if summary.get("conflict_count", 0) > 0:
        raise HTTPException(
            status_code=400,
            detail="存在未处理的冲突字段，请先核对并修改冲突字段后再确认入库",
        )

    document_id = review_data.get("document_id")
    fields = review_data.get("fields", {})
    parties_data = review_data.get("parties", {})
    coverages_data = review_data.get("coverages", [])
    exclusions_data = review_data.get("exclusions", [])

    # 转换金额
    prem_cents = None
    if fields.get("premium", {}).get("value"):
        pm = parse_cn_money(fields["premium"]["value"])
        if pm:
            prem_cents = pm.cents

    sum_cents = None
    if fields.get("sum_insured", {}).get("value"):
        sm = parse_cn_money(fields["sum_insured"]["value"])
        if sm:
            sum_cents = sm.cents

    # 读取保单号密文（若有）
    pii_policy_no = db.query(PiiMapping).filter(
        PiiMapping.document_id == document_id,
        PiiMapping.kind == "policy_no",
    ).first()
    policy_no_enc = pii_policy_no.value_enc if pii_policy_no else None

    # 创建 Policy 记录
    policy = Policy(
        document_id=document_id,
        insurer=fields.get("insurer", {}).get("value") or "未知保险公司",
        product_name=fields.get("product_name", {}).get("value") or "未知产品",
        policy_no_enc=policy_no_enc,
        category=review_data.get("category", "accident"),
        subcategory=fields.get("subcategory", {}).get("value"),
        term_type=review_data.get("term_type", "long_term"),
        premium_cents=prem_cents,
        pay_mode=fields.get("pay_mode", {}).get("value"),
        pay_years=fields.get("pay_years", {}).get("value"),
        sum_insured_cents=sum_cents,
        apply_date=fields.get("apply_date", {}).get("value"),
        effective_date=fields.get("effective_date", {}).get("value"),
        expiry_date=fields.get("expiry_date", {}).get("value"),
        status="active",
        confirmed_at=now_utc(),
    )
    db.add(policy)
    db.flush()

    # 关联成员映射
    members = db.query(Member).all()
    placeholder_to_member = {m.placeholder: m for m in members if m.placeholder}
    id_to_member = {m.id: m for m in members}

    name_to_member = {}
    from app.db.crypto import decrypt_str
    for m in members:
        if m.display_name:
            name_to_member[m.display_name.strip()] = m
        real = decrypt_str(m.real_name_enc)
        if real:
            name_to_member[real.strip()] = m

    def link_party(role_name: str, item_dict: dict, share_pct: int = 100):
        if not item_dict or not (item_dict.get("value") or item_dict.get("member_id")):
            return

        m = None
        # 1. 优先使用人工显式绑定的 member_id
        if item_dict.get("member_id"):
            m = id_to_member.get(item_dict["member_id"])

        val = str(item_dict.get("value") or "").strip()
        # 2. 次选占位符精准匹配（例如 〔成员A〕）
        if not m and val:
            m = placeholder_to_member.get(val)

        # 3. 再次尝试真实姓名或称谓兜底智能匹配
        if not m and val:
            m = name_to_member.get(val)

        party = PolicyParty(
            policy_id=policy.id,
            member_id=m.id if m else None,
            role=role_name,
            share=share_pct,
        )
        db.add(party)

    link_party("applicant", parties_data.get("applicant"))
    for ins in parties_data.get("insureds", []):
        link_party("insured", ins)
    for ben in parties_data.get("beneficiaries", []):
        link_party("beneficiary", ben)

    # 写入 Coverages
    for c in coverages_data:
        limit_c = None
        if c.get("limit", {}).get("value"):
            lm = parse_cn_money(c["limit"]["value"])
            if lm:
                limit_c = lm.cents

        ded_c = None
        if c.get("deductible", {}).get("value"):
            dm = parse_cn_money(c["deductible"]["value"])
            if dm:
                ded_c = dm.cents

        ratio_si = None
        if c.get("ratio_with_si", {}).get("value"):
            ratio_si = parse_cn_ratio(c["ratio_with_si"]["value"])

        ratio_no_si = None
        if c.get("ratio_without_si", {}).get("value"):
            ratio_no_si = parse_cn_ratio(c["ratio_without_si"]["value"])

        waiting_d = None
        if c.get("waiting_days", {}).get("value"):
            try:
                m = re.search(r"\d+", str(c["waiting_days"]["value"]))
                if m:
                    waiting_d = int(m.group())
            except Exception:
                pass

        cov = Coverage(
            policy_id=policy.id,
            name=c.get("name", "未命名责任"),
            kind=c.get("kind", "other"),
            limit_cents=limit_c,
            deductible_cents=ded_c,
            deductible_scope=c.get("deductible_scope", "none"),
            ratio_with_si=ratio_si,
            ratio_without_si=ratio_no_si,
            waiting_days=waiting_d,
            is_rider=c.get("is_rider", False),
        )
        db.add(cov)
        db.flush()

        # 写入 Coverage Evidence (limit / deductible)
        if c.get("limit", {}).get("quote"):
            ev = Evidence(
                owner_type="coverage",
                owner_id=cov.id,
                field="limit",
                page_no=c["limit"].get("page_no", 1),
                quote=c["limit"]["quote"],
                rects_json=json.dumps(c["limit"].get("rects", []), ensure_ascii=False),
                status=c["limit"].get("status", "verified"),
                model_value=c["limit"].get("original_model_value"),
                human_value=c["limit"].get("value"),
            )
            db.add(ev)

        if c.get("deductible", {}).get("quote"):
            ev = Evidence(
                owner_type="coverage",
                owner_id=cov.id,
                field="deductible",
                page_no=c["deductible"].get("page_no", 1),
                quote=c["deductible"]["quote"],
                rects_json=json.dumps(c["deductible"].get("rects", []), ensure_ascii=False),
                status=c["deductible"].get("status", "verified"),
                model_value=c["deductible"].get("original_model_value"),
                human_value=c["deductible"].get("value"),
            )
            db.add(ev)

    # 写入 Policy Evidence
    for fkey, fitem in fields.items():
        if fitem.get("quote"):
            ev = Evidence(
                owner_type="policy",
                owner_id=policy.id,
                field=fkey,
                page_no=fitem.get("page_no", 1),
                quote=fitem["quote"],
                rects_json=json.dumps(fitem.get("rects", []), ensure_ascii=False),
                status=fitem.get("status", "verified"),
                model_value=fitem.get("original_model_value"),
                human_value=fitem.get("value"),
            )
            db.add(ev)

    # 写入免责条款 (Exclusions)
    exclusions_data = review_data.get("exclusions", [])
    for ex_idx, ex in enumerate(exclusions_data):
        quote_text = ex.get("quote") or ""
        plain_exp = ex.get("plain_explanation") or f"免责条款 {ex_idx+1}"
        p_no = ex.get("page_no") or 1

        clause = Clause(
            document_id=document_id,
            page_no=p_no,
            clause_no=f"EXCL-{ex_idx+1}",
            title=plain_exp,
            category="exclusion",
            text_masked=quote_text,
        )
        db.add(clause)
        db.flush()

        res = db.connection().exec_driver_sql(
            "SELECT rowid FROM clause WHERE id = ?", (clause.id,)
        ).fetchone()
        if res:
            c_rowid = res[0]
            db.connection().exec_driver_sql(
                "INSERT INTO clause_fts(rowid, text_masked, title) VALUES (?, ?, ?)",
                (c_rowid, quote_text, plain_exp),
            )

        if quote_text:
            ev = Evidence(
                owner_type="clause",
                owner_id=clause.id,
                field="exclusion",
                page_no=p_no,
                quote=quote_text,
                rects_json=json.dumps(ex.get("rects", []), ensure_ascii=False),
                status=ex.get("status", "verified"),
                model_value=plain_exp,
                human_value=plain_exp,
            )
            db.add(ev)

    # 写入普通页面文本 Clauses 并更新 clause_fts
    pages = db.query(Page).filter(Page.document_id == document_id).all()
    for p in pages:
        txt = p.text_masked or ""
        if txt.strip():
            clause = Clause(
                document_id=document_id,
                page_no=p.page_no,
                title=f"第{p.page_no}页条款内容",
                category="liability",
                text_masked=txt,
            )
            db.add(clause)
            db.flush()

            # 查询刚刚插入的 clause 的 SQLite rowid 并同步插入 FTS5
            res = db.connection().exec_driver_sql(
                "SELECT rowid FROM clause WHERE id = ?", (clause.id,)
            ).fetchone()
            if res:
                c_rowid = res[0]
                db.connection().exec_driver_sql(
                    "INSERT INTO clause_fts(rowid, text_masked, title) VALUES (?, ?, ?)",
                    (c_rowid, txt, clause.title),
                )

    job.status = "succeeded"
    job.step = "confirmed"
    db.commit()

    return {
        "ok": True,
        "policy_id": policy.id,
        "product_name": policy.product_name,
        "insurer": policy.insurer,
    }
