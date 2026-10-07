import asyncio

import pytest

from app.search.base import ProviderError, SearchItem, SearchProvider
from app.search.service import RESULT_LIMIT, SearchService, TTLCache


class FakeProvider(SearchProvider):
    key = "fake"
    title = "Fake"

    def __init__(self, items=None, delay=0.0, error: Exception | None = None):
        self.items = items if items is not None else [SearchItem(id=str(i), title=f"#{i}", url=f"https://x/{i}") for i in range(5)]
        self.delay = delay
        self.error = error
        self.calls: list[str] = []
        self.timeout = 0.5

    async def search(self, query, limit):
        self.calls.append(query)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return self.items[:limit]


def make(provider, ttl=60.0, timeout=0.5):
    return SearchService({"fake": provider}, cache_ttl=ttl, default_timeout=timeout)


async def test_results_are_dicts_without_empty_fields():
    items, cached = await make(FakeProvider()).search("fake", "cats")
    assert cached is False
    assert items[0] == {"id": "0", "title": "#0", "url": "https://x/0", "kind": "video"}


async def test_cache_and_query_normalization():
    provider = FakeProvider()
    service = make(provider)
    await service.search("fake", "  Cats   Dogs ")
    _, cached = await service.search("fake", "cats dogs")
    assert cached is True
    assert provider.calls == ["cats dogs"]


async def test_cache_expires():
    provider = FakeProvider()
    service = make(provider, ttl=0.0)
    await service.search("fake", "cats")
    await asyncio.sleep(0.01)
    await service.search("fake", "cats")
    assert len(provider.calls) == 2


async def test_seen_urls_are_excluded():
    items, _ = await make(FakeProvider()).search("fake", "cats", exclude_urls={"https://x/0", "https://x/3"})
    assert [i["id"] for i in items] == ["1", "2", "4"]


async def test_result_limit():
    many = [SearchItem(id=str(i), title="t", url=f"https://x/{i}") for i in range(200)]
    items, _ = await make(FakeProvider(items=many)).search("fake", "cats")
    assert len(items) == RESULT_LIMIT


async def test_concurrent_identical_requests_hit_provider_once():
    provider = FakeProvider(delay=0.1)
    service = make(provider)
    results = await asyncio.gather(*(service.search("fake", "cats") for _ in range(5)))
    assert provider.calls == ["cats"]
    assert all(len(items) == 5 for items, _ in results)


async def test_timeout_becomes_provider_error():
    with pytest.raises(ProviderError, match="вовремя"):
        await make(FakeProvider(delay=2), timeout=0.05).search("fake", "cats")


async def test_provider_error_is_not_cached():
    provider = FakeProvider(error=ProviderError("Fake: сломалось"))
    service = make(provider)
    for _ in range(2):
        with pytest.raises(ProviderError, match="сломалось"):
            await service.search("fake", "cats")
    assert len(provider.calls) == 2


async def test_unexpected_exception_is_wrapped():
    with pytest.raises(ProviderError, match="внутренняя ошибка"):
        await make(FakeProvider(error=KeyError("boom"))).search("fake", "cats")


async def test_concurrent_waiters_get_the_error():
    provider = FakeProvider(delay=0.05, error=ProviderError("Fake: недоступно"))
    service = make(provider)
    results = await asyncio.gather(*(service.search("fake", "cats") for _ in range(3)), return_exceptions=True)
    assert all(isinstance(r, ProviderError) for r in results)
    assert provider.calls == ["cats"]


def test_ttl_cache_evicts_oldest():
    cache = TTLCache(ttl=60, max_entries=2)
    cache.set(("a",), [])
    cache.set(("b",), [])
    cache.get(("a",))  # a стал самым свежим
    cache.set(("c",), [])
    assert cache.get(("b",)) is None
    assert cache.get(("a",)) == [] and cache.get(("c",)) == []
