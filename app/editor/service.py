import logging
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MediaSource, RenderJob, User
from app.editor.pipeline import SUBTITLES_FILE
from app.editor.schemas import EditParams, JobOut, SourceOut
from app.editor.worker import ACTIVE_STATUSES, RenderQueue
from app.history.service import mark_seen
from app.media.fetch import platform_for_url, validate_url
from app.media.ffmpeg import MediaError, MediaInfo
from app.media.service import AUDIO_EXTENSIONS, IMAGE_EXTENSIONS, MediaService
from app.media.storage import Storage

log = logging.getLogger(__name__)

MAX_ACTIVE_JOBS_PER_USER = 3
MAX_LOGO_BYTES = 10 * 1024 * 1024
MAX_MUSIC_BYTES = 50 * 1024 * 1024
MAX_SUBTITLES_BYTES = 1024 * 1024


def source_out(source: MediaSource) -> SourceOut:
    return SourceOut(
        id=source.id,
        duration=source.duration,
        width=source.width,
        height=source.height,
        has_audio=source.has_audio,
        size_bytes=source.size_bytes,
        original_name=source.original_name,
        origin_url=source.origin_url,
        preview_url=f"/api/editor/sources/{source.id}/file",
    )


def job_out(job: RenderJob, live_progress: float | None = None) -> JobOut:
    done = job.status == "done"
    return JobOut(
        id=job.id,
        source_id=job.source_id,
        status=job.status,
        progress=round(live_progress if live_progress is not None and job.status == "processing" else job.progress, 3),
        error=job.error,
        result_url=f"/api/editor/jobs/{job.id}/result" if done else None,
        download_url=f"/api/editor/jobs/{job.id}/result?download=1" if done else None,
        output_size=job.output_size,
        output_duration=job.output_duration,
        params={k: v for k, v in job.params.items() if not k.startswith("_")},
    )


class EditorService:
    def __init__(self, media: MediaService, storage: Storage, queue: RenderQueue) -> None:
        self.media = media
        self.storage = storage
        self.queue = queue
        self.download_progress: dict[str, float] = {}  # "user_id:token" -> 0..1

    async def _save_source(
        self, db: AsyncSession, user: User, source_id: str, path: Path, info: MediaInfo, **extra
    ) -> MediaSource:
        source = MediaSource(
            id=source_id,
            user_id=user.id,
            path=self.storage.relative(path),
            duration=round(info.duration, 3),
            width=info.width,
            height=info.height,
            has_audio=info.has_audio,
            size_bytes=path.stat().st_size,
            **extra,
        )
        db.add(source)
        await db.commit()
        return source

    async def create_source_from_upload(self, db: AsyncSession, user: User, upload: UploadFile) -> MediaSource:
        source_id = self.storage.new_id()
        directory = self.storage.source_dir(source_id)
        try:
            path, info = await self.media.ingest_upload(upload, directory)
            name = (upload.filename or "video")[:255]
            return await self._save_source(db, user, source_id, path, info, original_name=name)
        except BaseException:
            self.storage.remove_dir(directory)
            raise

    async def create_source_from_url(
        self, db: AsyncSession, user: User, url: str, progress_token: str | None = None
    ) -> MediaSource:
        url = validate_url(url)
        # Тот же ролик уже скачан этим пользователем и ещё хранится — отдаём сразу
        existing = await db.scalar(
            select(MediaSource)
            .where(MediaSource.user_id == user.id, MediaSource.origin_url == url)
            .order_by(MediaSource.created_at.desc())
            .limit(1)
        )
        if existing is not None and self.storage.absolute(existing.path).exists():
            return existing

        key = f"{user.id}:{progress_token}" if progress_token else None

        def on_progress(value: float) -> None:
            if key:  # прогресс только растёт (видео и звук качаются отдельными файлами)
                self.download_progress[key] = max(self.download_progress.get(key, 0.0), value)

        source_id = self.storage.new_id()
        directory = self.storage.source_dir(source_id)
        try:
            if key:
                self.download_progress[key] = 0.0
            path, info, title = await self.media.ingest_url(url, directory, on_progress)
            source = await self._save_source(
                db, user, source_id, path, info, origin_url=url, original_name=(title or "")[:255] or None
            )
        except BaseException:
            self.storage.remove_dir(directory)
            raise
        finally:
            if key:
                self.download_progress.pop(key, None)
        await mark_seen(db, user.id, url, platform_for_url(url))
        return source

    def get_download_progress(self, user: User, token: str) -> float | None:
        return self.download_progress.get(f"{user.id}:{token}")

    async def get_source(self, db: AsyncSession, user: User, source_id: str) -> MediaSource:
        source = await db.get(MediaSource, source_id)
        if source is None or source.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Видео не найдено или срок его хранения истёк")
        return source

    async def get_job(self, db: AsyncSession, user: User, job_id: str) -> RenderJob:
        job = await db.get(RenderJob, job_id)
        if job is None or job.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Задача не найдена")
        return job

    async def list_jobs(self, db: AsyncSession, user: User, limit: int = 20) -> list[RenderJob]:
        rows = await db.scalars(
            select(RenderJob).where(RenderJob.user_id == user.id).order_by(RenderJob.created_at.desc()).limit(limit)
        )
        return list(rows.all())

    async def create_job(
        self,
        db: AsyncSession,
        user: User,
        source: MediaSource,
        params: EditParams,
        logo: UploadFile | None = None,
        music: UploadFile | None = None,
        subtitles: UploadFile | None = None,
    ) -> RenderJob:
        active = await db.scalar(
            select(func.count()).select_from(RenderJob)
            .where(RenderJob.user_id == user.id, RenderJob.status.in_(ACTIVE_STATUSES))
        )
        if active >= MAX_ACTIVE_JOBS_PER_USER:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Дождитесь окончания текущей обработки — одновременно можно обрабатывать до 3 видео",
            )
        if params.trim_start >= source.duration:
            raise MediaError("Начало фрагмента позже конца видео")

        job_id = self.storage.new_id()
        job_dir = self.storage.job_dir(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        data = params.model_dump()
        try:
            if logo is not None and logo.filename:
                path = await self.media.save_upload(logo, job_dir / "logo", MAX_LOGO_BYTES, IMAGE_EXTENSIONS)
                data["_logo"] = path.name
            if music is not None and music.filename:
                path = await self.media.save_upload(music, job_dir / "music", MAX_MUSIC_BYTES, AUDIO_EXTENSIONS)
                data["_music"] = path.name
            if subtitles is not None and subtitles.filename:
                await self._save_subtitles(subtitles, job_dir / SUBTITLES_FILE)
                data["_subtitles"] = True
            job = RenderJob(id=job_id, user_id=user.id, source_id=source.id, params=data, status="queued")
            db.add(job)
            await db.commit()
        except BaseException:
            self.storage.remove_dir(job_dir)
            raise
        await self.queue.enqueue(job_id)
        log.info("Render job queued: job=%s user=%s source=%s", job_id, user.id, source.id)
        return job

    async def _save_subtitles(self, upload: UploadFile, dest: Path) -> None:
        if not (upload.filename or "").lower().endswith(".srt"):
            raise MediaError("Субтитры принимаются в формате .srt")
        raw = await upload.read(MAX_SUBTITLES_BYTES + 1)
        if len(raw) > MAX_SUBTITLES_BYTES:
            raise MediaError("Файл субтитров слишком большой")
        for encoding in ("utf-8-sig", "cp1251"):
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise MediaError("Не удалось прочитать файл субтитров (ожидается UTF-8 или Windows-1251)")
        if "-->" not in text:
            raise MediaError("Файл субтитров не похож на .srt")
        dest.write_text(text.replace("\r\n", "\n"), encoding="utf-8")
