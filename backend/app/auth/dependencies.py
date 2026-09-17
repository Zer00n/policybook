from fastapi import HTTPException, Request

from app.auth.security import SESSION_COOKIE_NAME, is_session_valid


def require_login(request: Request) -> None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not is_session_valid(token):
        raise HTTPException(status_code=401, detail="未登录或会话已过期，请重新登录")
