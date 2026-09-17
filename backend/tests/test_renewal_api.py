import pytest
from httpx import ASGITransport, AsyncClient
from ulid import ULID

from app.main import app
from app.db.session import SessionLocal
from app.db.models import Coverage, Document, Policy
from conftest import authenticate_async


@pytest.fixture
def test_accident_policy():
    db = SessionLocal()
    doc = Document(
        id=str(ULID()),
        sha256="test_sha256_api_renewal",
        original_name="test_api_accident.pdf",
        mime="application/pdf",
    )
    db.add(doc)
    db.flush()

    policy = Policy(
        id=str(ULID()),
        document_id=doc.id,
        product_name="平安安心意外险（API测试）",
        insurer="中国平安财产保险股份有限公司",
        category="accident",
        premium_cents=29900,
    )
    db.add(policy)
    db.flush()

    cov1 = Coverage(
        id=str(ULID()),
        policy_id=policy.id,
        name="意外身故及伤残",
        kind="death",
        limit_cents=100000000,
    )
    cov2 = Coverage(
        id=str(ULID()),
        policy_id=policy.id,
        name="意外医疗",
        kind="accident_medical",
        limit_cents=5000000,
        deductible_cents=0,
        ratio_with_si=1000,
    )
    db.add_all([cov1, cov2])
    db.commit()
    policy_id = policy.id
    db.close()
    return policy_id


@pytest.mark.asyncio
async def test_renewal_api_full_flow(test_accident_policy):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await authenticate_async(client)
        # 1. Create renewal session
        resp = await client.post("/api/renewal/sessions", json={"policy_id": test_accident_policy})
        assert resp.status_code == 200
        data = resp.json()
        session_id = data["id"]
        assert data["state"] == "COLLECT_NEEDS"
        assert "平安安心意外险" in data["messages"][0]["content"]

        # 2. List sessions
        list_resp = await client.get("/api/renewal/sessions")
        assert list_resp.status_code == 200
        sessions = list_resp.json()
        assert any(s["id"] == session_id for s in sessions)

        # 3. User provides statement: advance to ASK_USER
        msg_resp = await client.post(
            f"/api/renewal/sessions/{session_id}/messages",
            json={"content": "今年经常加班，希望有猝死保障，经常坐高铁出差"},
        )
        assert msg_resp.status_code == 200
        msg_data = msg_resp.json()
        assert msg_data["state"] == "ASK_USER"
        assert len(msg_data["current_questions"]) >= 1

        # 4. User replies with answers
        dim_key = msg_data["current_questions"][0]["dimension"]
        ans_resp = await client.post(
            f"/api/renewal/sessions/{session_id}/messages",
            json={"content": "已选择", "answers": {dim_key: "需要猝死保障"}, "skip": True},
        )
        assert ans_resp.status_code == 200
        final_data = ans_resp.json()
        assert final_data["state"] == "END"
        assert final_data["report"] is not None
        assert final_data["report"]["status"] == "complete"
        assert len(final_data["report"]["comparison_matrix"]["products"]) >= 2

        # 5. Fetch standalone report
        rep_resp = await client.get(f"/api/renewal/sessions/{session_id}/report")
        assert rep_resp.status_code == 200
        report = rep_resp.json()
        assert report["status"] == "complete"
        assert len(report["customer_service_questions"]) >= 1
