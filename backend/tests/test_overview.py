from datetime import date
from starlette.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.db.models import Member, Policy, PolicyParty
from conftest import authenticate

client = TestClient(app)
authenticate(client)


def test_overview_api_and_timeline():
    # 1. Ensure test member exists
    db = SessionLocal()
    try:
        member = db.query(Member).filter(Member.relation == "本人").first() or db.query(Member).first()
        if not member:
            member = Member(
                id="01TESTMEMBER00000000000001",
                display_name="测试成员A",
                relation="本人",
                placeholder="〔成员A〕",
                color="#2A8F82"
            )
            db.add(member)
            db.commit()

        member_id = member.id

        # 2. Ensure test policies exist
        p_old = db.query(Policy).filter(Policy.product_name == "测试空档保单A").first()
        if not p_old:
            p_old = Policy(
                id="01TESTGAP000000000000001",
                insurer="平安保险",
                product_name="测试空档保单A",
                category="accident",
                effective_date="2023-01-01",
                expiry_date="2024-01-01",
                waiting_days=30,
                premium_cents=36000,
                pay_mode="年交",
                status="lapsed"
            )
            db.add(p_old)
            db.commit()

        p_new = db.query(Policy).filter(Policy.product_name == "测试空档保单B").first()
        if not p_new:
            p_new = Policy(
                id="01TESTGAP000000000000002",
                insurer="平安保险",
                product_name="测试空档保单B",
                category="accident",
                effective_date="2024-06-01",
                expiry_date="2027-06-01",
                waiting_days=30,
                premium_cents=45000,
                pay_mode="年交",
                status="active"
            )
            db.add(p_new)
            db.commit()

        # 3. Ensure party links exist for this member
        for p in [p_old, p_new]:
            party = db.query(PolicyParty).filter(
                PolicyParty.policy_id == p.id,
                PolicyParty.member_id == member_id,
                PolicyParty.role == "insured"
            ).first()
            if not party:
                db.add(PolicyParty(policy_id=p.id, member_id=member_id, role="insured"))
        db.commit()
    finally:
        db.close()

    # Call GET /api/overview
    response = client.get("/api/overview")
    assert response.status_code == 200
    data = response.json()

    assert "metrics" in data
    assert "timeline" in data
    assert "todos" in data
    assert "today" in data

    metrics = data["metrics"]
    assert metrics["active_policy_count"] >= 1
    assert metrics["total_annual_premium_yuan"] >= 0.0

    # Verify timeline bands and gap detection
    m_timeline = next((m for m in data["timeline"] if m["member_id"] == member_id), None)
    assert m_timeline is not None
    assert len(m_timeline["bands"]) >= 2

    # Verify waiting period segment exists
    band_b = next((b for b in m_timeline["bands"] if b["product_name"] == "测试空档保单B"), None)
    assert band_b is not None
    assert any(s["segment_type"] == "waiting" for s in band_b["segments"])
    assert any(s["segment_type"] == "effective" for s in band_b["segments"])

    # Verify gap was detected between 2024-01-01 and 2024-06-01
    assert m_timeline["has_gap"] is True
    gap_seg = next((g for g in m_timeline["gap_segments"] if g["start_date"] == "2024-01-01"), None)
    assert gap_seg is not None
    assert gap_seg["end_date"] == "2024-06-01"
    assert "空档" in gap_seg["label"]
