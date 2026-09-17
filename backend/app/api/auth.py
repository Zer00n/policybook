from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.security import (
    SESSION_COOKIE_NAME,
    SESSION_TTL_SECONDS,
    clear_failed_attempts,
    create_session_token,
    hash_password,
    is_rate_limited,
    is_session_valid,
    record_failed_attempt,
    verify_password,
)
from app.db.models import AppSetting
from app.db.session import get_db
from app.settings import settings

router = APIRouter(prefix="/auth", tags=["auth"])

PASSWORD_SETTING_KEY = "family_password_hash"
MIN_PASSWORD_LENGTH = 4


class PasswordPayload(BaseModel):
    password: str


def _get_stored_hash(db: Session) -> str | None:
    setting = db.query(AppSetting).filter(AppSetting.key == PASSWORD_SETTING_KEY).first()
    return setting.value if setting else None


def _is_configured(db: Session) -> bool:
    return bool(_get_stored_hash(db)) or bool(settings.family_password.strip())


def _set_session_cookie(response: Response) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=create_session_token(),
        httponly=True,
        samesite="lax",
        secure=False,  # 纯内网 HTTP 部署，不映射公网（见 DEV-GUIDE §12.4）
        max_age=SESSION_TTL_SECONDS,
        path="/",
    )


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.get("/status")
def get_auth_status(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(SESSION_COOKIE_NAME)
    return {
        "configured": _is_configured(db),
        "authenticated": is_session_valid(token),
    }


@router.post("/setup")
def setup_password(payload: PasswordPayload, response: Response, db: Session = Depends(get_db)):
    if _is_configured(db):
        raise HTTPException(status_code=409, detail="家庭密码已设置，请使用登录接口")
    if len(payload.password.strip()) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=422, detail=f"密码长度至少 {MIN_PASSWORD_LENGTH} 位")

    setting = AppSetting(key=PASSWORD_SETTING_KEY, value=hash_password(payload.password))
    db.add(setting)
    db.commit()

    _set_session_cookie(response)
    return {"ok": True}


@router.post("/login")
def login(payload: PasswordPayload, request: Request, response: Response, db: Session = Depends(get_db)):
    client_key = _client_key(request)
    if is_rate_limited(client_key):
        raise HTTPException(status_code=429, detail="失败次数过多，请稍后再试")

    stored_hash = _get_stored_hash(db)

    if stored_hash:
        ok = verify_password(payload.password, stored_hash)
    elif settings.family_password.strip():
        # 环境变量作为一次性引导密码，登录成功后落库为哈希，此后不再读取环境变量
        ok = payload.password == settings.family_password.strip()
        if ok:
            db.add(AppSetting(key=PASSWORD_SETTING_KEY, value=hash_password(payload.password)))
            db.commit()
    else:
        raise HTTPException(status_code=409, detail="尚未设置家庭密码，请先完成初始设置")

    if not ok:
        record_failed_attempt(client_key)
        raise HTTPException(status_code=401, detail="密码错误")

    clear_failed_attempts(client_key)
    _set_session_cookie(response)
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return {"ok": True}
