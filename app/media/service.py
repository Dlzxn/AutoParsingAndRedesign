"""Получение исходных видео: загрузка файла пользователем или скачивание по ссылке."""
import asyncio
import logging
import re
import shutil
from collections.abc import Callable
from pathlib import Path

from fastapi import UploadFile

from app.config import Settings
from app.media import fetch
from app.media.ffmpeg import MediaError, MediaInfo, probe
from app.media.storage import Storage

log = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi", ".3gp", ".flv", ".mpeg", ".mpg", ".ts"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".opus", ".flac"}
CHUNK = 1024 * 1024


class MediaService:
    def __init__(self, settings: Settings, storage: Storage) -> None:
        self.settings = settings
        self.storage = storage
        self._downloads = asyncio.Semaphore(4)  # одновременных скачиваний по ссылкам

    @property
    def max_upload_bytes(self) -> int:
        return self.settings.max_upload_mb * 1024 * 1024

    def fetch_options(self) -> fetch.FetchOptions:
        s = self.settings
        return fetch.FetchOptions(
            max_duration=s.max_source_duration,
            max_bytes=self.max_upload_bytes,
            timeout=s.download_timeout,
            proxy=s.ytdlp_proxy,
            ffmpeg=s.ffmpeg_path,
            js_runtimes=tuple(r.strip() for r in s.ytdlp_js_runtimes.split(",") if r.strip()),
        )

    async def save_upload(self, upload: UploadFile, dest: Path, max_bytes: int, allowed_ext: set[str]) -> Path:
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in allowed_ext:
            raise MediaError(f"Неподдерживаемый формат файла. Допустимо: {', '.join(sorted(allowed_ext))}")
        dest = dest.with_suffix(suffix)
        dest.parent.mkdir(parents=True, exist_ok=True)
        size = 0
        with dest.open("wb") as out:
            while chunk := await upload.read(CHUNK):
                size += len(chunk)
                if size > max_bytes:
                    out.close()
                    dest.unlink(missing_ok=True)
                    raise MediaError(f"Файл слишком большой (максимум {max_bytes // (1024 * 1024)} МБ)")
                out.write(chunk)
        if size == 0:
            dest.unlink(missing_ok=True)
            raise MediaError("Файл пустой")
        return dest

    async def inspect_video(self, path: Path) -> MediaInfo:
        info = await asyncio.to_thread(probe, path, self.settings.ffprobe_path)
        if not info.has_video:
            raise MediaError("Файл не содержит видео")
        if info.duration <= 0:
            raise MediaError("Не удалось определить длительность видео")
        if info.duration > self.settings.max_source_duration + 1:
            raise MediaError(f"Видео слишком длинное (максимум {self.settings.max_source_duration // 60} мин)")
        return info

    async def ingest_upload(self, upload: UploadFile, dest_dir: Path) -> tuple[Path, MediaInfo]:
        path = await self.save_upload(upload, dest_dir / "source", self.max_upload_bytes, VIDEO_EXTENSIONS)
        return path, await self.inspect_video(path)

    async def ingest_url(
        self, url: str, dest_dir: Path, on_progress: Callable[[float], None] | None = None
    ) -> tuple[Path, MediaInfo, str | None]:
        async with self._downloads:
            result = await asyncio.to_thread(fetch.download, url, dest_dir, self.fetch_options(), on_progress)
        return result.path, await self.inspect_video(result.path), result.title

    @staticmethod
    def discard(path: Path) -> None:
        shutil.rmtree(path, ignore_errors=True)


def safe_filename(title: str | None, fallback: str = "clip", max_length: int = 60) -> str:
    """Имя файла из названия ролика: буквы (в т.ч. кириллица), цифры, дефис и подчёркивание."""
    cleaned = re.sub(r"[^\w\s-]", "", title or "", flags=re.UNICODE)
    cleaned = re.sub(r"[\s_]+", "_", cleaned).strip("_-")[:max_length].rstrip("_-")
    return cleaned or fallback
