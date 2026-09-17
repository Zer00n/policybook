import json
from fastapi.testclient import TestClient

from app.db.models import Document, Job, Page
from app.db.session import SessionLocal
from app.main import app
from conftest import authenticate

client = TestClient(app)
authenticate(client)


def _make_job(db, doc_id: str, fields: dict) -> str:
    payload = {
        "document_id": doc_id,
        "fields": fields,
        "parties": {"applicant": None, "insureds": [], "beneficiaries": []},
        "coverages": [],
        "exclusions": [],
        "summary": {
            "total_fields": len(fields),
            "verified_count": 0,
            "unverified_count": 0,
            "not_found_count": 0,
            "conflict_count": 0,
        },
    }
    job = Job(kind="import", status="review_ready", step="review",
              payload_json=json.dumps(payload, ensure_ascii=False), progress=1.0)
    db.add(job)
    db.commit()
    return job.id


def test_status_cannot_be_forged_without_real_change():
    """红线5：客户端在不改动取值的情况下强传 status:'verified'，不应被直接采信，
    服务端必须重新核验原文引用。"""
    db = SessionLocal()
    try:
        doc = Document(sha256="fake_sha256_review_status_1", original_name="test.pdf",
                        mime="application/pdf", page_count=1)
        db.add(doc)
        db.flush()

        page = Page(document_id=doc.id, page_no=1, image_path="fake.png",
                     text_masked="这是一份保险合同，保额为伍拾万元整。", width=595, height=842)
        db.add(page)
        db.flush()

        fields = {
            "sum_insured": {
                "key": "sum_insured",
                "label": "基本保额",
                "value": "100万元",
                "quote": "这段引用原文里根本不存在",  # 编造的引用，无法在页面文本中找到
                "page_no": 1,
                "status": "not_found",
            }
        }
        job_id = _make_job(db, doc.id, fields)

        # 客户端不改动 value，但强行声称 status 为 verified
        resp = client.patch(
            f"/api/imports/{job_id}/review/fields/sum_insured",
            json={"value": "100万元", "status": "verified"},
        )
        assert resp.status_code == 200
        body = resp.json()
        # 服务端应重新核验，quote 找不到，状态不应变成 verified
        assert body["field"]["status"] != "verified"
        assert body["field"]["status"] == "not_found"
    finally:
        db.close()


def test_status_becomes_verified_on_real_edit():
    """value 真实发生变化时，应被标记为人工核验通过（DEV-GUIDE 3.5）。"""
    db = SessionLocal()
    try:
        doc = Document(sha256="fake_sha256_review_status_2", original_name="test.pdf",
                        mime="application/pdf", page_count=1)
        db.add(doc)
        db.flush()

        page = Page(document_id=doc.id, page_no=1, image_path="fake.png",
                     text_masked="保额为伍拾万元整。", width=595, height=842)
        db.add(page)
        db.flush()

        fields = {
            "sum_insured": {
                "key": "sum_insured",
                "label": "基本保额",
                "value": "100万元",
                "quote": "保额为伍拾万元整",
                "page_no": 1,
                "status": "conflict",
            }
        }
        job_id = _make_job(db, doc.id, fields)

        resp = client.patch(
            f"/api/imports/{job_id}/review/fields/sum_insured",
            json={"value": "50万元", "status": "conflict"},  # 客户端甚至传了错误的 status，也应被忽略
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["field"]["value"] == "50万元"
        assert body["field"]["status"] == "verified"
        assert body["field"]["is_human_modified"] is True
    finally:
        db.close()


def test_status_reverifies_correctly_when_quote_is_valid():
    """value 未变化但 quote 确实能在原文中核验通过时，服务端应据实判定为 verified
    （不是盲目采信客户端，而是重新核验后恰好一致）。"""
    db = SessionLocal()
    try:
        doc = Document(sha256="fake_sha256_review_status_3", original_name="test.pdf",
                        mime="application/pdf", page_count=1)
        db.add(doc)
        db.flush()

        page = Page(document_id=doc.id, page_no=1, image_path="fake.png",
                     text_masked="保险公司为平安人寿保险股份有限公司。", width=595, height=842)
        db.add(page)
        db.flush()

        fields = {
            "insurer": {
                "key": "insurer",
                "label": "保险公司",
                "value": "平安人寿保险股份有限公司",
                "quote": "平安人寿保险股份有限公司",
                "page_no": 1,
                "status": "unverified",
            }
        }
        job_id = _make_job(db, doc.id, fields)

        resp = client.patch(
            f"/api/imports/{job_id}/review/fields/insurer",
            json={"value": "平安人寿保险股份有限公司", "status": "verified"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["field"]["status"] == "verified"
        assert len(body["field"]["rects"]) >= 0  # 不因未传 char_map 而报错
    finally:
        db.close()
