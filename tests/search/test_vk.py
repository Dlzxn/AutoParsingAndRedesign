import pytest

from app.search.base import ProviderError
from app.search.providers import vk
from app.search.providers.vk import VK_API_URL, VKProvider, canonical_vk_url, items_from_links
from tests.search.fake_http import FakeSession


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://vk.com/video-123_456", "https://vk.com/video-123_456"),
        ("https://vk.com/video123_456?list=abc", "https://vk.com/video123_456"),
        ("https://m.vk.com/video-1_2", "https://vk.com/video-1_2"),
        ("https://vkvideo.ru/video-77_88", "https://vk.com/video-77_88"),
        ("https://vk.com/clip-5_6", "https://vk.com/video-5_6"),
        ("https://vk.ru/video-9_10", "https://vk.com/video-9_10"),
        ("https://vk.com/about", None),
        ("https://notvk.com/video-1_2", None),
        ("", None),
    ],
)
def test_canonical_vk_url(url, expected):
    assert canonical_vk_url(url) == expected


def test_items_from_google_links():
    links = [
        ("https://vk.com/video-1_2", "Котики\nВКонтакте · 1 мин"),
        ("https://www.google.com/url?q=https://vk.com/video-3_4&sa=U", "Через редирект"),
        ("https://vk.com/video-1_2?list=x", "Дубль"),
        ("https://youtube.com/watch?v=x", "Не VK"),
        ("https://vk.com/video5_6", ""),
    ]
    items = items_from_links(links, limit=10)
    assert [i.url for i in items] == ["https://vk.com/video-1_2", "https://vk.com/video-3_4", "https://vk.com/video5_6"]
    assert items[0].title == "Котики"
    assert items[2].title == "Клип VK"
    assert items[0].embed_url == "https://vk.com/video_ext.php?oid=-1&id=2&hd=1"
    assert len(items_from_links(links, limit=1)) == 1


async def test_api_mode_filters_long_videos():
    payload = {"response": {"items": [
        {"owner_id": -1, "id": 10, "title": "Короткий", "duration": 30, "player": "https://vk.com/video_ext.php?x",
         "image": [{"url": "small.jpg"}, {"url": "big.jpg"}]},
        {"owner_id": -1, "id": 11, "title": "Длинный", "duration": 900},
        {"owner_id": -1, "id": 12, "title": "Трансляция", "duration": 0},
    ]}}
    session = FakeSession().get(VK_API_URL, payload=payload)
    items = await VKProvider(session, access_token="tok", max_duration=180).search("котики", 50)
    assert [i.id for i in items] == ["-1_10"]
    assert items[0].url == "https://vk.com/video-1_10"
    assert items[0].thumbnail == "big.jpg"
    assert items[0].embed_url == "https://vk.com/video_ext.php?x"
    assert session.calls[0].params["access_token"] == "tok"
    assert session.calls[0].params["q"] == "котики"


async def test_api_error_is_reported():
    session = FakeSession().get(VK_API_URL, payload={"error": {"error_code": 5, "error_msg": "User authorization failed"}})
    with pytest.raises(ProviderError, match="authorization"):
        await VKProvider(session, access_token="bad").search("x", 10)


async def test_google_mode_runs_browser_in_thread(monkeypatch):
    calls = []

    def fake_links(query, chrome_binary, timeout):
        calls.append(query)
        return [("https://vk.com/video-1_2", "Клип")]

    monkeypatch.setattr(vk, "_google_links_sync", fake_links)
    items = await VKProvider(FakeSession(), access_token="").search("котики", 10)
    assert calls == ["котики"]
    assert [i.url for i in items] == ["https://vk.com/video-1_2"]


async def test_google_mode_error_propagates(monkeypatch):
    def captcha(*_):
        raise ProviderError("ВКонтакте: поисковик временно ограничил запросы")

    monkeypatch.setattr(vk, "_google_links_sync", captcha)
    with pytest.raises(ProviderError, match="ограничил"):
        await VKProvider(FakeSession()).search("x", 10)
