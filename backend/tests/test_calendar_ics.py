from starlette.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_calendar_token_management():
    # 1. Get calendar settings
    res = client.get("/api/settings/calendar")
    assert res.status_code == 200
    data = res.json()
    token = data["token"]
    assert len(token) > 10
    assert data["ics_url"] == f"/api/calendar/{token}.ics"

    # 2. Access with valid token
    res_ics = client.get(f"/calendar/{token}.ics")
    assert res_ics.status_code == 200
    assert "text/calendar" in res_ics.headers.get("content-type", "")
    ics_text = res_ics.text
    assert "BEGIN:VCALENDAR" in ics_text
    assert "PRODID:-//PolicyBook//CN" in ics_text
    assert "VERSION:2.0" in ics_text
    assert "END:VCALENDAR" in ics_text

    # Also test /api/calendar/{token}.ics
    res_ics_api = client.get(f"/api/calendar/{token}.ics")
    assert res_ics_api.status_code == 200
    assert "BEGIN:VCALENDAR" in res_ics_api.text

    # 3. Access with invalid token returns 404 (Red Line 11)
    res_bad = client.get("/calendar/invalid_token_123.ics")
    assert res_bad.status_code == 404

    # 4. Reset token
    res_reset = client.post("/api/settings/calendar/reset-token")
    assert res_reset.status_code == 200
    new_token = res_reset.json()["token"]
    assert new_token != token

    # 5. Old token should now be rejected
    res_old = client.get(f"/calendar/{token}.ics")
    assert res_old.status_code == 404

    # 6. New token should work
    res_new = client.get(f"/calendar/{new_token}.ics")
    assert res_new.status_code == 200


def test_reminders_list_and_dismiss():
    res = client.get("/api/reminders")
    assert res.status_code == 200
    reminders = res.json()
    assert isinstance(reminders, list)

    if len(reminders) > 0:
        target_id = reminders[0]["id"]
        res_dismiss = client.patch(f"/api/reminders/{target_id}/dismiss")
        assert res_dismiss.status_code == 200
        assert res_dismiss.json()["status"] == "dismissed"
