"""家庭密码登录：口令哈希、会话令牌签发/校验、简单的暴力破解限流。

会话令牌直接复用 app.db.crypto 里已有的 Fernet 实例（密钥来自 APP_SECRET），
Fernet 自带防篡改与 ttl 过期校验，因此不需要额外的 session 表或新依赖。
"""
import hashlib
import hmac
import os
import time

from app.db.crypto import get_fernet

SESSION_COOKIE_NAME = "policybook_session"
SESSION_TTL_SECONDS = 7 * 24 * 3600  # 7 天

_SESSION_PAYLOAD = b"authenticated"

_PBKDF2_ITERATIONS = 200_000

# 简单的内存暴力破解限流：同一来源 IP 在窗口期内失败次数过多则锁定
_RATE_LIMIT_WINDOW_SECONDS = 15 * 60
_RATE_LIMIT_MAX_ATTEMPTS = 10
_failed_attempts: dict[str, list[float]] = {}


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"{salt.hex()}:{_PBKDF2_ITERATIONS}:{digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, iterations_str, hash_hex = stored.split(":")
        salt = bytes.fromhex(salt_hex)
        iterations = int(iterations_str)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def create_session_token() -> str:
    return get_fernet().encrypt(_SESSION_PAYLOAD).decode("utf-8")


def is_session_valid(token: str | None) -> bool:
    if not token:
        return False
    try:
        payload = get_fernet().decrypt(token.encode("utf-8"), ttl=SESSION_TTL_SECONDS)
    except Exception:
        return False
    return payload == _SESSION_PAYLOAD


def is_rate_limited(client_key: str) -> bool:
    now = time.time()
    attempts = _failed_attempts.get(client_key, [])
    attempts = [t for t in attempts if now - t < _RATE_LIMIT_WINDOW_SECONDS]
    _failed_attempts[client_key] = attempts
    return len(attempts) >= _RATE_LIMIT_MAX_ATTEMPTS


def record_failed_attempt(client_key: str) -> None:
    _failed_attempts.setdefault(client_key, []).append(time.time())


def clear_failed_attempts(client_key: str) -> None:
    _failed_attempts.pop(client_key, None)
