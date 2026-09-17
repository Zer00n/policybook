"""测试专用的鉴权辅助：所有测试共用同一个 SQLite 文件（app/db/session.py），
家庭密码一旦被某个测试文件 setup 过，后续测试只能用同一套密码登录，
因此这里的 authenticate 必须是幂等的（先看有没有配置，未配置才 setup，否则直接 login）。
"""
TEST_PASSWORD = "pytest-only-password"


def authenticate(client) -> None:
    """供同步 TestClient 使用。"""
    status = client.get("/api/auth/status").json()
    if not status.get("configured"):
        resp = client.post("/api/auth/setup", json={"password": TEST_PASSWORD})
        assert resp.status_code == 200, resp.text
    elif not status.get("authenticated"):
        resp = client.post("/api/auth/login", json={"password": TEST_PASSWORD})
        assert resp.status_code == 200, resp.text


async def authenticate_async(client) -> None:
    """供异步 httpx.AsyncClient 使用。"""
    status_resp = await client.get("/api/auth/status")
    status = status_resp.json()
    if not status.get("configured"):
        resp = await client.post("/api/auth/setup", json={"password": TEST_PASSWORD})
        assert resp.status_code == 200, resp.text
    elif not status.get("authenticated"):
        resp = await client.post("/api/auth/login", json={"password": TEST_PASSWORD})
        assert resp.status_code == 200, resp.text
