import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_model_test_endpoint():
    response = client.post("/api/settings/models/test", json={"model_key": "evolving"})
    assert response.status_code == 200
    data = response.json()
    assert "ok" in data
    assert "model_id" in data
    assert "display_name" in data
    # When ARK_API_KEY is not set in env, it should gracefully return ok=False with explanation
    if not data["ok"]:
        assert "ARK_API_KEY" in data.get("error", "") or "未配置" in data.get("error", "")


def test_model_test_fallback():
    response = client.post("/api/settings/models/test", json={})
    assert response.status_code == 200
    data = response.json()
    assert "model_id" in data
