import json
from fastapi.testclient import TestClient
from app.db.models import Document, Job, Member, Page, Policy
from app.db.session import SessionLocal
from app.main import app
from conftest import authenticate

client = TestClient(app)
authenticate(client)


def test_review_and_confirm_policy_pipeline():
    db = SessionLocal()
    try:
        # 1. 准备测试数据
        # 成员
        member = db.query(Member).filter(Member.placeholder == "〔成员A〕").first()
        if not member:
            member = Member(
                display_name="爸爸",
                relation="本人",
                placeholder="〔成员A〕",
                color="#2A8F82",
            )
            db.add(member)
            db.flush()

        # 文档与页面
        doc = Document(
            sha256="fake_sha256_pipeline_test",
            original_name="测试意外险保单.pdf",
            mime="application/pdf",
            page_count=1,
        )
        db.add(doc)
        db.flush()

        page = Page(
            document_id=doc.id,
            page_no=1,
            image_path="fake_p001.png",
            text_masked="平安人寿保险股份有限公司\n产品名称：平安守护综合意外险\n基本保额：500,000.00元\n首年保费：1,280元\n投保人：〔成员A〕\n被保险人：〔成员A〕",
            width=595,
            height=842,
        )
        db.add(page)
        db.flush()

        # 模拟 Job 处于 review_ready 状态，包含一个 conflict 字段
        sample_review_payload = {
            "document_id": doc.id,
            "document_name": doc.original_name,
            "category": "accident",
            "term_type": "long_term",
            "pages": [
                {
                    "page_no": 1,
                    "width": 595,
                    "height": 842,
                    "image_url": f"/api/documents/{doc.id}/pages/1/image?masked=0",
                    "masked_image_url": f"/api/documents/{doc.id}/pages/1/image?masked=1",
                }
            ],
            "fields": {
                "insurer": {
                    "key": "insurer",
                    "label": "保险公司",
                    "value": "平安人寿保险股份有限公司",
                    "original_model_value": "平安人寿保险股份有限公司",
                    "quote": "平安人寿保险股份有限公司",
                    "page_no": 1,
                    "status": "verified",
                    "rects": [{"x0": 50, "y0": 50, "x1": 200, "y1": 65}],
                },
                "product_name": {
                    "key": "product_name",
                    "label": "产品名称",
                    "value": "平安守护综合意外险",
                    "original_model_value": "平安守护综合意外险",
                    "quote": "产品名称：平安守护综合意外险",
                    "page_no": 1,
                    "status": "verified",
                    "rects": [{"x0": 50, "y0": 70, "x1": 250, "y1": 85}],
                },
                "sum_insured": {
                    "key": "sum_insured",
                    "label": "基本保额",
                    "value": "100万元",  # 故意与 quote 500,000 冲突
                    "original_model_value": "100万元",
                    "quote": "基本保额：500,000.00元",
                    "page_no": 1,
                    "status": "conflict",
                    "conflict_reason": "金额不一致：模型值 100万元 与引用原文 500,000.00元 冲突",
                    "rects": [{"x0": 50, "y0": 90, "x1": 220, "y1": 105}],
                },
                "premium": {
                    "key": "premium",
                    "label": "首期保费",
                    "value": "1280元",
                    "original_model_value": "1280元",
                    "quote": "首年保费：1,280元",
                    "page_no": 1,
                    "status": "verified",
                    "rects": [{"x0": 50, "y0": 110, "x1": 180, "y1": 125}],
                },
            },
            "parties": {
                "applicant": {
                    "key": "applicant",
                    "label": "投保人",
                    "value": "〔成员A〕",
                    "status": "verified",
                    "page_no": 1,
                },
                "insureds": [
                    {
                        "key": "insured_1",
                        "label": "被保险人1",
                        "value": "〔成员A〕",
                        "status": "verified",
                        "page_no": 1,
                    }
                ],
                "beneficiaries": [],
            },
            "coverages": [
                {
                    "id": "cov_1",
                    "name": "意外伤害身故伤残保障",
                    "kind": "death",
                    "limit": {
                        "value": "50万元",
                        "quote": "基本保额：500,000.00元",
                        "page_no": 1,
                        "status": "verified",
                        "rects": [],
                    },
                    "deductible": {"value": "0元", "status": "verified"},
                    "deductible_scope": "none",
                    "is_rider": False,
                }
            ],
            "exclusions": [],
            "summary": {
                "total_fields": 4,
                "verified_count": 3,
                "unverified_count": 0,
                "not_found_count": 0,
                "conflict_count": 1,
            },
        }

        job = Job(
            kind="import",
            status="review_ready",
            step="review",
            payload_json=json.dumps(sample_review_payload, ensure_ascii=False),
            progress=1.0,
        )
        db.add(job)
        db.commit()

        job_id = job.id

        # 2. 调用 GET /api/imports/{job_id}/review
        res_review = client.get(f"/api/imports/{job_id}/review")
        assert res_review.status_code == 200
        rev_body = res_review.json()
        assert rev_body["job_status"] == "review_ready"
        assert rev_body["review_data"]["summary"]["conflict_count"] == 1

        # 3. 尝试在存在 conflict 时直接确认入库 -> 必须拒绝 (400)
        res_confirm_fail = client.post(f"/api/imports/{job_id}/confirm")
        assert res_confirm_fail.status_code == 400
        assert "冲突字段" in res_confirm_fail.json()["error"]["message"]

        # 4. 人工修改冲突字段为 50万元 -> PATCH /api/imports/{job_id}/review/fields/sum_insured
        res_patch = client.patch(
            f"/api/imports/{job_id}/review/fields/sum_insured",
            json={"value": "50万元", "status": "verified"},
        )
        assert res_patch.status_code == 200
        patch_body = res_patch.json()
        assert patch_body["summary"]["conflict_count"] == 0
        assert patch_body["field"]["is_human_modified"] is True

        # 5. 解决冲突后确认入库 -> POST /api/imports/{job_id}/confirm
        res_confirm = client.post(f"/api/imports/{job_id}/confirm")
        assert res_confirm.status_code == 200
        policy_id = res_confirm.json()["policy_id"]
        assert policy_id is not None

        # 6. 查询保单列表与全文检索
        res_list = client.get("/api/policies")
        assert res_list.status_code == 200
        items = res_list.json()["items"]
        assert any(p["id"] == policy_id for p in items)

        # 关键词检索产品名
        res_search = client.get("/api/policies?q=平安守护")
        assert res_search.status_code == 200
        search_items = res_search.json()["items"]
        assert len(search_items) >= 1
        assert search_items[0]["product_name"] == "平安守护综合意外险"

        # 7. 获取保单详情
        res_detail = client.get(f"/api/policies/{policy_id}")
        assert res_detail.status_code == 200
        detail_data = res_detail.json()
        assert detail_data["sum_insured_cents"] == 50000000  # 50万元
        assert detail_data["premium_cents"] == 128000  # 1280元
        assert len(detail_data["coverages"]) == 1
        assert detail_data["coverages"][0]["name"] == "意外伤害身故伤残保障"
        assert len(detail_data["parties"]) >= 1

        # 8. 删除保单
        res_del = client.delete(f"/api/policies/{policy_id}")
        assert res_del.status_code == 200
    finally:
        db.close()
