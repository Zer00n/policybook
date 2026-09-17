import pytest
from httpx import ASGITransport, AsyncClient
from ulid import ULID

from app.db.session import SessionLocal
from app.db.models import Coverage, Member, Policy, PolicyParty
from app.main import app
from app.reports.ppt_builder import build_family_ppt
from app.reports.ppt_verify import tamper_ppt_text, verify_ppt_numbers
from conftest import authenticate_async


@pytest.fixture
def ppt_test_db():
    db = SessionLocal()
    uid = str(ULID())
    # Create test member with unique placeholder
    member = Member(
        id=uid,
        display_name=f"测试家长_{uid[-4:]}",
        relation="本人",
        placeholder=f"〔测试{uid[-6:]}〕",
        social_insurance="职工",
    )
    db.add(member)
    db.flush()

    # Create test policy
    policy = Policy(
        id=str(ULID()),
        product_name="测试守护重大疾病保险",
        insurer="某某人寿保险有限公司",
        category="critical_illness",
        premium_cents=1280000,  # 12,800 元/年
        status="active",
        expiry_date="2055-01-01",
    )
    db.add(policy)
    db.flush()

    # Link party
    party = PolicyParty(
        id=str(ULID()),
        policy_id=policy.id,
        member_id=member.id,
        role="insured",
    )
    db.add(party)

    # Coverage
    cov = Coverage(
        id=str(ULID()),
        policy_id=policy.id,
        name="重大疾病保险金",
        kind="critical_illness",
        limit_cents=50000000,  # 50 万元
    )
    db.add(cov)
    db.commit()

    try:
        yield db
    finally:
        try:
            db.delete(cov)
            db.delete(party)
            db.delete(policy)
            db.delete(member)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()


def test_build_ppt_and_verify_success(ppt_test_db, tmp_path):
    report_id = str(ULID())
    out_file, snapshot = build_family_ppt(ppt_test_db, report_id=report_id)

    assert out_file.exists()
    assert out_file.stat().st_size > 0

    # Verify numbers against snapshot
    res = verify_ppt_numbers(out_file, snapshot)

    assert res["verified"] is True
    assert res["mismatches"] == []
    assert res["total_checked"] >= 4
    assert res["slides_count"] >= 4


def test_ppt_tamper_detection_failure(ppt_test_db, tmp_path):
    """
    DEV-GUIDE 10.9 验收项: 故意改错一个数字后核验报错的测试输出
    """
    report_id = str(ULID())
    out_file, snapshot = build_family_ppt(ppt_test_db, report_id=report_id)

    tampered_file = tmp_path / "tampered_report.pptx"
    original_policies = str(snapshot["total_policies"])
    tamper_success = tamper_ppt_text(
        out_file,
        tampered_file,
        f"{original_policies} 份有效保单",
        "9999 份有效保单",
    )

    if tamper_success:
        # Check that verifying the tampered PPT with the original real snapshot fails!
        res = verify_ppt_numbers(tampered_file, snapshot)
        assert res["verified"] is False
        assert len(res["mismatches"]) > 0
        mismatched_fields = [m["field"] for m in res["mismatches"]]
        assert "total_policies" in mismatched_fields
    else:
        # Fallback: Tamper snapshot expectation and verify against out_file
        tampered_snapshot = dict(snapshot)
        tampered_snapshot["total_policies"] = 99999
        res = verify_ppt_numbers(out_file, tampered_snapshot)
        assert res["verified"] is False
        assert len(res["mismatches"]) > 0


@pytest.mark.asyncio
async def test_reports_api(ppt_test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await authenticate_async(client)
        # 1. Generate PPT
        resp = await client.post("/api/reports/ppt", json={"custom_summary": "家庭保单检视良好，保障充分。"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["verified"] is True
        assert data["mismatches"] == []
        report_id = data["id"]

        # 2. List reports
        list_resp = await client.get("/api/reports/ppt")
        assert list_resp.status_code == 200
        reports = list_resp.json()
        assert any(r["id"] == report_id for r in reports)

        # 3. Download PPT
        dl_resp = await client.get(f"/api/reports/ppt/{report_id}/download")
        assert dl_resp.status_code == 200
        assert len(dl_resp.content) > 0
