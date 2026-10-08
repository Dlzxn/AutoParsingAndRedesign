"""Работа с ffmpeg/ffprobe: анализ файлов и запуск рендера с отслеживанием прогресса."""
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


class MediaError(Exception):
    """Ошибка обработки медиа с сообщением для пользователя."""


@dataclass(frozen=True)
class MediaInfo:
    duration: float
    width: int  # с учётом поворота из метаданных (как увидит зритель)
    height: int
    has_audio: bool
    has_video: bool
    fps: float | None = None
    video_codec: str | None = None


def resolve_binary(name_or_path: str) -> str:
    found = shutil.which(name_or_path)
    if found:
        return found
    if Path(name_or_path).is_file():
        return str(name_or_path)
    raise MediaError(f"Не найден {name_or_path}. Установите ffmpeg и добавьте его в PATH.")


def _parse_fps(value: str | None) -> float | None:
    if not value or value in ("0/0",):
        return None
    try:
        num, _, den = value.partition("/")
        return float(num) / float(den or 1)
    except (ValueError, ZeroDivisionError):
        return None


def _rotation(stream: dict) -> int:
    rotate = (stream.get("tags") or {}).get("rotate")
    if rotate is not None:
        try:
            return int(float(rotate))
        except ValueError:
            return 0
    for side in stream.get("side_data_list") or []:
        if "rotation" in side:
            return int(float(side["rotation"]))
    return 0


def parse_probe(data: dict) -> MediaInfo:
    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"
                  and not (s.get("disposition") or {}).get("attached_pic")), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    duration = 0.0
    for candidate in ((data.get("format") or {}).get("duration"), (video or {}).get("duration")):
        try:
            duration = float(candidate)
            break
        except (TypeError, ValueError):
            continue
    width = int((video or {}).get("width") or 0)
    height = int((video or {}).get("height") or 0)
    if video and abs(_rotation(video)) % 180 == 90:
        width, height = height, width
    return MediaInfo(
        duration=duration,
        width=width,
        height=height,
        has_audio=audio is not None,
        has_video=video is not None and width > 0 and height > 0,
        fps=_parse_fps((video or {}).get("avg_frame_rate")) or _parse_fps((video or {}).get("r_frame_rate")),
        video_codec=(video or {}).get("codec_name"),
    )


def probe(path: Path, ffprobe: str = "ffprobe", timeout: float = 60) -> MediaInfo:
    cmd = [resolve_binary(ffprobe), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=_NO_WINDOW)
    except subprocess.TimeoutExpired as exc:
        raise MediaError("Не удалось прочитать файл: превышено время анализа") from exc
    if proc.returncode != 0:
        log.warning("ffprobe failed for %s: %s", path, proc.stderr.decode(errors="replace")[-500:])
        raise MediaError("Файл повреждён или не является видео")
    return parse_probe(json.loads(proc.stdout.decode("utf-8", errors="replace") or "{}"))


def run_ffmpeg(
    args: list[str],
    *,
    ffmpeg: str = "ffmpeg",
    expected_duration: float | None = None,
    on_progress: Callable[[float], None] | None = None,
    timeout: float = 600,
    cwd: Path | None = None,
    cancel: threading.Event | None = None,
) -> None:
    """Запускает ffmpeg (блокирующе — вызывать из потока). Прогресс 0..1 передаётся в on_progress.

    Процесс принудительно завершается по таймауту или при установке события cancel.
    """
    cmd = [resolve_binary(ffmpeg), "-hide_banner", "-nostdin", "-y", "-progress", "pipe:1", "-nostats", *args]
    log.debug("ffmpeg: %s", " ".join(cmd))
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(cwd) if cwd else None,
        creationflags=_NO_WINDOW,
    )
    stderr_tail: deque[str] = deque(maxlen=40)

    def _drain_stderr() -> None:
        assert proc.stderr is not None
        for raw in proc.stderr:
            stderr_tail.append(raw.decode("utf-8", errors="replace").rstrip())

    stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
    stderr_thread.start()

    timed_out = threading.Event()
    cancelled = threading.Event()
    finished = threading.Event()

    def _watchdog() -> None:
        deadline = time.monotonic() + timeout
        while not finished.wait(0.25):
            if cancel is not None and cancel.is_set():
                cancelled.set()
                proc.kill()
                return
            if time.monotonic() > deadline:
                timed_out.set()
                proc.kill()
                return

    watchdog = threading.Thread(target=_watchdog, daemon=True)
    watchdog.start()
    last_report = 0.0
    try:
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.decode("ascii", errors="ignore").strip()
            if not on_progress or not expected_duration:
                continue
            key, _, value = line.partition("=")
            if key in ("out_time_us", "out_time_ms") and value.lstrip("-").isdigit():
                seconds = int(value) / 1_000_000  # out_time_ms тоже в микросекундах (историческая особенность)
                now = time.monotonic()
                if now - last_report >= 0.5:
                    last_report = now
                    on_progress(max(0.0, min(0.99, seconds / expected_duration)))
        proc.wait()
    finally:
        finished.set()
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        stderr_thread.join(timeout=5)

    if cancelled.is_set():
        raise MediaError("Обработка отменена")
    if timed_out.is_set():
        raise MediaError("Обработка заняла слишком много времени и была остановлена")
    if proc.returncode != 0:
        tail = "\n".join(stderr_tail)
        log.error("ffmpeg failed (code %s):\n%s", proc.returncode, tail)
        raise MediaError("Не удалось обработать видео")
    if on_progress:
        on_progress(1.0)


def ffmpeg_dir(ffmpeg: str) -> str | None:
    try:
        return os.path.dirname(resolve_binary(ffmpeg))
    except MediaError:
        return None
