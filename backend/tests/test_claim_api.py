from datetime import date
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import get_db, engine, Base
from app.db.models import Coverage, Document, Member, Policy, PolicyParty
from app.db.crypto import encrypt_str


@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    session = Session(bind=engine)
    try:
        yield session
    finally:
        session.close()


def test_claim_simulate_endpoint_success(db_session: Session):
    client = TestClient(app)

    # 1. 建立测试成员
    member = db_session.query(Member).filter(Member.id == "mem_claim_1").first()
    if not member:
        member = Member(
            id="mem_claim_1",
            display_name="张三",
            relation="本人",
            placeholder="〔测试理赔成员〕",
            social_insurance="职工",
        )
        member.real_name_enc = encrypt_str("测试张三")
        db_session.add(member)

    # 2. 建立测试保单与被保人关联
    pol = db_session.query(Policy).filter(Policy.id == "pol_claim_1").first()
    if not pol:
        pol = Policy(
            id="pol_claim_1",
            insurer="某健康人寿",
            product_name="安心医疗健康保障计划",
            category="medical",
            effective_date="2025-01-01",
            waiting_days=30,
            status="active",
        )
        db_session.add(pol)

    party = db_session.query(PolicyParty).filter(PolicyParty.id == "party_claim_1").first()
    if not party:
        party = PolicyParty(
            id="party_claim_1",
            policy_id="pol_claim_1",
            member_id=member.id,
            role="insured",
        )
        db_session.add(party)
    else:
        party.member_id = member.id

    # 3. 建立责任项：住院医疗费用
    cov = db_session.query(Coverage).filter(Coverage.id == "cov_claim_1").first()
    if not cov:
        cov = Coverage(
            id="cov_claim_1",
            policy_id="pol_claim_1",
            name="住院医疗费用保险金",
            kind="medical",
            limit_cents=2000000,      # 20,000 元限额
            deductible_cents=10000,   # 100 元免赔
            ratio_with_si=1000,       # 100%
            ratio_without_si=800,     # 80%
        )
        db_session.add(cov)
    db_session.commit()

    # 4. 发起理赔模拟请求
    payload = {
        "member_id": member.id,
        "event_kind": "illness",
        "event_date": "2025-05-20",  # 超过 30 天等待期
        "description": "因急性阑尾炎住院行腹腔镜微创切除手术，在公立三甲医院住院 4 天",
        "total_cost": 8500.0,
        "si_covered_cost": 6000.0,
        "si_reimbursed": 4500.0,
        "has_si": True,
        "city": "北京",
    }

    resp = client.post("/api/claim/simulate", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["member_id"] == member.id
    assert len(data["waterfall_steps"]) >= 2
    # 步骤 0: 总医疗费用 8500
    assert data["waterfall_steps"][0]["amount_low"] == 8500.0
    # 步骤 1: 社保报销 4500
    assert data["waterfall_steps"][1]["amount_low"] == 4500.0
    # 剩余自付区间在合理范围内
    assert data["out_of_pocket_low"] <= 4000.0
    assert isinstance(data["materials_needed"], list)
    assert isinstance(data["confirm_with_insurer"], list)


def test_claim_simulate_member_not_found(db_session: Session):
    client = TestClient(app)
    resp = client.post(
        "/api/claim/simulate",
        json={
            "member_id": "non_existent_id",
            "event_kind": "illness",
            "event_date": "2025-05-20",
            "description": "测试",
            "total_cost": 1000.0,
        },
    )
    assert resp.status_code == 404
