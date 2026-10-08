import asyncio

import aiohttp
import pytest

from app.search.base import ProviderError
from app.search.providers.youtube import SEARCH_URL, VIDEOS_URL, YouTubeProvider, parse_iso_duration
from tests.conftest import load_fixture
from tests.search.fake_http import FakeSession


@pytest.mark.parametrize(
    ("value", "expected"),
    [("PT10S", 10), ("PT1M5S", 65), ("PT2H", 7200), ("PT1H2M3S", 3723), ("P1DT1S", 86401), ("PT", None),
     ("", None), ("garbage", None)],
)
def test_parse_iso_duration(value, expected):
    assert parse_iso_duration(value) == expected


async def test_search_returns_short_videos():
    session = FakeSession().get(SEARCH_URL, payload=load_fixture("youtube_search.json"))
    session.get(VIDEOS_URL, payload=load_fixture("youtube_videos.json"))
    items = await YouTubeProvider(session, "key", max_duration=60).search("cats", 50)

    assert len(items) == 3
    first = items[0]
    assert first.url == f"https://www.youtube.com/watch?v={first.id}"
    assert first.embed_url == f"https://www.youtube.com/embed/{first.id}"
    assert first.duration == 10
    assert first.thumbnail and first.thumbnail.startswith("https://")
    search_call = session.calls_to(SEARCH_URL)[0]
    assert search_call.params["q"] == "cats"
    assert search_call.params["videoDuration"] == "short"
    assert search_call.params["key"] == "key"
    assert session.calls_to(VIDEOS_URL)[0].params["id"] == ",".join(i.id for i in items)


async def test_long_videos_are_filtered_and_html_unescaped():
    search = {"items": [
        {"id": {"videoId": "short1"}, "snippet": {"title": "Tom &amp; Jerry &#39;cats&#39;"}},
        {"id": {"videoId": "long1"}, "snippet": {"title": "Long"}},
        {"id": {"videoId": "nodur"}, "snippet": {"title": "No duration"}},
        {"id": {"channelId": "chan"}, "snippet": {"title": "Not a video"}},
    ]}
    videos = {"items": [
        {"id": "short1", "contentDetails": {"duration": "PT59S"}},
        {"id": "long1", "contentDetails": {"duration": "PT3M1S"}},
    ]}
    session = FakeSession().get(SEARCH_URL, payload=search).get(VIDEOS_URL, payload=videos)
    items = await YouTubeProvider(session, "key", max_duration=180).search("x", 50)
    assert [i.id for i in items] == ["short1"]
    assert items[0].title == "Tom & Jerry 'cats'"


async def test_limit_is_respected():
    session = FakeSession().get(SEARCH_URL, payload=load_fixture("youtube_search.json"))
    session.get(VIDEOS_URL, payload=load_fixture("youtube_videos.json"))
    assert len(await YouTubeProvider(session, "key", max_duration=60).search("cats", 2)) == 2


async def test_empty_search_skips_details_request():
    session = FakeSession().get(SEARCH_URL, payload={"items": []})
    assert await YouTubeProvider(session, "key", 60).search("nothing", 10) == []
    assert session.calls_to(VIDEOS_URL) == []


async def test_quota_exceeded_is_reported():
    session = FakeSession().get(SEARCH_URL, status=403, body='{"error": {"errors": [{"reason": "quotaExceeded"}]}}')
    with pytest.raises(ProviderError, match="квота"):
        await YouTubeProvider(session, "key", 60).search("cats", 10)


async def test_invalid_key_is_reported():
    session = FakeSession().get(SEARCH_URL, status=400, body='{"error": {"message": "API key not valid"}}')
    with pytest.raises(ProviderError, match="400"):
        await YouTubeProvider(session, "key", 60).search("cats", 10)


async def test_missing_key():
    with pytest.raises(ProviderError, match="ключ"):
        await YouTubeProvider(FakeSession(), "", 60).search("cats", 10)


@pytest.mark.parametrize(
    ("route", "message"),
    [
        ({"status": 503}, "недоступен"),
        ({"exception": aiohttp.ClientConnectionError("boom")}, "связаться"),
        ({"exception": asyncio.TimeoutError()}, "вовремя"),
        ({"body": "<html>not json</html>"}, "связаться"),
    ],
)
async def test_transport_errors(route, message):
    session = FakeSession().get(SEARCH_URL, **route)
    with pytest.raises(ProviderError, match=message):
        await YouTubeProvider(session, "key", 60).search("cats", 10)
