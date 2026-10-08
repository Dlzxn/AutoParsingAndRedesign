import os
import shutil
import subprocess
import tempfile
from pathlib import Path

# Окружение задаётся до импорта приложения: часть настроек читается при импорте модулей.
_TMP = Path(tempfile.mkdtemp(prefix="autoparsing-tests-"))
os.environ.update(
    {
        "APP_ENV_FILE": "",
        "ENVIRONMENT": "test",
        "DEBUG": "false",
        "VAR_DIR": str(_TMP / "var"),
        "DATABASE_URL": "",
        "AUTH_REQUIRED": "true",
        "YOUTUBE_API_KEY": "yt-test-key",
        "IMGUR_CLIENT_ID": "imgur-test-id",
        "REDDIT_CLIENT_ID": "reddit-id",
        "REDDIT_CLIENT_SECRET": "reddit-secret",
        "TUMBLR_API_KEYS": "tumblr-key-1,tumblr-key-2",
        "VK_ACCESS_TOKEN": "",
        "RENDER_WORKERS": "2",
        "LOG_LEVEL": "WARNING",
    }
)

import json  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402

from app.config import Settings, get_settings  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
requires_ffmpeg = pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg/ffprobe не установлены")


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# По умолчанию тесты идут на SQLite. Для проверки на PostgreSQL:
#   TEST_DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/test_db pytest
# (база будет полностью очищаться перед каждым тестом — не указывайте рабочую БД!)
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    get_settings.cache_clear()
    s = get_settings()
    s.var_dir = tmp_path / "var"
    s.database_url = TEST_DATABASE_URL or f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}"
    return s


async def _reset_postgres(url: str) -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await engine.dispose()


@pytest.fixture(autouse=True)
async def _clean_database(settings):
    if TEST_DATABASE_URL:
        await _reset_postgres(settings.resolved_database_url)
    yield


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    from app.auth.router import login_limiter
    from app.search.router import search_limiter

    login_limiter.reset()
    search_limiter.reset()
    yield


@pytest.fixture
async def app(settings: Settings):
    from app.main import create_app

    application = create_app(settings)
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def client(app) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


async def _new_client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


async def register(c: httpx.AsyncClient, identity: str = "user@example.com", password: str = "secret123") -> None:
    response = await c.post("/api/registration", json={"identity": identity, "password": password})
    assert response.status_code == 201, response.text


@pytest.fixture
async def user_client(app) -> httpx.AsyncClient:
    async with await _new_client(app) as c:
        await register(c)
        yield c


@pytest.fixture
async def other_client(app) -> httpx.AsyncClient:
    async with await _new_client(app) as c:
        await register(c, "other@example.com")
        yield c


@pytest.fixture
async def admin_client(app) -> httpx.AsyncClient:
    from app.auth.service import create_user
    from app.db.base import session_factory

    async with session_factory()() as db:
        await create_user(db, "admin@example.com", "adminpass", is_admin=True)
    async with await _new_client(app) as c:
        response = await c.post("/api/login", json={"identity": "admin@example.com", "password": "adminpass"})
        assert response.status_code == 200
        yield c


@pytest.fixture
async def db(app):
    from app.db.base import session_factory

    async with session_factory()() as session:
        yield session


# ---------- Медиафайлы для тестов редактора (генерируются ffmpeg один раз за сессию) ----------

def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


@pytest.fixture(scope="session")
def media_dir() -> Path:
    if not HAS_FFMPEG:
        pytest.skip("ffmpeg/ffprobe не установлены")
    directory = _TMP / "media"
    directory.mkdir(exist_ok=True)
    _ffmpeg("-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25:duration=4", "-f", "lavfi", "-i",
            "sine=frequency=440:duration=4", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest",
            str(directory / "landscape.mp4"))
    _ffmpeg("-f", "lavfi", "-i", "testsrc2=size=360x640:rate=30:duration=3", "-c:v", "libx264", "-preset",
            "ultrafast", str(directory / "vertical_silent.mp4"))
    _ffmpeg("-f", "lavfi", "-i", "color=c=red@0.8:s=120x60,format=rgba", "-frames:v", "1", str(directory / "logo.png"))
    _ffmpeg("-f", "lavfi", "-i", "sine=frequency=880:duration=1.5", str(directory / "music.mp3"))
    (directory / "subs.srt").write_text("1\n00:00:00,200 --> 00:00:01,500\nПривет, субтитры!\n", encoding="utf-8")
    (directory / "subs_cp1251.srt").write_bytes("1\n00:00:00,200 --> 00:00:01,500\nКириллица\n".encode("cp1251"))
    (directory / "broken.mp4").write_bytes(b"this is not a video at all")
    return directory
