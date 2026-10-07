import asyncio

import pytest

from app.search.base import ProviderError
from app.search.providers.coub import MAX_PAGES, SEARCH_URL, CoubProvider, parse_coub
from tests.conftest import load_fixture
from tests.search.fake_http import FakeSession


def test_parse_coub_uses_share_video_with_sound():
    coub = load_fixture("coub_search.json")["coubs"][0]
    item = parse_coub(coub)
    assert item.url == coub["file_versions"]["share"]["default"]
    assert item.preview_url == item.url
    assert item.page_url == f"https://coub.com/view/{coub['permalink']}"
    assert item.thumbnail.endswith(".jpg") and "%{version}" not in item.thumbnail
    assert item.duration == coub["duration"]
    assert item.width and item.height


def test_parse_coub_without_share_is_skipped():
    assert parse_coub({"id": 1, "file_versions": {}}) is None
    assert parse_coub({"id": 1}) is None


async def test_search_fetches_all_pages_and_dedupes():
    page = load_fixture("coub_search.json")  # meta.total_pages = 2
    session = FakeSession().get(SEARCH_URL, payload=page).get(SEARCH_URL, payload=page)
    items = await CoubProvider(session).search("car", 100)
    assert len(items) == len(page["coubs"])
    assert len({i.url for i in items}) == len(items)
    assert [c.params["page"] for c in session.calls] == [1, 2]
    assert all(c.params["search_query"] == "car" for c in session.calls)


async def test_page_count_is_capped():
    page = dict(load_fixture("coub_search.json"), meta={"total_pages": 100})
    session = FakeSession().get(SEARCH_URL, payload=page, repeat=True)
    await CoubProvider(session).search("car", 1000)
    assert len(session.calls) == MAX_PAGES


async def test_failed_extra_pages_do_not_break_search():
    page = load_fixture("coub_search.json")
    session = FakeSession().get(SEARCH_URL, payload=page).get(SEARCH_URL, status=500)
    assert len(await CoubProvider(session).search("car", 100)) == len(page["coubs"])


async def test_limit():
    session = FakeSession().get(SEARCH_URL, payload=load_fixture("coub_search.json"))
    session.get(SEARCH_URL, payload={"coubs": []})
    assert len(await CoubProvider(session).search("car", 2)) == 2


async def test_unexpected_payload():
    session = FakeSession().get(SEARCH_URL, payload={"error": "oops"})
    with pytest.raises(ProviderError):
        await CoubProvider(session).search("car", 10)


async def test_empty_result():
    session = FakeSession().get(SEARCH_URL, payload={"coubs": [], "meta": {"total_pages": 0}})
    assert await CoubProvider(session).search("zzzz", 10) == []


async def test_timeout_is_reported():
    session = FakeSession().get(SEARCH_URL, exception=asyncio.TimeoutError())
    with pytest.raises(ProviderError, match="вовремя"):
        await CoubProvider(session).search("car", 10)
