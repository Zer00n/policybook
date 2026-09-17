import pytest
from fastapi.testclient import TestClient
from app.main import app
from conftest import authenticate

client = TestClient(app)
authenticate(client)


def test_model_test_endpoint():
    response = client.post("/api/settings/models/test", json={"model_key": "evolving"})
    assert response.status_code == 200
    data = response.json()
    assert "ok" in data
    assert "model_id" in data
    assert "display_name" in data
    if not data["ok"]:
        assert data.get("error") is not None and len(data.get("error")) > 0



def test_model_test_fallback():
    response = client.post("/api/settings/models/test", json={})
    assert response.status_code == 200
    data = response.json()
    assert "model_id" in data
