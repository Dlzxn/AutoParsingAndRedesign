"""Хеширование паролей и токенов сессий (только стандартная библиотека)."""
import base64
import hashlib
import hmac
import secrets

_SCHEME = "scrypt"
_N, _R, _P = 2**14, 8, 1
_DKLEN = 32


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN)
    return f"{_SCHEME}${_N}${_R}${_P}${_b64(salt)}${_b64(digest)}"


def is_password_hash(value: str) -> bool:
    return value.startswith(f"{_SCHEME}$")


def verify_password(password: str, stored: str) -> bool:
    """Проверяет пароль. Поддерживает устаревшие записи с паролем открытым текстом."""
    if not stored:
        return False
    if not is_password_hash(stored):
        return hmac.compare_digest(password.encode("utf-8"), stored.encode("utf-8"))
    try:
        _, n, r, p, salt_b64, digest_b64 = stored.split("$")
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
