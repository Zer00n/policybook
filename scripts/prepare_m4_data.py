import json
from datetime import date
from app.db.session import SessionLocal
from app.db.models import Member, Policy, PolicyParty, Coverage, AppSetting
from app.coverage.calculator import DEFAULT_REFERENCES
from app.jobs.reminders import generate_daily_reminders

def seed_m4_data():
    db = SessionLocal()
    try:
        # 1. Ensure 3 family members
        m_dad = db.query(Member).filter(Member.relation == "本人").first()
        if not m_dad:
            m_dad = Member(
                id="01M4MEMBER000000000000001",
                display_name="爸爸",
                relation="本人",
                birth_year=1985,
                gender="男",
                city="北京",
                social_insurance="职工",
                color="#2A8F82",
                placeholder="〔成员A〕"
            )
            db.add(m_dad)
            db.flush()
        else:
            m_dad.display_name = "爸爸"
            m_dad.color = "#2A8F82"

        m_mom = db.query(Member).filter(Member.relation == "配偶").first()
        if not m_mom:
            m_mom = Member(
                id="01M4MEMBER000000000000002",
                display_name="妈妈",
                relation="配偶",
                birth_year=1988,
                gender="女",
                city="北京",
                social_insurance="职工",
                color="#5E54C9",
                placeholder="〔成员B〕"
            )
            db.add(m_mom)
            db.flush()

        m_kid = db.query(Member).filter(Member.relation == "子女").first()
        if not m_kid:
            m_kid = Member(
                id="01M4MEMBER000000000000003",
                display_name="大宝",
                relation="子女",
                birth_year=2018,
                gender="男",
                city="北京",
                social_insurance="居民",
                color="#C98217",
                placeholder="〔成员C〕"
            )
            db.add(m_kid)
            db.flush()

        # 2. Add / Link policies for Dad (with intentional coverage gap!)
        # Dad Policy 1: Expired Accident Policy
        p_dad_old = db.query(Policy).filter(Policy.product_name == "平安综合意外险（已到期）").first()
        if not p_dad_old:
            p_dad_old = Policy(
                id="01M4POL0000000000000000001",
                insurer="中国平安人寿保险股份有限公司",
                product_name="平安综合意外险（已到期）",
                category="accident",
                term_type="one_year",
                premium_cents=29900,
                pay_mode="年交",
                sum_insured_cents=100000000,
                effective_date="2024-03-01",
                expiry_date="2025-03-01",
                waiting_days=0,
                status="lapsed"
            )
            db.add(p_dad_old)
            db.flush()
            cov1 = Coverage(
                policy_id=p_dad_old.id,
                name="意外伤害身故/伤残",
                kind="accident",
                limit_cents=100000000
            )
            db.add(cov1)

        # Dad Policy 2: New Accident Policy starting with gap
        p_dad_new = db.query(Policy).filter(Policy.product_name == "太平洋行安百万意外险").first()
        if not p_dad_new:
            p_dad_new = Policy(
                id="01M4POL0000000000000000002",
                insurer="中国太平洋财产保险股份有限公司",
                product_name="太平洋行安百万意外险",
                category="accident",
                term_type="one_year",
                premium_cents=35000,
                pay_mode="年交",
                sum_insured_cents=100000000,
                effective_date="2025-09-01",
                expiry_date="2027-09-01",
                waiting_days=0,
                status="active"
            )
            db.add(p_dad_new)
            db.flush()
            cov2 = Coverage(
                policy_id=p_dad_new.id,
                name="意外伤残与全残",
                kind="accident",
                limit_cents=100000000
            )
            db.add(cov2)

        # Dad Policy 3: Medical Policy with Waiting Period
        p_dad_med = db.query(Policy).filter(Policy.product_name == "泰康健康尊享全球医疗保险").first()
        if p_dad_med:
            p_dad_med.effective_date = "2025-09-01"
            p_dad_med.expiry_date = "2027-09-01"
            p_dad_med.waiting_days = 30
            p_dad_med.status = "active"

        # Dad Policy 4: Critical Illness
        p_dad_ci = db.query(Policy).filter(Policy.product_name == "百年多倍保终身重大疾病保险").first()
        if p_dad_ci:
            p_dad_ci.effective_date = "2024-05-01"
            p_dad_ci.expiry_date = "2054-05-01"
            p_dad_ci.waiting_days = 90
            p_dad_ci.status = "active"

        # 3. Mom Policy
        p_mom_med = db.query(Policy).filter(Policy.product_name == "众安尊享e生百万医疗2025").first()
        if not p_mom_med:
            p_mom_med = Policy(
                id="01M4POL0000000000000000003",
                insurer="众安在线财产保险股份有限公司",
                product_name="众安尊享e生百万医疗2025",
                category="medical",
                term_type="one_year",
                premium_cents=48000,
                pay_mode="年交",
                sum_insured_cents=300000000,
                effective_date="2025-04-01",
                expiry_date="2027-04-01",
                waiting_days=30,
                status="active"
            )
            db.add(p_mom_med)
            db.flush()
            cov_m1 = Coverage(
                policy_id=p_mom_med.id,
                name="一般医疗保险金",
                kind="medical",
                limit_cents=300000000
            )
            cov_m2 = Coverage(
                policy_id=p_mom_med.id,
                name="重大疾病医疗保险金",
                kind="medical",
                limit_cents=300000000
            )
            db.add_all([cov_m1, cov_m2])

        # 4. Kid Policy
        p_kid_med = db.query(Policy).filter(Policy.product_name == "平安少儿住院万元护").first()
        if not p_kid_med:
            p_kid_med = Policy(
                id="01M4POL0000000000000000004",
                insurer="中国平安财产保险股份有限公司",
                product_name="平安少儿住院万元护",
                category="medical",
                term_type="one_year",
                premium_cents=38000,
                pay_mode="年交",
                sum_insured_cents=5000000,
                effective_date="2025-06-01",
                expiry_date="2027-06-01",
                waiting_days=30,
                status="active"
            )
            db.add(p_kid_med)
            db.flush()
            cov_k1 = Coverage(
                policy_id=p_kid_med.id,
                name="住院医疗保险金",
                kind="medical",
                limit_cents=5000000
            )
            db.add(cov_k1)

        db.commit()

        # Link Parties
        _ensure_party(db, p_dad_old.id, m_dad.id, "insured")
        _ensure_party(db, p_dad_new.id, m_dad.id, "insured")
        if p_dad_med:
            _ensure_party(db, p_dad_med.id, m_dad.id, "insured")
        if p_dad_ci:
            _ensure_party(db, p_dad_ci.id, m_dad.id, "insured")
        _ensure_party(db, p_mom_med.id, m_mom.id, "insured")
        _ensure_party(db, p_kid_med.id, m_kid.id, "insured")

        # 5. Set references
        ref_setting = db.query(AppSetting).filter(AppSetting.key == "coverage_references").first()
        if not ref_setting:
            ref_setting = AppSetting(
                key="coverage_references",
                value=json.dumps({"default": DEFAULT_REFERENCES}, ensure_ascii=False)
            )
            db.add(ref_setting)
        db.commit()

        # 6. Generate reminders
        generate_daily_reminders(db)

        print("M4 Demo Data Seeded Successfully!")
        print(f"  Dad ID: {m_dad.id}, Mom ID: {m_mom.id}, Kid ID: {m_kid.id}")
        print("  Dad has an intentional gap between 2025-03-01 and 2025-09-01 (184 days)!")

    finally:
        db.close()

def _ensure_party(db, policy_id: str, member_id: str, role: str):
    party = db.query(PolicyParty).filter(
        PolicyParty.policy_id == policy_id,
        PolicyParty.role == role
    ).first()
    if not party:
        party = PolicyParty(policy_id=policy_id, member_id=member_id, role=role)
        db.add(party)
    else:
        party.member_id = member_id
    db.commit()

if __name__ == "__main__":
    seed_m4_data()
