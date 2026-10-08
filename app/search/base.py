import asyncio
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, ClassVar

import aiohttp

log = logging.getLogger(__name__)


class ProviderError(Exception):
    """Ошибка платформы с сообщением, которое можно показать пользователю."""


@dataclass
class SearchItem:
    id: str
    title: str
    url: str  # каноническая ссылка: по ней ведётся история, скачивание и редактирование
    kind: str = "video"  # video | text
    page_url: str | None = None  # страница с оригиналом
    preview_url: str | None = None  # прямой mp4 для <video>
    embed_url: str | None = None  # плеер для <iframe>
    thumbnail: str | None = None
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    text: str | None = None
    summary: str | None = None
    author: str | None = None
    published_at: int | None = None
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v not in (None, [], "")}


class SearchProvider:
    key: ClassVar[str]
    title: ClassVar[str]
    timeout: float = 25.0

    async def search(self, query: str, limit: int) -> list[SearchItem]:
        raise NotImplementedError

    async def close(self) -> None:
        return None


async def fetch_json(
    session: aiohttp.ClientSession,
    url: str,
    *,
    platform: str,
    method: str = "GET",
    **kwargs: Any,
) -> Any:
    """HTTP-запрос с переводом сетевых ошибок и кодов ответа в ProviderError."""
    kwargs.setdefault("timeout", aiohttp.ClientTimeout(total=20))
    try:
        async with session.request(method, url, **kwargs) as resp:
            if resp.status == 429:
                raise ProviderError(f"{platform}: превышен лимит запросов к API, попробуйте позже")
            if resp.status in (401, 403):
                body = await resp.text()
                log.error("%s API auth error %s: %s", platform, resp.status, body[:500])
                if "quota" in body.lower():
                    raise ProviderError(f"{platform}: исчерпана дневная квота API")
                raise ProviderError(f"{platform}: доступ к API отклонён (проверьте ключи)")
            if resp.status >= 500:
                raise ProviderError(f"{platform}: сервис временно недоступен")
            if resp.status >= 400:
                body = await resp.text()
                log.warning("%s API error %s: %s", platform, resp.status, body[:500])
                raise ProviderError(f"{platform}: ошибка запроса ({resp.status})")
            return await resp.json(content_type=None)
    except ProviderError:
        raise
    except asyncio.TimeoutError as exc:
        raise ProviderError(f"{platform}: сервис не ответил вовремя") from exc
    except (aiohttp.ClientError, ValueError) as exc:
        log.warning("%s request failed: %r", platform, exc)
        raise ProviderError(f"{platform}: не удалось связаться с сервисом") from exc
