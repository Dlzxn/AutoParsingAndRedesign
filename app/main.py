import asyncio
import logging
import ssl
import time
import urllib.parse
from contextlib import asynccontextmanager

import aiohttp
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.admin import router as admin_router
from app.auth import router as auth_router
from app.auth.deps import LoginRequired
from app.config import Settings, get_settings
from app.core.errors import humanize_validation_error
from app.db.base import dispose_engine, get_engine, init_engine, session_factory
from app.db.migrate import upgrade_to_head
from app.db.seed import seed_defaults
from app.editor import router as editor_router
from app.editor.service import EditorService
from app.editor.worker import RenderQueue
from app.history import router as history_router
from app.logging_config import setup_logging
from app.maintenance import maintenance_loop
from app.media.ffmpeg import MediaError, resolve_binary
from app.media.service import MediaService
from app.media.storage import Storage
from app.pages import router as pages_router
from app.search import router as search_router
from app.search.factory import build_search_service
from app.users import router as users_router
from app.web.templating import STATIC_DIR, render

log = logging.getLogger("app")


def _check_binaries(settings: Settings) -> None:
    for binary in (settings.ffmpeg_path, settings.ffprobe_path):
        try:
            resolve_binary(binary)
        except MediaError as exc:
            log.error("%s Редактор и скачивание работать не будут.", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    engine = init_engine(settings.resolved_database_url, settings.db_echo)
    await upgrade_to_head(engine)
    async with session_factory()() as db:
        await seed_defaults(db)
    _check_binaries(settings)

    storage = Storage(settings.storage_dir)
    media = MediaService(settings, storage)
    render_queue = RenderQueue(settings, storage)
    http = aiohttp.ClientSession(
        # Явный стандартный SSL-контекст: с контекстом aiohttp по умолчанию api.tumblr.com рвёт соединение
        connector=aiohttp.TCPConnector(limit=100, ttl_dns_cache=300, ssl=ssl.create_default_context()),
        headers={"User-Agent": "Mozilla/5.0 (compatible; AutoParsing/2.0)"},
    )
    app.state.storage = storage
    app.state.media = media
    app.state.render_queue = render_queue
    app.state.editor = EditorService(media, storage, render_queue)
    app.state.search = build_search_service(settings, http)

    await render_queue.start()
    maintenance = asyncio.create_task(maintenance_loop(settings, storage)) if settings.environment != "test" else None
    log.info("Application started (env=%s)", settings.environment)
    try:
        yield
    finally:
        if maintenance:
            maintenance.cancel()
        await render_queue.stop()
        await app.state.search.close()
        await http.close()
        await dispose_engine()
        log.info("Application stopped")


def _wants_json(request: Request) -> bool:
    return request.url.path.startswith("/api/") or "application/json" in request.headers.get("accept", "")


def _install_handlers(app: FastAPI) -> None:
    @app.exception_handler(LoginRequired)
    async def login_required(request: Request, exc: LoginRequired):
        return RedirectResponse(f"/login?next={urllib.parse.quote(exc.next_url)}", status.HTTP_303_SEE_OTHER)

    @app.exception_handler(MediaError)
    async def media_error(request: Request, exc: MediaError):
        return JSONResponse({"detail": str(exc)}, status.HTTP_400_BAD_REQUEST)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        message = humanize_validation_error(errors[0]) if errors else "Некорректные данные запроса"
        return JSONResponse({"detail": message}, status.HTTP_422_UNPROCESSABLE_ENTITY)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        if _wants_json(request):
            return JSONResponse({"detail": exc.detail}, exc.status_code, headers=getattr(exc, "headers", None))
        template = "NotFoundPage.html" if exc.status_code == 404 else "InternetErrorPage.html"
        return render(request, template, status_code=exc.status_code, error=exc.detail)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        if _wants_json(request):
            return JSONResponse({"detail": "Внутренняя ошибка сервера"}, status.HTTP_500_INTERNAL_SERVER_ERROR)
        return render(request, "InternetErrorPage.html", status_code=500, error="Внутренняя ошибка сервера")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings)
    app = FastAPI(
        title="AutoParsing",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.debug else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.debug else None,
    )
    app.state.settings = settings

    @app.middleware("http")
    async def limit_upload_size(request: Request, call_next):
        """Отклоняет слишком большие загрузки по Content-Length до чтения тела запроса."""
        if request.method == "POST" and request.url.path.startswith("/api/editor/"):
            length = request.headers.get("content-length", "")
            limit = settings.max_upload_mb * 1024 * 1024 + 10 * 1024 * 1024  # + запас на логотип/музыку и поля формы
            if length.isdigit() and int(length) > limit:
                return JSONResponse({"detail": f"Файл слишком большой (максимум {settings.max_upload_mb} МБ)"},
                                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        return await call_next(request)

    @app.middleware("http")
    async def timing_and_headers(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        elapsed = (time.perf_counter() - started) * 1000
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if request.url.path.startswith("/api/"):
            log.info("%s %s -> %s (%.0f ms)", request.method, request.url.path, response.status_code, elapsed)
        return response

    _install_handlers(app)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    for module in (auth_router, users_router, search_router, history_router, editor_router, pages_router):
        app.include_router(module.router)
    app.include_router(admin_router.pages)
    app.include_router(admin_router.api)

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return RedirectResponse("/static/img/logo.svg", status.HTTP_301_MOVED_PERMANENTLY)

    @app.get("/healthz", include_in_schema=False)
    async def healthz():
        checks = {"db": False, "ffmpeg": False}
        try:
            async with get_engine().connect() as conn:
                await conn.execute(text("SELECT 1"))
            checks["db"] = True
        except Exception:
            log.exception("Health check: database unavailable")
        try:
            resolve_binary(settings.ffmpeg_path)
            checks["ffmpeg"] = True
        except MediaError:
            pass
        healthy = all(checks.values())
        return JSONResponse({"status": "ok" if healthy else "degraded", **checks},
                            status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE)

    return app
