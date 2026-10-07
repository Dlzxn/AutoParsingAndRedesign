from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.auth.deps import DbSession, FeatureUser
from app.catalog.service import ensure_platform_enabled
from app.config import get_settings
from app.core.rate_limit import RateLimiter
from app.history.service import seen_urls
from app.search.base import ProviderError
from app.search.service import SearchService

router = APIRouter(prefix="/api/search", tags=["search"])

search_limiter = RateLimiter(get_settings().search_rate_limit)


def get_search_service(request: Request) -> SearchService:
    return request.app.state.search


@router.get("/{platform}")
async def search(
    platform: str,
    request: Request,
    db: DbSession,
    user: FeatureUser,
    q: Annotated[str, Query(min_length=2, max_length=100)],
):
    service = get_search_service(request)
    if not service.has_platform(platform):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Неизвестная платформа")
    await ensure_platform_enabled(db, platform)
    query = q.strip()
    if len(query) < 2:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Введите хотя бы 2 символа")

    limiter_key = f"user:{user.id}" if user else f"ip:{request.client.host if request.client else '-'}"
    search_limiter.check(limiter_key, "Слишком много поисковых запросов, подождите минуту")

    exclude = await seen_urls(db, user.id) if user else set()
    try:
        items, cached = await service.search(platform, query, exclude)
    except ProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return {"platform": platform, "query": query, "items": items, "cached": cached}
