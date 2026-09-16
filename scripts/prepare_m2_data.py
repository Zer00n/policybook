import asyncio
import json
from pathlib import Path
from ulid import ULID
import sys

# 将 backend 加入 sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "backend"))

from app.db.crypto import encrypt_str
from app.db.init_db import init_db
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
    now_utc,
)
from app.db.session import SessionLocal
from app.settings import settings


def prepare_m2_data():
    init_db()
    db = SessionLocal()

    print("开始准备 M2 演示与截图数据...")

    # 1. 确保家庭成员
    m1 = db.query(Member).filter(Member.placeholder == "〔成员A〕").first()
    if not m1:
        m1 = Member(
            display_name="爸爸",
            relation="本人",
            birth_year=1980,
            gender="男",
            occupation="高级软件工程师",
            city="北京",
            social_insurance="职工",
            color="#2A8F82",
            placeholder="〔成员A〕",
            real_name_enc=encrypt_str("张伟明"),
        )
        db.add(m1)

    m2 = db.query(Member).filter(Member.placeholder == "〔成员B〕").first()
    if not m2:
        m2 = Member(
            display_name="大宝",
            relation="子女",
            birth_year=2012,
            gender="男",
            occupation="在读学生",
            city="北京",
            social_insurance="居民",
            color="#5E54C9",
            placeholder="〔成员B〕",
            real_name_enc=encrypt_str("张子轩"),
        )
        db.add(m2)

    m3 = db.query(Member).filter(Member.placeholder == "〔成员C〕").first()
    if not m3:
        m3 = Member(
            display_name="妈妈",
            relation="配偶",
            birth_year=1982,
            gender="女",
            occupation="产品经理",
            city="北京",
            social_insurance="职工",
            color="#C98217",
            placeholder="〔成员C〕",
            real_name_enc=encrypt_str("李晓华"),
        )
        db.add(m3)

    db.commit()
    db.refresh(m1)
    db.refresh(m2)
    db.refresh(m3)

    # 2. 查找已存在的文档或创建模拟文档与页面
    doc = db.query(Document).filter(Document.mime == "application/pdf").order_by(Document.created_at.desc()).first()
    if not doc:
        doc_id = str(ULID())
        doc_dir = settings.abs_data_dir / "documents" / doc_id
        doc_dir.mkdir(parents=True, exist_ok=True)
        doc = Document(
            id=doc_id,
            sha256="m2_demo_sha256",
            original_name="中国平安守护综合意外伤害保险合同.pdf",
            mime="application/pdf",
            page_count=2,
            source="upload",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        p1 = Page(
            document_id=doc.id,
            page_no=1,
            image_path=str((doc_dir / "p001.png").resolve()),
            char_map_path=str((doc_dir / "p001_chars.json").resolve()),
            text_raw_enc=encrypt_str("平安人寿保险股份有限公司\n产品名称：平安守护综合意外险\n基本保额：500,000.00元\n首年保费：1,280元\n投保人：张伟明\n被保险人：张伟明"),
            text_masked="平安人寿保险股份有限公司\n产品名称：平安守护综合意外险\n基本保额：500,000.00元\n首年保费：1,280元\n投保人：〔成员A〕\n被保险人：〔成员A〕",
            width=595,
            height=842,
            pii_status="success",
        )
        db.add(p1)
        db.commit()

    # 3. 创建用于核对页展示的 Job (review_ready)
    review_job_id = "01M2REVIEWJOB0000000000001"
    existing_job = db.query(Job).filter(Job.id == review_job_id).first()
    if not existing_job:
        review_draft = {
            "document_id": doc.id,
            "document_name": "中国平安守护综合意外伤害保险合同.pdf",
            "category": "accident",
            "term_type": "long_term",
            "pages": [
                {
                    "page_no": 1,
                    "width": 595,
                    "height": 842,
                    "image_url": f"/api/documents/{doc.id}/pages/1/image?masked=0",
                    "masked_image_url": f"/api/documents/{doc.id}/pages/1/image?masked=1",
                },
                {
                    "page_no": 2,
                    "width": 595,
                    "height": 842,
                    "image_url": f"/api/documents/{doc.id}/pages/2/image?masked=0",
                    "masked_image_url": f"/api/documents/{doc.id}/pages/2/image?masked=1",
                },
            ],
            "fields": {
                "insurer": {
                    "key": "insurer",
                    "label": "保险公司",
                    "value": "中国平安人寿保险股份有限公司",
                    "original_model_value": "中国平安人寿保险股份有限公司",
                    "quote": "中国平安人寿保险股份有限公司",
                    "page_no": 1,
                    "status": "verified",
                    "rects": [{"x0": 45.0, "y0": 48.0, "x1": 240.0, "y1": 66.0}],
                },
                "product_name": {
                    "key": "product_name",
                    "label": "产品名称",
                    "value": "平安守护综合意外险",
                    "original_model_value": "平安守护综合意外险",
                    "quote": "产品名称：平安守护综合意外险",
                    "page_no": 1,
                    "status": "verified",
                    "rects": [{"x0": 45.0, "y0": 75.0, "x1": 260.0, "y1": 95.0}],
                },
                "sum_insured": {
                    "key": "sum_insured",
                    "label": "基本保额",
                    "value": "50万元",
                    "original_model_value": "50万元",
                    "quote": "基本保额：500,000.00元",
                    "page_no": 1,
                    "status": "verified",
                    "rects": [{"x0": 45.0, "y0": 105.0, "x1": 230.0, "y1": 125.0}],
                },
                "premium": {
                    "key": "premium",
                    "label": "首期保费",
                    "value": "1280元",
                    "original_model_value": "1280元",
                    "quote": "首年保费：1,280.00元",
                    "page_no": 1,
                    "status": "verified",
                    "rects": [{"x0": 45.0, "y0": 135.0, "x1": 210.0, "y1": 155.0}],
                },
                "pay_mode": {
                    "key": "pay_mode",
                    "label": "缴费方式",
                    "value": "银行自动转账",
                    "original_model_value": "银行自动转账",
                    "quote": "交费方式：银行自动转账",
                    "page_no": 1,
                    "status": "verified",
                    "rects": [{"x0": 45.0, "y0": 165.0, "x1": 190.0, "y1": 185.0}],
                },
                "pay_years": {
                    "key": "pay_years",
                    "label": "交费期间",
                    "value": "20年",
                    "original_model_value": "20年",
                    "quote": "交费期间：二十年",
                    "page_no": 1,
                    "status": "verified",
                    "rects": [{"x0": 45.0, "y0": 195.0, "x1": 170.0, "y1": 215.0}],
                },
                "apply_date": {
                    "key": "apply_date",
                    "label": "投保日期",
                    "value": "2025-03-15",
                    "original_model_value": "2025-03-15",
                    "quote": "投保日期：2025年03月15日",
                    "page_no": 1,
                    "status": "verified",
                    "rects": [{"x0": 45.0, "y0": 225.0, "x1": 220.0, "y1": 245.0}],
                },
                "effective_date": {
                    "key": "effective_date",
                    "label": "生效日期",
                    "value": "2025-03-16",
                    "original_model_value": "2025-03-16",
                    "quote": "生效日期：2025年03月16日零时",
                    "page_no": 1,
                    "status": "verified",
                    "rects": [{"x0": 45.0, "y0": 255.0, "x1": 245.0, "y1": 275.0}],
                },
                "cooling_days": {
                    "key": "cooling_days",
                    "label": "犹豫期",
                    "value": "15天",
                    "original_model_value": "15天",
                    "quote": "自签收本保险合同次日起十五日为犹豫期",
                    "page_no": 2,
                    "status": "verified",
                    "rects": [{"x0": 45.0, "y0": 60.0, "x1": 320.0, "y1": 80.0}],
                },
                "waiting_days": {
                    "key": "waiting_days",
                    "label": "等待期",
                    "value": "0天",
                    "original_model_value": "0天",
                    "quote": "本保险无等待期，自生效之日零时起承担保险责任",
                    "page_no": 2,
                    "status": "verified",
                    "rects": [{"x0": 45.0, "y0": 90.0, "x1": 340.0, "y1": 110.0}],
                },
            },
            "parties": {
                "applicant": {
                    "key": "applicant",
                    "label": "投保人",
                    "value": "〔成员A〕",
                    "original_model_value": "〔成员A〕",
                    "quote": "投保人姓名：〔成员A〕",
                    "page_no": 1,
                    "status": "verified",
                    "rects": [{"x0": 45.0, "y0": 300.0, "x1": 180.0, "y1": 320.0}],
                },
                "insureds": [
                    {
                        "key": "insured_1",
                        "label": "被保险人1",
                        "value": "〔成员A〕",
                        "original_model_value": "〔成员A〕",
                        "quote": "被保险人姓名：〔成员A〕",
                        "page_no": 1,
                        "status": "verified",
                        "rects": [{"x0": 45.0, "y0": 330.0, "x1": 190.0, "y1": 350.0}],
                    }
                ],
                "beneficiaries": [],
            },
            "coverages": [
                {
                    "id": "cov_1",
                    "name": "意外身故及伤残保障",
                    "kind": "death",
                    "limit": {
                        "value": "50万元",
                        "quote": "本公司按基本保险金额 500,000.00 元给付身故保险金，本合同终止。",
                        "page_no": 2,
                        "status": "verified",
                        "rects": [{"x0": 45.0, "y0": 130.0, "x1": 380.0, "y1": 150.0}],
                    },
                    "deductible": {"value": "0元", "status": "verified"},
                    "deductible_scope": "none",
                    "is_rider": False,
                },
                {
                    "id": "cov_2",
                    "name": "意外医疗费用补偿",
                    "kind": "accident_medical",
                    "limit": {
                        "value": "3万元",
                        "quote": "基本保额限额为 30,000 元。",
                        "page_no": 2,
                        "status": "verified",
                        "rects": [{"x0": 45.0, "y0": 160.0, "x1": 220.0, "y1": 180.0}],
                    },
                    "deductible": {
                        "value": "100元",
                        "quote": "在扣除 100 元免赔额后按约定比例给付",
                        "page_no": 2,
                        "status": "verified",
                        "rects": [{"x0": 45.0, "y0": 190.0, "x1": 280.0, "y1": 210.0}],
                    },
                    "ratio_with_si": {"value": "100%"},
                    "ratio_without_si": {"value": "80%"},
                    "deductible_scope": "per_claim",
                    "is_rider": False,
                },
                {
                    "id": "cov_3",
                    "name": "意外住院津贴保障",
                    "kind": "hospital_allowance",
                    "limit": {
                        "value": "150元/天",
                        "quote": "意外伤害住院津贴为每日 150 元，单次以 90 天为限。",
                        "page_no": 2,
                        "status": "verified",
                        "rects": [{"x0": 45.0, "y0": 220.0, "x1": 360.0, "y1": 240.0}],
                    },
                    "deductible": {"value": "0元", "status": "verified"},
                    "deductible_scope": "none",
                    "is_rider": True,
                },
            ],
            "exclusions": [
                {
                    "id": "excl_1",
                    "quote": "被保险人从事潜水、跳伞、攀岩、蹦极等高风险运动期间遭受的意外伤害，本公司不承担给付保险金责任。",
                    "page_no": 2,
                    "status": "verified",
                    "rects": [{"x0": 45.0, "y0": 260.0, "x1": 460.0, "y1": 290.0}],
                    "plain_explanation": "从事潜水、攀岩、蹦极等高风险运动发生的意外伤害不予赔偿。",
                },
                {
                    "id": "excl_2",
                    "quote": "被保险人酒后驾驶、无合法有效驾驶证驾驶，或驾驶无有效行驶证的机动车导致的事故，本公司不承担责任。",
                    "page_no": 2,
                    "status": "verified",
                    "rects": [{"x0": 45.0, "y0": 300.0, "x1": 480.0, "y1": 330.0}],
                    "plain_explanation": "酒驾、无证驾驶机动车导致的事故不在理赔范围内。",
                },
            ],
            "summary": {
                "total_fields": 10,
                "verified_count": 10,
                "unverified_count": 0,
                "not_found_count": 0,
                "conflict_count": 0,
            },
        }

        job = Job(
            id=review_job_id,
            kind="import",
            status="review_ready",
            step="review",
            payload_json=json.dumps(review_draft, ensure_ascii=False),
            progress=1.0,
        )
        db.add(job)
        db.commit()
        print(f"已创建核对演示任务: {review_job_id}")

    # 4. 创建已确认入库的 Policy（平安守护综合意外险）
    pol_id_1 = "01M2POLICY000000000000001"
    existing_pol_1 = db.query(Policy).filter(Policy.id == pol_id_1).first()
    if not existing_pol_1:
        pol_1 = Policy(
            id=pol_id_1,
            document_id=doc.id,
            insurer="中国平安人寿保险股份有限公司",
            product_name="平安守护综合意外险",
            policy_no_enc=encrypt_str("PA20250315-9988231"),
            category="accident",
            subcategory="综合人身意外险",
            term_type="long_term",
            premium_cents=128000,
            pay_mode="年交",
            pay_years="20年",
            sum_insured_cents=50000000,
            apply_date="2025-03-15",
            effective_date="2025-03-16",
            expiry_date="2045-03-15",
            cooling_days=15,
            waiting_days=0,
            guaranteed_renewal=True,
            renewal_years="20年",
            status="active",
            confirmed_at=now_utc(),
        )
        db.add(pol_1)
        db.flush()

        # 关联人员
        db.add(PolicyParty(policy_id=pol_1.id, member_id=m1.id, role="insured", share=100))
        db.add(PolicyParty(policy_id=pol_1.id, member_id=m1.id, role="applicant", share=100))
        db.add(PolicyParty(policy_id=pol_1.id, member_id=m3.id, role="beneficiary", share=100))

        # 关联责任
        c1 = Coverage(
            id="01M2COV0000000000000000001",
            policy_id=pol_1.id,
            name="意外身故及伤残保障",
            kind="death",
            limit_cents=50000000,
            deductible_cents=0,
            deductible_scope="none",
            ratio_with_si=1000,
            is_rider=False,
        )
        db.add(c1)
        db.flush()
        db.add(Evidence(
            owner_type="coverage",
            owner_id=c1.id,
            field="limit",
            page_no=1,
            quote="本公司按基本保险金额 500,000.00 元给付身故保险金，本合同终止。",
            rects_json=json.dumps([{"x0": 45.0, "y0": 105.0, "x1": 230.0, "y1": 125.0}]),
            status="verified",
        ))

        c2 = Coverage(
            id="01M2COV0000000000000000002",
            policy_id=pol_1.id,
            name="意外医疗费用补偿",
            kind="accident_medical",
            limit_cents=3000000,
            deductible_cents=10000,
            deductible_scope="per_claim",
            ratio_with_si=1000,
            ratio_without_si=800,
            is_rider=False,
        )
        db.add(c2)
        db.flush()
        db.add(Evidence(
            owner_type="coverage",
            owner_id=c2.id,
            field="limit",
            page_no=1,
            quote="基本保额限额为 30,000 元。",
            rects_json=json.dumps([{"x0": 45.0, "y0": 135.0, "x1": 210.0, "y1": 155.0}]),
            status="verified",
        ))

        c3 = Coverage(
            id="01M2COV0000000000000000003",
            policy_id=pol_1.id,
            name="意外住院津贴保障",
            kind="hospital_allowance",
            limit_cents=15000,
            deductible_cents=0,
            deductible_scope="none",
            is_rider=True,
            waiting_days=3,
        )
        db.add(c3)

        # 关联免责条款 Clauses
        cl1 = Clause(
            id="01M2CL00000000000000000001",
            document_id=doc.id,
            page_no=1,
            clause_no="EXCL-1",
            title="从事潜水、攀岩、蹦极等高风险运动发生的意外伤害不予赔偿。",
            category="exclusion",
            text_masked="被保险人从事潜水、跳伞、攀岩、蹦极等高风险运动期间遭受的意外伤害，本公司不承担给付保险金责任。",
        )
        db.add(cl1)
        db.flush()
        db.add(Evidence(
            owner_type="clause",
            owner_id=cl1.id,
            field="exclusion",
            page_no=1,
            quote="被保险人从事潜水、跳伞、攀岩、蹦极等高风险运动期间遭受的意外伤害，本公司不承担给付保险金责任。",
            rects_json=json.dumps([{"x0": 45.0, "y0": 260.0, "x1": 460.0, "y1": 290.0}]),
            status="verified",
        ))

        cl2 = Clause(
            id="01M2CL00000000000000000002",
            document_id=doc.id,
            page_no=1,
            clause_no="EXCL-2",
            title="酒驾、无证驾驶机动车导致的事故不在理赔范围内。",
            category="exclusion",
            text_masked="被保险人酒后驾驶、无合法有效驾驶证驾驶，或驾驶无有效行驶证的机动车导致的事故，本公司不承担责任。",
        )
        db.add(cl2)
        db.flush()
        db.add(Evidence(
            owner_type="clause",
            owner_id=cl2.id,
            field="exclusion",
            page_no=1,
            quote="被保险人酒后驾驶、无合法有效驾驶证驾驶，或驾驶无有效行驶证的机动车导致的事故，本公司不承担责任。",
            rects_json=json.dumps([{"x0": 45.0, "y0": 300.0, "x1": 480.0, "y1": 330.0}]),
            status="verified",
        ))

        # 写入 FTS 虚拟表
        try:
            db.connection().exec_driver_sql(
                "INSERT INTO clause_fts(text_masked, title) VALUES (?, ?)",
                (cl1.text_masked, cl1.title),
            )
            db.connection().exec_driver_sql(
                "INSERT INTO clause_fts(text_masked, title) VALUES (?, ?)",
                (cl2.text_masked, cl2.title),
            )
        except Exception:
            pass

        # 写入 Policy Evidence
        db.add(Evidence(
            owner_type="policy",
            owner_id=pol_1.id,
            field="product_name",
            page_no=1,
            quote="产品名称：平安守护综合意外险",
            rects_json=json.dumps([{"x0": 45.0, "y0": 75.0, "x1": 260.0, "y1": 95.0}]),
            status="verified",
        ))

        print(f"已创建演示保单 1: {pol_1.product_name} ({pol_id_1})")

    # 5. 创建第二份已确认入库的 Policy（泰康健康尊享全球医疗险）
    pol_id_2 = "01M2POLICY000000000000002"
    existing_pol_2 = db.query(Policy).filter(Policy.id == pol_id_2).first()
    if not existing_pol_2:
        pol_2 = Policy(
            id=pol_id_2,
            document_id=doc.id,
            insurer="泰康人寿保险有限责任公司",
            product_name="泰康健康尊享全球医疗保险",
            policy_no_enc=encrypt_str("TK8809202501001"),
            category="medical",
            subcategory="中高端百万医疗",
            term_type="one_year",
            premium_cents=360000,
            pay_mode="年交",
            pay_years="1年",
            sum_insured_cents=300000000,
            apply_date="2025-01-10",
            effective_date="2025-01-11",
            expiry_date="2026-01-10",
            cooling_days=15,
            waiting_days=30,
            guaranteed_renewal=False,
            status="active",
            confirmed_at=now_utc(),
        )
        db.add(pol_2)
        db.flush()

        db.add(PolicyParty(policy_id=pol_2.id, member_id=m3.id, role="insured", share=100))
        db.add(PolicyParty(policy_id=pol_2.id, member_id=m1.id, role="applicant", share=100))

        c2_1 = Coverage(
            policy_id=pol_2.id,
            name="一般医疗保险金",
            kind="medical",
            limit_cents=300000000,
            deductible_cents=1000000,
            deductible_scope="annual",
            ratio_with_si=1000,
            ratio_without_si=600,
            waiting_days=30,
        )
        db.add(c2_1)

        c2_2 = Coverage(
            policy_id=pol_2.id,
            name="重大疾病医疗保险金",
            kind="critical_illness",
            limit_cents=600000000,
            deductible_cents=0,
            deductible_scope="none",
            ratio_with_si=1000,
            ratio_without_si=1000,
            waiting_days=30,
        )
        db.add(c2_2)

        print(f"已创建演示保单 2: {pol_2.product_name} ({pol_id_2})")

    # 6. 创建第三份已确认入库的 Policy（大宝的少儿重疾险 - 等待期状态）
    pol_id_3 = "01M2POLICY000000000000003"
    existing_pol_3 = db.query(Policy).filter(Policy.id == pol_id_3).first()
    if not existing_pol_3:
        pol_3 = Policy(
            id=pol_id_3,
            document_id=doc.id,
            insurer="中国人寿保险股份有限公司",
            product_name="国寿少儿青云卫重大疾病保险",
            policy_no_enc=encrypt_str("CLIC20250218-0091"),
            category="critical_illness",
            subcategory="少儿少发特定重疾险",
            term_type="long_term",
            premium_cents=450000,
            pay_mode="年交",
            pay_years="30年",
            sum_insured_cents=60000000,
            apply_date="2025-02-18",
            effective_date="2025-02-19",
            expiry_date="2055-02-18",
            cooling_days=15,
            waiting_days=90,
            guaranteed_renewal=True,
            status="waiting",
            confirmed_at=now_utc(),
        )
        db.add(pol_3)
        db.flush()

        db.add(PolicyParty(policy_id=pol_3.id, member_id=m2.id, role="insured", share=100))
        db.add(PolicyParty(policy_id=pol_3.id, member_id=m1.id, role="applicant", share=100))

        c3_1 = Coverage(
            policy_id=pol_3.id,
            name="重大疾病保险金（110种）",
            kind="critical_illness",
            limit_cents=60000000,
            deductible_cents=0,
            deductible_scope="none",
            waiting_days=90,
        )
        db.add(c3_1)

        c3_2 = Coverage(
            policy_id=pol_3.id,
            name="少儿罕见疾病关爱保险金",
            kind="critical_illness",
            limit_cents=120000000,
            deductible_cents=0,
            deductible_scope="none",
            waiting_days=90,
            is_rider=True,
        )
        db.add(c3_2)

        print(f"已创建演示保单 3: {pol_3.product_name} ({pol_id_3})")

    db.commit()
    db.close()
    print("M2 数据准备完毕。")


if __name__ == "__main__":
    prepare_m2_data()
