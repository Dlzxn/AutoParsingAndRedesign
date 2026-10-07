"""Фоновая очередь рендера.

Задачи хранятся в БД (render_jobs), очередь — в памяти процесса. Рендер выполняет ffmpeg в отдельном
потоке, поэтому сервер продолжает отвечать на запросы. Число одновременных рендеров ограничено
настройкой RENDER_WORKERS. После перезапуска незавершённые задачи ставятся в очередь заново.

Важно: очередь живёт в одном процессе — запускайте uvicorn с одним воркером (ffmpeg и так
использует все ядра).
"""
import asyncio
import logging
import shutil
import threading
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.config import Settings
from app.db.base import session_factory
from app.db.models import MediaSource, RenderJob
from app.editor.pipeline import FONT_FILE, TEXT_IMAGE, RenderInputs, plan_render
from app.editor.schemas import EditParams
from app.editor.textrender import find_emoji_font, render_text_image
from app.media.ffmpeg import MediaError, probe, run_ffmpeg
from app.media.storage import Storage

log = logging.getLogger(__name__)

ACTIVE_STATUSES = ("queued", "processing")


class RenderQueue:
    def __init__(self, settings: Settings, storage: Storage) -> None:
        self.settings = settings
        self.storage = storage
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.progress: dict[str, float] = {}
        self._workers: list[asyncio.Task] = []
        self._cancel = threading.Event()

    async def start(self) -> None:
        await self._requeue_unfinished()
        self._cancel.clear()
        for i in range(max(1, self.settings.render_workers)):
            self._workers.append(asyncio.create_task(self._worker(), name=f"render-worker-{i}"))
        log.info("Render queue started with %d worker(s)", len(self._workers))

    async def stop(self) -> None:
        self._cancel.set()  # останавливает запущенные ffmpeg
        for task in self._workers:
            task.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    async def enqueue(self, job_id: str) -> None:
        self.progress[job_id] = 0.0
        await self.queue.put(job_id)

    async def _requeue_unfinished(self) -> None:
        async with session_factory()() as db:
            await db.execute(update(RenderJob).where(RenderJob.status == "processing").values(status="queued"))
            await db.commit()
            ids = (await db.scalars(
                select(RenderJob.id).where(RenderJob.status == "queued").order_by(RenderJob.created_at)
            )).all()
        for job_id in ids:
            await self.enqueue(job_id)
        if ids:
            log.info("Re-queued %d unfinished render job(s)", len(ids))

    async def _worker(self) -> None:
        while True:
            job_id = await self.queue.get()
            try:
                await self._process(job_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Render worker crashed on job %s", job_id)
            finally:
                self.queue.task_done()

    async def _set(self, job_id: str, **values) -> None:
        async with session_factory()() as db:
            await db.execute(update(RenderJob).where(RenderJob.id == job_id).values(**values))
            await db.commit()

    async def _process(self, job_id: str) -> None:
        async with session_factory()() as db:
            job = await db.get(RenderJob, job_id)
            if job is None or job.status != "queued":
                self.progress.pop(job_id, None)
                return
            source = await db.get(MediaSource, job.source_id)
            params_data = dict(job.params)
        if source is None:
            await self._set(job_id, status="failed", error="Исходное видео удалено", finished_at=_now())
            return

        await self._set(job_id, status="processing", started_at=_now(), progress=0.0)
        job_dir = self.storage.job_dir(job_id)
        started = asyncio.get_running_loop().time()
        try:
            params = EditParams(**{k: v for k, v in params_data.items() if not k.startswith("_")})
            source_path = self.storage.absolute(source.path)
            info = await asyncio.to_thread(probe, source_path, self.settings.ffprobe_path)
            inputs = RenderInputs(
                source=str(source_path),
                output="output.mp4",
                logo=params_data.get("_logo"),
                music=params_data.get("_music"),
                subtitles=bool(params_data.get("_subtitles")),
                text_image=bool(params.text),
            )
            plan = plan_render(params, info, inputs)
            if params.text:
                await asyncio.to_thread(self._render_text, params, plan.width, plan.height, job_dir / TEXT_IMAGE)
            if plan.needs_font and not (job_dir / FONT_FILE).exists():
                shutil.copyfile(self.settings.font_path, job_dir / FONT_FILE)

            def on_progress(value: float) -> None:
                self.progress[job_id] = value

            timeout = max(120.0, plan.output_duration * self.settings.render_timeout_factor)
            await asyncio.to_thread(
                run_ffmpeg,
                plan.args,
                ffmpeg=self.settings.ffmpeg_path,
                expected_duration=plan.output_duration,
                on_progress=on_progress,
                timeout=timeout,
                cwd=job_dir,
                cancel=self._cancel,
            )
            output = job_dir / "output.mp4"
            result = await asyncio.to_thread(probe, output, self.settings.ffprobe_path)
            if not result.has_video:
                raise MediaError("Не удалось обработать видео")
            await self._set(
                job_id,
                status="done",
                progress=1.0,
                output_path=self.storage.relative(output),
                output_size=output.stat().st_size,
                output_duration=round(result.duration, 3),
                finished_at=_now(),
            )
            log.info("Render done: job=%s %dx%d %.1fs in %.1fs", job_id, plan.width, plan.height,
                     plan.output_duration, asyncio.get_running_loop().time() - started)
        except MediaError as exc:
            log.warning("Render failed: job=%s: %s", job_id, exc)
            await self._set(job_id, status="failed", error=str(exc), finished_at=_now())
        except asyncio.CancelledError:
            await asyncio.shield(self._set(job_id, status="queued", progress=0.0))
            raise
        except Exception:
            log.exception("Render crashed: job=%s", job_id)
            await self._set(job_id, status="failed", error="Внутренняя ошибка обработки видео", finished_at=_now())
        finally:
            self.progress.pop(job_id, None)
            (job_dir / TEXT_IMAGE).unlink(missing_ok=True)

    def _render_text(self, params: EditParams, width: int, height: int, dest) -> None:
        image = render_text_image(
            params.text, width, height,
            position=params.text_position, size=params.text_size, color=params.text_color,
            background=params.text_background, font_path=str(self.settings.font_path),
            emoji_font_path=find_emoji_font(self.settings.emoji_font_path),
        )
        image.save(dest, optimize=False, compress_level=1)


def _now() -> datetime:
    return datetime.now(timezone.utc)
