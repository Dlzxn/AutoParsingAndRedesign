"""Периодическое обслуживание: удаление устаревших медиафайлов, сессий и временных каталогов."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.auth.service import delete_expired_sessions
from app.config import Settings
from app.db.base import session_factory
from app.db.models import MediaSource, RenderJob
from app.media.storage import Storage

log = logging.getLogger(__name__)

INTERVAL_SECONDS = 30 * 60


async def cleanup_once(settings: Settings, storage: Storage) -> dict[str, int]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.media_ttl_hours)
    async with session_factory()() as db:
        old_sources = (await db.scalars(select(MediaSource.id).where(MediaSource.created_at < cutoff))).all()
        old_jobs = (await db.scalars(
            select(RenderJob.id).where(
                (RenderJob.created_at < cutoff) | RenderJob.source_id.in_(old_sources),
                RenderJob.status.not_in(("queued", "processing")),
            )
        )).all()
        if old_jobs:
            await db.execute(delete(RenderJob).where(RenderJob.id.in_(old_jobs)))
        busy_sources = set((await db.scalars(
            select(RenderJob.source_id).where(RenderJob.status.in_(("queued", "processing")))
        )).all())
        removable_sources = [s for s in old_sources if s not in busy_sources]
        if removable_sources:
            await db.execute(delete(MediaSource).where(MediaSource.id.in_(removable_sources)))
        await db.commit()
        sessions = await delete_expired_sessions(db)

    for job_id in old_jobs:
        storage.remove_dir(storage.job_dir(job_id))
    for source_id in removable_sources:
        storage.remove_dir(storage.source_dir(source_id))
    tmp = await asyncio.to_thread(storage.cleanup_tmp)
    result = {"jobs": len(old_jobs), "sources": len(removable_sources), "sessions": sessions, "tmp": tmp}
    if any(result.values()):
        log.info("Cleanup: %s", result)
    return result


async def maintenance_loop(settings: Settings, storage: Storage) -> None:
    while True:
        try:
            await cleanup_once(settings, storage)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Maintenance failed")
        await asyncio.sleep(INTERVAL_SECONDS)
