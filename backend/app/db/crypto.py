import base64
from cryptography.fernet import Fernet
from app.settings import settings

_fernet_instance: Fernet | None = None


def get_fernet() -> Fernet:
    global _fernet_instance
    if _fernet_instance is None:
        key = settings.app_secret
        if not key:
            raise ValueError("APP_SECRET is not configured in settings")
        try:
            # 确保密钥是 32 字节 base64url 格式
            key_bytes = key.encode("utf-8")
            _fernet_instance = Fernet(key_bytes)
        except Exception:
            # 若不是标准 base64，按 sha256 派生 32 字节 base64url key
            import hashlib
            derived = base64.urlsafe_b64encode(hashlib.sha256(key.encode("utf-8")).digest())
            _fernet_instance = Fernet(derived)
    return _fernet_instance


def encrypt_str(plain_text: str | None) -> str | None:
    if plain_text is None:
        return None
    f = get_fernet()
    return f.encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_str(cipher_text: str | None) -> str | None:
    if not cipher_text:
        return None
    try:
        f = get_fernet()
        return f.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
    except Exception:
        return None
