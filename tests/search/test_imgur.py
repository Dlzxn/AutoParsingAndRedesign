import pytest

from app.search.base import ProviderError
from app.search.providers.imgur import PAGES, ImgurProvider, parse_gallery_item
from tests.conftest import load_fixture
from tests.search.fake_http import FakeSession

PREFIX = "https://api.imgur.com/3/gallery/search/"


def _video(id_, w, h, **extra):
    return {"id": id_, "type": "video/mp4", "width": w, "height": h, "mp4": f"https://i.imgur.com/{id_}.mp4", **extra}


def test_only_vertical_videos_from_albums_and_posts():
    album = {"is_album": True, "title": "Album", "link": "https://imgur.com/a/x",
             "images": [_video("v1", 480, 854), _video("h1", 1280, 720), {"id": "img", "type": "image/png"}]}
    single = {"is_album": False, "title": "Single", **_video("v2", 720, 1280)}
    assert [i.id for i in parse_gallery_item(album)] == ["v1"]
    assert [i.id for i in parse_gallery_item(single)] == ["v2"]
    item = parse_gallery_item(album)[0]
    assert item.url == item.preview_url == "https://i.imgur.com/v1.mp4"
    assert item.page_url == "https://imgur.com/a/x"
    assert item.thumbnail == "https://i.imgur.com/v1h.jpg"


def test_nsfw_and_broken_items_skipped():
    assert parse_gallery_item({"nsfw": True, "is_album": False, **_video("n", 480, 854)}) == []
    assert parse_gallery_item({"is_album": True, "images": None}) == []
    assert parse_gallery_item({"is_album": False, "type": "video/mp4", "width": 1, "height": 2}) == []


def test_real_fixture():
    items = [i for entry in load_fixture("imgur_search.json")["data"] for i in parse_gallery_item(entry)]
    assert items and all(i.height > i.width for i in items)


async def test_search_merges_pages_and_sends_client_id():
    session = FakeSession().get(PREFIX, payload=load_fixture("imgur_search.json"), repeat=True)
    items = await ImgurProvider(session, "cid").search("cats", 50)
    assert items
    assert len({i.url for i in items}) == len(items)
    assert len(session.calls) == PAGES
    assert {c.url for c in session.calls} == {f"{PREFIX}viral/all/{p}" for p in range(PAGES)}
    assert all(c.headers["Authorization"] == "Client-ID cid" for c in session.calls)


async def test_partial_page_failure_is_tolerated():
    session = FakeSession().get(PREFIX, payload=load_fixture("imgur_search.json"))
    session.get(PREFIX, status=500).get(PREFIX, status=500)
    assert await ImgurProvider(session, "cid").search("cats", 50)


async def test_all_pages_failed():
    session = FakeSession().get(PREFIX, status=429, repeat=True)
    with pytest.raises(ProviderError, match="лимит"):
        await ImgurProvider(session, "cid").search("cats", 50)


async def test_missing_client_id():
    with pytest.raises(ProviderError):
        await ImgurProvider(FakeSession(), "").search("cats", 10)
