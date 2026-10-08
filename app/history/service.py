"""История клипов пользователя: просмотренные/скачанные ролики не попадают в выдачу повторно."""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ClipHistory

MAX_URL_LENGTH = 2048


async def seen_urls(db: AsyncSession, user_id: int) -> set[str]:
    return set((await db.scalars(select(ClipHistory.url).where(ClipHistory.user_id == user_id))).all())


async def mark_seen(db: AsyncSession, user_id: int, url: str, platform: str | None = None) -> bool:
    """Добавляет ссылку в историю. Возвращает False, если она там уже была."""
    url = url.strip()
    if not url or len(url) > MAX_URL_LENGTH:
        return False
    exists = await db.scalar(
        select(ClipHistory.id).where(ClipHistory.user_id == user_id, ClipHistory.url == url)
    )
    if exists:
        return False
    db.add(ClipHistory(user_id=user_id, url=url, platform=platform))
    try:
        await db.commit()
    except IntegrityError:  # параллельный запрос успел раньше
        await db.rollback()
        return False
    return True
