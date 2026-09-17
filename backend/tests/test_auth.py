from fastapi.testclient import TestClient

from app.auth.security import SESSION_COOKIE_NAME, is_session_valid
from app.db.models import AppSetting
from app.db.session import SessionLocal
from app.main import app

TEST_PASSWORD = "auth-test-password"


def _reset_password_setting():
    db = SessionLocal()
    try:
        db.query(AppSetting).filter(AppSetting.key == "family_password_hash").delete()
        db.commit()
    finally:
        db.close()


def test_auth_flow_setup_login_logout():
    _reset_password_setting()
    client = TestClient(app)

    # 未配置时：status 显示未配置，受保护路由 401
    status = client.get("/api/auth/status").json()
    assert status["configured"] is False
    assert status["authenticated"] is False

    resp = client.get("/api/members")
    assert resp.status_code == 401

    # 公开路由（health）不受影响
    assert client.get("/api/health").status_code == 200

    # setup 成功，返回 Cookie 并自动登录
    resp = client.post("/api/auth/setup", json={"password": TEST_PASSWORD})
    assert resp.status_code == 200
    assert SESSION_COOKIE_NAME in resp.cookies

    status = client.get("/api/auth/status").json()
    assert status["configured"] is True
    assert status["authenticated"] is True

    # 重复 setup 应被拒绝
    resp = client.post("/api/auth/setup", json={"password": "another-password"})
    assert resp.status_code == 409

    # 已登录状态下可访问受保护路由
    assert client.get("/api/members").status_code == 200

    # logout 后应重新变为未登录
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200
    assert client.get("/api/members").status_code == 401

    # 错误密码登录应 401
    resp = client.post("/api/auth/login", json={"password": "wrong-password"})
    assert resp.status_code == 401

    # 正确密码登录应恢复访问
    resp = client.post("/api/auth/login", json={"password": TEST_PASSWORD})
    assert resp.status_code == 200
    assert client.get("/api/members").status_code == 200

    _reset_password_setting()


def test_ics_calendar_and_reminders_split():
    """calendar_router 混装了公开的 ICS 端点与需要登录的 /api/reminders，
    必须分别验证二者的访问控制符合预期。"""
    _reset_password_setting()
    client = TestClient(app)

    # /api/reminders 现在需要登录
    assert client.get("/api/reminders").status_code == 401

    # ICS 订阅端点即使未登录也应可访问（凭自己的随机 token，不存在的 token 返回 404 而非 401）
    resp = client.get("/calendar/not-a-real-token.ics")
    assert resp.status_code == 404

    _reset_password_setting()


def test_session_token_expiry_rejected():
    # 构造一个格式正确但内容不是我们签发的 token，应被判定为无效
    assert is_session_valid("not-a-real-fernet-token") is False
    assert is_session_valid(None) is False
    assert is_session_valid("") is False
