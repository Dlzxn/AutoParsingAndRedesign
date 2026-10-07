import base64

import pytest

from app.search.base import ProviderError
from app.search.providers.reddit import SEARCH_URL, TOKEN_URL, RedditProvider, parse_post
from tests.conftest import load_fixture
from tests.search.fake_http import FakeSession


def _provider(session):
    return RedditProvider(session, "id", "secret", "test-agent")


def _video_post(**overrides) -> dict:
    post = {
        "id": "abc", "title": "Cat &amp; dog", "permalink": "/r/cats/comments/abc/cat/", "is_video": True,
        "over_18": False, "subreddit_name_prefixed": "r/cats",
        "media": {"reddit_video": {"fallback_url": "https://v.redd.it/x/CMAF_720.mp4", "duration": 12,
                                   "width": 720, "height": 1280}},
    }
    post.update(overrides)
    return post


def _listing(*posts, after=None) -> dict:
    return {"data": {"children": [{"data": p} for p in posts], "after": after}}


def test_parse_post_uses_permalink_for_audio():
    item = parse_post(_video_post())
    assert item.url == "https://www.reddit.com/r/cats/comments/abc/cat/"
    assert item.preview_url == "https://v.redd.it/x/CMAF_720.mp4"
    assert item.title == "Cat & dog"
    assert (item.width, item.height, item.duration) == (720, 1280, 12)


@pytest.mark.parametrize("overrides", [{"is_video": False}, {"over_18": True}, {"media": None}, {"permalink": None}])
def test_parse_post_skips_unsuitable(overrides):
    assert parse_post(_video_post(**overrides)) is None


def test_parse_real_fixture():
    children = load_fixture("reddit_search.json")["data"]["children"]
    parsed = [parse_post(c["data"]) for c in children]
    assert sum(p is not None for p in parsed) == 2  # в фикстуре 2 видео и 2 обычных поста


async def test_search_and_token_caching():
    listing = load_fixture("reddit_search.json")
    session = FakeSession().post(TOKEN_URL, payload={"access_token": "tok", "expires_in": 3600})
    session.get(SEARCH_URL, payload=listing, repeat=True)
    provider = _provider(session)
    first = await provider.search("cats", 50)
    await provider.search("dogs", 50)

    token_calls = session.calls_to(TOKEN_URL)
    assert len(token_calls) == 1  # токен запрошен один раз и переиспользуется
    expected = base64.b64encode(b"id:secret").decode()
    assert token_calls[0].headers["Authorization"] == f"Basic {expected}"
    search_call = session.calls_to(SEARCH_URL)[0]
    assert search_call.headers["Authorization"] == "bearer tok"
    assert search_call.params["include_over_18"] == "off"
    assert search_call.params["q"] == "cats"
    assert len(first) == 2


async def test_pagination_follows_after():
    session = FakeSession().post(TOKEN_URL, payload={"access_token": "tok"})
    session.get(SEARCH_URL, payload=_listing(_video_post(id="1", permalink="/r/a/1/"), after="t3_1"))
    session.get(SEARCH_URL, payload=_listing(_video_post(id="2", permalink="/r/a/2/")))
    items = await _provider(session).search("cats", 50)
    assert [i.id for i in items] == ["1", "2"]
    assert session.calls_to(SEARCH_URL)[1].params["after"] == "t3_1"


async def test_duplicates_removed():
    post = _video_post()
    session = FakeSession().post(TOKEN_URL, payload={"access_token": "tok"})
    session.get(SEARCH_URL, payload=_listing(post, post))
    assert len(await _provider(session).search("cats", 50)) == 1


async def test_bad_credentials():
    session = FakeSession().post(TOKEN_URL, status=401, body="unauthorized")
    with pytest.raises(ProviderError, match="ключ"):
        await _provider(session).search("cats", 10)


async def test_token_missing_in_response():
    session = FakeSession().post(TOKEN_URL, payload={"error": "invalid_grant"})
    with pytest.raises(ProviderError, match="токен"):
        await _provider(session).search("cats", 10)


async def test_missing_credentials():
    with pytest.raises(ProviderError):
        await RedditProvider(FakeSession(), "", "", "ua").search("cats", 10)


async def test_rate_limited():
    session = FakeSession().post(TOKEN_URL, payload={"access_token": "tok"}).get(SEARCH_URL, status=429)
    with pytest.raises(ProviderError, match="лимит"):
        await _provider(session).search("cats", 10)
