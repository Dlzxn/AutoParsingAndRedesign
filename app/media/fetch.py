"""Скачивание видео по ссылке через yt-dlp.

Разрешены только ссылки поддерживаемых платформ — сервер не должен скачивать произвольные адреса
(в т.ч. внутренние адреса сети).
"""
import logging
import time
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.media.ffmpeg import MediaError, ffmpeg_dir

log = logging.getLogger(__name__)

ALLOWED_DOMAINS: dict[str, str] = {
    "youtube.com": "yt",
    "youtu.be": "yt",
    "vk.com": "vk",
    "vk.ru": "vk",
    "vkvideo.ru": "vk",
    "coub.com": "coub",
    "reddit.com": "reddit",
    "redd.it": "reddit",
    "imgur.com": "imgur",
    "tumblr.com": "tumblr",
}

LONG_SOURCE = 180  # секунд: для длинных роликов качаем 720p — из них всё равно вырезают короткий фрагмент


def format_for(duration: float | None) -> str:
    """H.264 + AAC в mp4 — совместимо и быстро обрабатывается.

    Ограничение по обеим сторонам кадра: вертикальный 1080×1920 тоже считается 1080p.
    `<=?` пропускает форматы без известного размера (прямые ссылки на mp4).
    """
    side = 1280 if duration and duration > LONG_SOURCE else 1920
    f = f"[height<=?{side}][width<=?{side}]"
    return f"bv*{f}[vcodec^=avc1]+ba[ext=m4a]/b{f}[ext=mp4]/bv*{f}+ba/b{f}/b"


@dataclass(frozen=True)
class FetchOptions:
    max_duration: int
    max_bytes: int
    timeout: float
    proxy: str = ""
    ffmpeg: str = "ffmpeg"
    js_runtimes: tuple[str, ...] = ("deno", "node")


def platform_for_url(url: str) -> str | None:
    """Ключ платформы для разрешённой ссылки, иначе None."""
    try:
        parsed = urllib.parse.urlsplit(url.strip())
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None
    if parsed.username or parsed.password or (parsed.port not in (None, 80, 443)):
        return None
    host = parsed.hostname.lower().rstrip(".")
    for domain, platform in ALLOWED_DOMAINS.items():
        if host == domain or host.endswith("." + domain):
            return platform
    return None


def validate_url(url: str) -> str:
    url = (url or "").strip()
    if len(url) > 2048 or platform_for_url(url) is None:
        raise MediaError("Ссылка не поддерживается. Используйте ссылку на ролик VK, YouTube, Coub, Reddit или Imgur.")
    return url


def _friendly_error(message: str) -> str:
    text = message.lower()
    if "too long" in text:
        return "Видео слишком длинное для обработки"
    if "file is larger" in text or "max_filesize" in text or "larger than max-filesize" in text:
        return "Видео слишком большое для обработки"
    if "private" in text or "login" in text or "sign in" in text or ("access" in text and "denied" in text):
        return "Видео недоступно: оно приватное или требует входа"
    if "not available" in text or "unavailable" in text or "404" in text or "removed" in text:
        return "Видео недоступно или удалено"
    if "timed out" in text or "timeout" in text:
        return "Платформа не отдаёт видео: превышено время ожидания"
    return "Не удалось скачать видео по ссылке"


class _Timeout(Exception):
    pass


@dataclass(frozen=True)
class DownloadResult:
    path: Path
    title: str | None


def download(
    url: str,
    dest_dir: Path,
    options: FetchOptions,
    on_progress: Callable[[float], None] | None = None,
) -> DownloadResult:
    """Скачивает ролик в dest_dir (блокирующе — вызывать из потока).

    Сначала читаются только метаданные: слишком длинный ролик отклоняется до скачивания,
    а качество выбирается по длительности. Прогресс 0..1 передаётся в on_progress.
    """
    import yt_dlp
    from yt_dlp.utils import DownloadError

    url = validate_url(url)
    dest_dir.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + options.timeout
    files: list[str] = []
    expected_files = 1

    def _progress_hook(d: dict) -> None:
        if time.monotonic() > deadline:
            raise _Timeout()
        if on_progress is None:
            return
        name = d.get("filename") or ""
        if name and name not in files:
            files.append(name)
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            fraction = (d.get("downloaded_bytes") or 0) / total if total else 0.0
            done = max(0, len(files) - 1)
            on_progress(min(0.97, (done + min(fraction, 1.0)) / max(expected_files, len(files))))

    params: dict = {
        "merge_output_format": "mp4",
        "outtmpl": str(dest_dir / "source.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "socket_timeout": 30,
        "retries": 3,
        "fragment_retries": 3,
        "max_filesize": options.max_bytes,
        "progress_hooks": [_progress_hook],
        "overwrites": True,
        "js_runtimes": {name: {} for name in options.js_runtimes},
    }
    location = ffmpeg_dir(options.ffmpeg)
    if location:
        params["ffmpeg_location"] = location
    if options.proxy:
        params["proxy"] = options.proxy

    started = time.monotonic()
    try:
        with yt_dlp.YoutubeDL(params) as probe_ydl:
            raw = probe_ydl.extract_info(url, download=False, process=False)
        if raw is None:
            raise MediaError("Видео недоступно или удалено")
        if raw.get("_type") in ("playlist", "multi_video"):
            raise MediaError("По ссылке находится плейлист, а не один ролик")
        duration = raw.get("duration")
        if duration and duration > options.max_duration:
            raise MediaError(f"Видео слишком длинное (максимум {options.max_duration // 60} мин)")
        # Отдельные дорожки видео и звука (YouTube, Reddit) скачиваются двумя файлами
        if any(f.get("vcodec") == "none" for f in raw.get("formats") or []):
            expected_files = 2
        if on_progress:
            on_progress(0.02)
        with yt_dlp.YoutubeDL({**params, "format": format_for(duration)}) as ydl:
            info = ydl.process_ie_result(raw, download=True)
    except MediaError:
        raise
    except _Timeout as exc:
        raise MediaError("Скачивание заняло слишком много времени") from exc
    except DownloadError as exc:
        if isinstance(exc.exc_info[1] if exc.exc_info else None, _Timeout):
            raise MediaError("Скачивание заняло слишком много времени") from exc
        log.warning("yt-dlp failed for %s: %s", url, exc)
        raise MediaError(_friendly_error(str(exc))) from exc
    except Exception as exc:  # yt-dlp может бросать самые разные исключения
        log.exception("yt-dlp crashed for %s", url)
        raise MediaError("Не удалось скачать видео по ссылке") from exc

    downloads = (info or {}).get("requested_downloads") or []
    path = Path(downloads[0]["filepath"]) if downloads and downloads[0].get("filepath") else None
    if path is None or not path.exists():
        candidates = sorted(dest_dir.glob("source.*"), key=lambda p: p.stat().st_size, reverse=True)
        path = candidates[0] if candidates else None
    if path is None or not path.exists() or path.stat().st_size == 0:
        raise MediaError("Видео недоступно или удалено")
    if on_progress:
        on_progress(1.0)
    log.info("Downloaded %s -> %s (%.1f MB) in %.1fs", url, path.name, path.stat().st_size / 1e6,
             time.monotonic() - started)
    title = (info or {}).get("title") or raw.get("title")
    return DownloadResult(path=path, title=title if title and not str(title).startswith("source") else None)
