import pytest
from fastapi.testclient import TestClient
from app.main import app
from conftest import authenticate

client = TestClient(app)


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "policybook"
    assert "version" in data
    assert "timestamp" in data


def test_settings_summary():
    authenticate(client)
    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert len(data["models"]) >= 2
    assert "eval_mode" in data
