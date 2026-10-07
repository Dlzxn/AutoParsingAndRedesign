from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service
from app.config import get_settings
from app.db.base import get_session
from app.db.models import User

DbSession = Annotated[AsyncSession, Depends(get_session)]


class LoginRequired(Exception):
    """Для HTML-страниц: неавторизованного пользователя перенаправляем на /login."""

    def __init__(self, next_url: str) -> None:
        self.next_url = next_url


async def get_optional_user(request: Request, db: DbSession) -> User | None:
    if hasattr(request.state, "user"):  # кэш на время запроса
        return request.state.user
    token = request.cookies.get(get_settings().session_cookie_name)
    user = await service.get_user_by_token(db, token)
    request.state.user = user
    return user


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


async def get_current_user(user: OptionalUser) -> User:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Требуется авторизация")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_feature_user(user: OptionalUser) -> User | None:
    """Пользователь для платных функций: обязателен, если включено AUTH_REQUIRED."""
    if user is None and get_settings().auth_required:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Войдите в аккаунт, чтобы пользоваться сервисом")
    return user


FeatureUser = Annotated[User | None, Depends(get_feature_user)]


async def get_admin_user(user: OptionalUser) -> User:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Требуется авторизация")
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступ только для администраторов")
    return user


AdminUser = Annotated[User, Depends(get_admin_user)]


async def require_page_user(request: Request, user: OptionalUser) -> User | None:
    if user is None and get_settings().auth_required:
        raise LoginRequired(request.url.path)
    return user


PageUser = Annotated[User | None, Depends(require_page_user)]
