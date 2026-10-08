import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, hash_token, is_password_hash, new_session_token, verify_password
from app.db.models import User, UserSession

log = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PHONE_RE = re.compile(r"^\d{10,15}$")
MIN_PASSWORD_LENGTH = 6


class AuthError(Exception):
    pass


def normalize_identity(identity: str) -> str:
    return identity.strip().lower()


def validate_identity(identity: str) -> None:
    if not (_EMAIL_RE.match(identity) or _PHONE_RE.match(identity)):
        raise AuthError("Введите корректный email или телефон")
    if len(identity) > 255:
        raise AuthError("Слишком длинный логин")


def validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AuthError(f"Пароль должен содержать минимум {MIN_PASSWORD_LENGTH} символов")
    if len(password) > 256:
        raise AuthError("Слишком длинный пароль")


async def create_user(
    db: AsyncSession, identity: str, password: str, *, is_admin: bool = False, **fields
) -> User:
    identity = normalize_identity(identity)
    validate_identity(identity)
    validate_password(password)
    exists = await db.scalar(select(User.id).where(User.email == identity).limit(1))
    if exists:
        raise AuthError("Пользователь с таким логином уже существует")
    user = User(email=identity, password=await asyncio.to_thread(hash_password, password), is_admin=is_admin, **fields)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    log.info("User registered: id=%s", user.id)
    return user


async def authenticate(db: AsyncSession, identity: str, password: str) -> User | None:
    identity = normalize_identity(identity)
    # В старой БД email не был уникальным — проверяем все совпадения.
    candidates = (await db.scalars(select(User).where(User.email == identity).order_by(User.id))).all()
    for user in candidates:
        if await asyncio.to_thread(verify_password, password, user.password):
            if not is_password_hash(user.password):
                user.password = await asyncio.to_thread(hash_password, password)
                await db.commit()
                log.info("Legacy plaintext password upgraded to hash: user id=%s", user.id)
            return user
    return None


async def set_password(db: AsyncSession, user: User, password: str) -> None:
    validate_password(password)
    user.password = await asyncio.to_thread(hash_password, password)
    await db.commit()


async def create_session(db: AsyncSession, user: User, ttl_days: int) -> str:
    token = new_session_token()
    now = datetime.now(timezone.utc)
    db.add(UserSession(token_hash=hash_token(token), user_id=user.id, created_at=now, expires_at=now + timedelta(days=ttl_days)))
    await db.commit()
    return token


async def get_user_by_token(db: AsyncSession, token: str | None) -> User | None:
    if not token or len(token) > 128:
        return None
    now = datetime.now(timezone.utc)
    row = await db.execute(
        select(User)
        .join(UserSession, UserSession.user_id == User.id)
        .where(UserSession.token_hash == hash_token(token), UserSession.expires_at > now)
    )
    return row.scalar_one_or_none()


async def delete_session(db: AsyncSession, token: str | None) -> None:
    if not token:
        return
    await db.execute(delete(UserSession).where(UserSession.token_hash == hash_token(token)))
    await db.commit()


async def delete_expired_sessions(db: AsyncSession) -> int:
    result = await db.execute(delete(UserSession).where(UserSession.expires_at <= datetime.now(timezone.utc)))
    await db.commit()
    return result.rowcount or 0
