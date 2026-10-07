import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.auth.deps import CurrentUser, DbSession, FeatureUser
from app.catalog.service import ensure_platform_enabled
from app.history.service import mark_seen
from app.media.fetch import platform_for_url, validate_url
from app.media.service import MediaService
from app.media.storage import Storage

log = logging.getLogger(__name__)

router = APIRouter(tags=["history"])


class SeenIn(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    platform: str | None = Field(None, max_length=20)


@router.post("/api/history", status_code=status.HTTP_204_NO_CONTENT)
async def add_to_history(data: SeenIn, db: DbSession, user: CurrentUser):
    """Отметить клип как просмотренный — он больше не появится в выдаче."""
    await mark_seen(db, user.id, data.url, data.platform)


@router.get("/api/download")
async def download_clip(url: str, request: Request, background: BackgroundTasks, db: DbSession, user: FeatureUser):
    """Скачать ролик с платформы в mp4 (со звуком)."""
    url = validate_url(url)
    platform = platform_for_url(url)
    await ensure_platform_enabled(db, platform)
    media: MediaService = request.app.state.media
    storage: Storage = request.app.state.storage
    tmp_dir = storage.new_tmp_dir()
    try:
        path, _ = await media.ingest_url(url, tmp_dir)
    except BaseException:
        storage.remove_dir(tmp_dir)
        raise
    if user is not None:
        await mark_seen(db, user.id, url, platform)
    background.add_task(storage.remove_dir, tmp_dir)
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Видео недоступно")
    return FileResponse(path, media_type="video/mp4", filename=f"{platform}_clip{path.suffix}")
