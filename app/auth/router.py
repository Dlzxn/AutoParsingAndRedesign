from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.auth import service
from app.auth.deps import DbSession, OptionalUser
from app.config import get_settings
from app.core.rate_limit import RateLimiter
from app.web.templating import render

router = APIRouter(tags=["auth"])

login_limiter = RateLimiter(get_settings().login_rate_limit)


class Credentials(BaseModel):
    identity: str = Field(max_length=255)
    password: str = Field(max_length=256)


def _client_ip(request: Request) -> str:
    # За reverse proxy реальный IP подставляет uvicorn (--proxy-headers); сам заголовок
    # X-Forwarded-For не читаем — клиент может его подделать и обойти ограничение попыток.
    return request.client.host if request.client else "unknown"


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def _safe_next(next_url: str | None) -> str:
    # Разрешаем только относительные пути внутри сайта (защита от open redirect)
    if next_url and next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return "/"


@router.get("/login", include_in_schema=False)
async def login_page(request: Request, user: OptionalUser, next: str | None = None):
    if user is not None:
        return RedirectResponse(_safe_next(next), status.HTTP_303_SEE_OTHER)
    return render(request, "login.html", next_url=_safe_next(next))


@router.get("/registration", include_in_schema=False)
async def registration_page(request: Request, user: OptionalUser, next: str | None = None):
    if user is not None:
        return RedirectResponse(_safe_next(next), status.HTTP_303_SEE_OTHER)
    return render(request, "registration.html", next_url=_safe_next(next))


@router.get("/register", include_in_schema=False)
async def register_alias():
    return RedirectResponse("/registration", status.HTTP_301_MOVED_PERMANENTLY)


@router.get("/logout", include_in_schema=False)
async def logout(request: Request, db: DbSession):
    settings = get_settings()
    await service.delete_session(db, request.cookies.get(settings.session_cookie_name))
    response = RedirectResponse("/", status.HTTP_303_SEE_OTHER)
    response.delete_cookie(settings.session_cookie_name, path="/")
    return response


@router.post("/api/login")
async def api_login(data: Credentials, request: Request, response: Response, db: DbSession):
    login_limiter.check(f"login:{_client_ip(request)}", "Слишком много попыток входа, попробуйте через минуту")
    user = await service.authenticate(db, data.identity, data.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный логин или пароль")
    _set_session_cookie(response, await service.create_session(db, user, get_settings().session_ttl_days))
    return {"status": "success"}


@router.post("/api/registration", status_code=status.HTTP_201_CREATED)
async def api_registration(data: Credentials, request: Request, response: Response, db: DbSession):
    login_limiter.check(f"register:{_client_ip(request)}", "Слишком много попыток, попробуйте через минуту")
    try:
        user = await service.create_user(db, data.identity, data.password)
    except service.AuthError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    _set_session_cookie(response, await service.create_session(db, user, get_settings().session_ttl_days))
    return {"status": "success"}
