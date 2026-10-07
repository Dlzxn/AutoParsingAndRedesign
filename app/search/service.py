import asyncio
import logging
import time
from collections import OrderedDict

from app.search.base import ProviderError, SearchItem, SearchProvider

log = logging.getLogger(__name__)

FETCH_LIMIT = 120  # сколько берём у платформы (с запасом на фильтрацию просмотренного)
RESULT_LIMIT = 50  # сколько отдаём пользователю


class TTLCache:
    def __init__(self, ttl: float, max_entries: int = 500) -> None:
        self.ttl = ttl
        self.max_entries = max_entries
        self._data: OrderedDict[tuple, tuple[float, list[SearchItem]]] = OrderedDict()

    def get(self, key: tuple) -> list[SearchItem] | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        stored_at, value = entry
        if time.monotonic() - stored_at > self.ttl:
            del self._data[key]
            return None
        self._data.move_to_end(key)
        return value

    def set(self, key: tuple, value: list[SearchItem]) -> None:
        self._data[key] = (time.monotonic(), value)
        self._data.move_to_end(key)
        while len(self._data) > self.max_entries:
            self._data.popitem(last=False)

    def clear(self) -> None:
        self._data.clear()


class SearchService:
    """Поиск по платформам с кэшем, таймаутом и объединением одинаковых одновременных запросов."""

    def __init__(self, providers: dict[str, SearchProvider], cache_ttl: float, default_timeout: float) -> None:
        self.providers = providers
        self.cache = TTLCache(cache_ttl)
        self.default_timeout = default_timeout
        self._inflight: dict[tuple, asyncio.Future] = {}

    def has_platform(self, key: str) -> bool:
        return key in self.providers

    async def _fetch(self, platform: str, query: str) -> list[SearchItem]:
        provider = self.providers[platform]
        timeout = max(provider.timeout, self.default_timeout)
        started = time.monotonic()
        try:
            items = await asyncio.wait_for(provider.search(query, FETCH_LIMIT), timeout=timeout)
        except asyncio.TimeoutError as exc:
            log.warning("Search timeout: platform=%s query=%r", platform, query)
            raise ProviderError(f"{provider.title}: платформа не ответила вовремя, попробуйте ещё раз") from exc
        except ProviderError:
            raise
        except Exception as exc:  # неожиданная ошибка разбора ответа и т.п.
            log.exception("Search failed: platform=%s query=%r", platform, query)
            raise ProviderError(f"{provider.title}: внутренняя ошибка поиска") from exc
        log.info("Search ok: platform=%s query=%r found=%d in %.2fs", platform, query, len(items),
                 time.monotonic() - started)
        return items

    async def _fetch_cached(self, platform: str, query: str) -> tuple[list[SearchItem], bool]:
        key = (platform, query)
        cached = self.cache.get(key)
        if cached is not None:
            return cached, True
        if key in self._inflight:
            return await asyncio.shield(self._inflight[key]), True

        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._inflight[key] = future
        try:
            items = await self._fetch(platform, query)
        except BaseException as exc:
            if not future.done():
                future.set_exception(exc)
                future.exception()  # помечаем как обработанное, если никто не ждёт
            raise
        else:
            self.cache.set(key, items)
            future.set_result(items)
            return items, False
        finally:
            self._inflight.pop(key, None)

    async def search(self, platform: str, query: str, exclude_urls: set[str] | None = None) -> tuple[list[dict], bool]:
        query = " ".join(query.split()).lower()
        items, cached = await self._fetch_cached(platform, query)
        exclude = exclude_urls or set()
        results = [item.to_dict() for item in items if item.url not in exclude][:RESULT_LIMIT]
        return results, cached

    async def close(self) -> None:
        for provider in self.providers.values():
            await provider.close()
