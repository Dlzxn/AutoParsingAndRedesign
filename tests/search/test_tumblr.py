import pytest

from app.search.base import ProviderError
from app.search.providers.tumblr import TAGGED_URL, TumblrProvider, html_to_text, parse_post
from tests.conftest import load_fixture
from tests.search.fake_http import FakeSession


def _post(i: int, ts: int, **extra) -> dict:
    return {"type": "text", "id": i, "id_string": str(i), "post_url": f"https://b.tumblr.com/post/{i}",
            "timestamp": ts, "body": f"<p>Post {i}</p>", "blog_name": "b", "tags": ["t"], **extra}


def test_html_to_text():
    html = "<p>Привет,&nbsp;<b>мир</b></p><p></p><ul><li>один</li><li>два</li></ul>"
    text = html_to_text(html)
    assert "Привет" in text and "мир" in text and "один\nдва" in text
    assert "<" not in text


def test_parse_post_fixture():
    for post in load_fixture("tumblr_tagged.json")["response"]:
        item = parse_post(post)
        assert item is not None
        assert item.kind == "text"
        assert item.url == post["post_url"]
        assert item.text and "<img" not in item.text
        assert item.tags == post["tags"]
        assert item.published_at == post["timestamp"]


@pytest.mark.parametrize("post", [{"type": "photo"}, {"type": "text", "body": ""}, {"type": "text", "body": "<p></p>"}])
def test_parse_post_skips(post):
    assert parse_post(post) is None


def test_title_falls_back_to_blog_name():
    assert parse_post(_post(1, 100, title="")).title == "b"


async def test_backup_key_used_when_primary_fails():
    session = FakeSession().get(TAGGED_URL, status=429).get(TAGGED_URL, payload={"response": [_post(1, 100)]})
    items = await TumblrProvider(session, ["k1", "k2"]).search("cats", 10)
    assert [i.id for i in items] == ["1"]
    assert [c.params["api_key"] for c in session.calls] == ["k1", "k2"]
    assert session.calls[0].params["tag"] == "cats"


async def test_all_keys_failed():
    session = FakeSession().get(TAGGED_URL, status=401, repeat=True)
    with pytest.raises(ProviderError):
        await TumblrProvider(session, ["k1", "k2"]).search("cats", 10)


async def test_pagination_uses_timestamp():
    page1 = [_post(i, 1000 - i) for i in range(20)]
    page2 = [_post(100 + i, 500 - i) for i in range(3)]
    session = FakeSession().get(TAGGED_URL, payload={"response": page1}).get(TAGGED_URL, payload={"response": page2})
    items = await TumblrProvider(session, ["k"]).search("cats", 100)
    assert len(items) == 23
    assert "before" not in session.calls[0].params
    assert session.calls[1].params["before"] == page1[-1]["timestamp"]


async def test_limit_stops_pagination():
    page = [_post(i, 1000 - i) for i in range(20)]
    session = FakeSession().get(TAGGED_URL, payload={"response": page}, repeat=True)
    assert len(await TumblrProvider(session, ["k"]).search("cats", 5)) == 5
    assert len(session.calls) == 1


async def test_no_keys():
    with pytest.raises(ProviderError):
        await TumblrProvider(FakeSession(), []).search("cats", 10)
