"""Unit-тесты служебных модулей: ограничитель частоты, сообщения валидации, конфигурация, хранилище и т.п."""
import os
import subprocess
import time
from pathlib import Path

import pytest

from app.config import Settings
from app.core.errors import humanize_validation_error
from app.core.rate_limit import RateLimiter
from app.media.storage import Storage

# ---------- RateLimiter ----------


def test_rate_limiter_window_and_reset(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    limiter = RateLimiter(limit=2, window_seconds=60)
    assert limiter.hit("a") and limiter.hit("a")
    assert not limiter.hit("a")
    assert limiter.hit("b")  # ключи независимы
    now[0] += 61
    assert limiter.hit("a")  # окно сдвинулось
    limiter.reset()
    assert limiter._hits == {}


def test_rate_limiter_disabled():
    limiter = RateLimiter(limit=0)
    assert all(limiter.hit("x") for _ in range(100))


def test_rate_limiter_cleans_up_old_keys(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    limiter = RateLimiter(limit=5, window_seconds=10)
    for i in range(10_001):
        limiter._hits[f"k{i}"].append(0.0)
    now[0] = 100.0
    limiter.hit("fresh")  # словарь разросся — старые ключи удаляются
    assert set(limiter._hits) == {"fresh"}


def test_rate_limiter_check_raises_429():
    from fastapi import HTTPException

    limiter = RateLimiter(limit=1)
    limiter.check("k")
    with pytest.raises(HTTPException) as exc:
        limiter.check("k", "Подождите")
    assert exc.value.status_code == 429 and exc.value.detail == "Подождите"


# ---------- Сообщения валидации ----------

@pytest.mark.parametrize(
    ("error", "expected"),
    [
        ({"type": "less_than_equal", "loc": ("body", "speed"), "ctx": {"le": 4.0}}, "Скорость: должно быть не больше 4"),
        ({"type": "greater_than", "loc": ("body", "volume"), "ctx": {"gt": 0}}, "Громкость: должно быть не меньше 0"),
        ({"type": "string_too_long", "loc": ("body", "text"), "ctx": {"max_length": 300}}, "Текст: не длиннее 300 символов"),
        ({"type": "string_too_short", "loc": ("query", "q"), "ctx": {"min_length": 2}}, "Запрос: не короче 2 символов"),
        ({"type": "missing", "loc": ("body", "url")}, "Ссылка: обязательное поле"),
        ({"type": "literal_error", "loc": ("body", "aspect")}, "Формат кадра: недопустимое значение"),
        ({"type": "string_pattern_mismatch", "loc": ("body", "text_color")}, "Цвет текста: неверный формат"),
        ({"type": "float_parsing", "loc": ("body", "speed")}, "Скорость: неверное число"),
        ({"type": "extra_forbidden", "loc": ("body", "foo")}, "foo: неизвестный параметр"),
        ({"type": "value_error", "loc": ("body",), "msg": "Value error, Конец раньше начала"}, "Конец раньше начала"),
        ({"type": "something_new", "loc": (), "msg": "raw message"}, "raw message"),
    ],
)
def test_humanize_validation_error(error, expected):
    assert humanize_validation_error(error) == expected


# ---------- Настройки ----------

@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("postgresql://u:p@h:5432/db", "postgresql+asyncpg://u:p@h:5432/db"),
        ("postgres://u:p@h/db", "postgresql+asyncpg://u:p@h/db"),
        ("postgresql+asyncpg://u:p@h/db", "postgresql+asyncpg://u:p@h/db"),
    ],
)
def test_database_url_normalization(url, expected):
    assert Settings(database_url=url).resolved_database_url == expected


def test_sqlite_by_default(tmp_path):
    s = Settings(database_url="", var_dir=tmp_path / "var")
    assert s.resolved_database_url == f"sqlite+aiosqlite:///{(tmp_path / 'var' / 'app.db').as_posix()}"
    assert (tmp_path / "var").is_dir()


def test_tumblr_keys_parsing():
    assert Settings(tumblr_api_keys=" a, ,b ,").tumblr_keys == ["a", "b"]
    assert Settings(tumblr_api_keys="").tumblr_keys == []


# ---------- База данных ----------

async def test_engine_must_be_initialized():
    from app.db import base

    await base.dispose_engine()
    with pytest.raises(RuntimeError):
        base.get_engine()
    with pytest.raises(RuntimeError):
        base.session_factory()


def test_postgres_engine_options():
    from app.db import base

    engine = base.init_engine("postgresql+asyncpg://u:p@localhost:1/db")
    try:
        assert engine.pool.size() == 10
    finally:
        engine.sync_engine.dispose()
        base._engine = base._session_factory = None


# ---------- Хранилище ----------

def test_storage_paths_and_escape(tmp_path):
    storage = Storage(tmp_path / "s")
    job = storage.job_dir("abc")
    job.mkdir(parents=True)
    assert storage.relative(job) == "jobs/abc"
    assert storage.absolute("jobs/abc") == job.resolve()
    with pytest.raises(ValueError):
        storage.absolute("../../etc/passwd")
    assert len(storage.new_id()) == 32


def test_storage_cleans_only_old_tmp(tmp_path):
    storage = Storage(tmp_path / "s")
    old_dir, new_dir = storage.new_tmp_dir(), storage.new_tmp_dir()
    old_file = storage.root / "tmp" / "stray.part"
    old_file.write_text("x")
    past = time.time() - 7200
    os.utime(old_dir, (past, past))
    os.utime(old_file, (past, past))
    assert storage.cleanup_tmp(3600) == 2
    assert not old_dir.exists() and not old_file.exists() and new_dir.exists()


# ---------- Шаблоны ----------

def test_static_url_for_missing_file():
    from app.web.templating import static_url

    assert static_url("/css/does-not-exist.css") == "/static/css/does-not-exist.css?v=0"


# ---------- ffmpeg/ffprobe: служебные функции ----------

def test_resolve_binary_accepts_file_path(tmp_path):
    from app.media.ffmpeg import ffmpeg_dir, resolve_binary

    fake = tmp_path / "my-ffmpeg"
    fake.write_text("")
    assert resolve_binary(str(fake)) == str(fake)
    assert ffmpeg_dir("no-such-binary-xyz") is None


@pytest.mark.parametrize(("value", "expected"), [("30/1", 30.0), ("0/0", None), ("abc", None), ("25/0", None), (None, None)])
def test_parse_fps(value, expected):
    from app.media.ffmpeg import _parse_fps

    assert _parse_fps(value) == expected


@pytest.mark.parametrize(("stream", "expected"), [({"tags": {"rotate": "bad"}}, 0), ({"tags": {"rotate": "90"}}, 90), ({}, 0)])
def test_rotation_parsing(stream, expected):
    from app.media.ffmpeg import _rotation

    assert _rotation(stream) == expected


def test_probe_timeout(monkeypatch, tmp_path):
    from app.media import ffmpeg

    monkeypatch.setattr(ffmpeg, "resolve_binary", lambda name: name)

    def slow(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="ffprobe", timeout=1)

    monkeypatch.setattr(ffmpeg.subprocess, "run", slow)
    with pytest.raises(ffmpeg.MediaError, match="превышено время"):
        ffmpeg.probe(tmp_path / "x.mp4")


# ---------- Загрузчик: редкие ветки ----------

def test_platform_for_malformed_url():
    from app.media.fetch import platform_for_url

    assert platform_for_url("http://[::1") is None


@pytest.fixture
def ydl(monkeypatch):
    import yt_dlp

    from tests.editor.test_media import FakeYDL

    FakeYDL.info, FakeYDL.error, FakeYDL.write_file, FakeYDL.instances = {"duration": 5}, None, True, []
    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYDL)
    return FakeYDL


def _options(timeout=30):
    from app.media.fetch import FetchOptions

    return FetchOptions(max_duration=60, max_bytes=10**6, timeout=timeout)


def test_download_no_metadata(ydl, tmp_path, monkeypatch):
    from app.media import fetch

    monkeypatch.setattr(ydl, "extract_info", lambda self, *a, **k: None)
    with pytest.raises(fetch.MediaError, match="недоступно"):
        fetch.download("https://coub.com/view/x", tmp_path, _options())


def test_download_timeout_in_progress_hook(ydl, tmp_path):
    from app.media import fetch

    with pytest.raises(fetch.MediaError, match="слишком много времени"):
        fetch.download("https://coub.com/view/x", tmp_path, _options(timeout=-1))


def test_download_timeout_wrapped_by_ytdlp(ydl, tmp_path, monkeypatch):
    from yt_dlp.utils import DownloadError

    from app.media import fetch

    def wrapped(self, info, download=True):
        try:
            raise fetch._Timeout()
        except fetch._Timeout:
            import sys

            raise DownloadError("timeout", sys.exc_info())

    monkeypatch.setattr(ydl, "process_ie_result", wrapped)
    with pytest.raises(fetch.MediaError, match="слишком много времени"):
        fetch.download("https://coub.com/view/x", tmp_path, _options())


def test_download_progress_with_separate_audio(ydl, tmp_path):
    from app.media import fetch

    ydl.info = {"duration": 5, "formats": [{"vcodec": "none"}, {"vcodec": "avc1"}]}
    progress: list[float] = []
    fetch.download("https://www.youtube.com/watch?v=x", tmp_path, _options(), progress.append)
    assert 0.2 < progress[1] < 0.3  # первый файл из двух скачан наполовину = 25%


# ---------- Рендер текста: редкие ветки ----------

def test_find_emoji_font_prefers_configured(tmp_path):
    from app.editor.textrender import find_emoji_font

    font = tmp_path / "emoji.ttf"
    font.write_bytes(b"x")
    assert find_emoji_font(str(font)) == str(font)
    assert find_emoji_font(str(tmp_path / "missing.ttf")) != str(tmp_path / "missing.ttf")


def test_bitmap_emoji_font_falls_back_to_native_size(monkeypatch):
    from PIL import ImageFont

    from app.editor import textrender

    textrender._emoji_font.cache_clear()
    calls = []

    def truetype(path, size):
        calls.append(size)
        if size != 109:
            raise OSError("invalid pixel size")
        return "font"

    monkeypatch.setattr(ImageFont, "truetype", truetype)
    try:
        assert textrender._emoji_font("noto.ttf") == ("font", 109)
        assert calls == [128, 109]
    finally:
        textrender._emoji_font.cache_clear()


def test_broken_emoji_font_is_skipped(tmp_path):
    from app.config import get_settings
    from app.editor import textrender

    broken = tmp_path / "broken.ttf"
    broken.write_bytes(b"not a font")
    textrender._emoji_font.cache_clear()
    image = textrender.render_text_image("Огонь 🔥", 400, 400, position="top", size="medium", color="#ffffff",
                                        background=True, font_path=str(get_settings().font_path),
                                        emoji_font_path=str(broken))
    assert image.getbbox() is not None  # текст нарисован, эмодзи пропущено без падения
    textrender._emoji_font.cache_clear()


def test_blank_line_between_paragraphs_keeps_spacing():
    from app.config import get_settings
    from app.editor.textrender import render_text_image

    font = str(get_settings().font_path)
    one = render_text_image("Раз\nДва", 400, 800, position="top", size="medium", color="#ffffff", background=True,
                            font_path=font, emoji_font_path=None).getbbox()
    two = render_text_image("Раз\n\nДва", 400, 800, position="top", size="medium", color="#ffffff", background=True,
                            font_path=font, emoji_font_path=None).getbbox()
    assert two[3] > one[3]  # пустая строка добавляет отступ
