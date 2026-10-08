import pytest

from app.db.models import Platform
from app.search.base import ProviderError, SearchItem
from tests.search.test_service import FakeProvider


@pytest.fixture
def fake_provider(app):
    provider = FakeProvider()
    provider.key = "coub"
    service = app.state.search
    service.providers["coub"] = provider
    service.cache.clear()
    return provider


async def test_requires_login(client, fake_provider):
    response = await client.get("/api/search/coub", params={"q": "cats"})
    assert response.status_code == 401
    assert fake_provider.calls == []


async def test_search_ok(user_client, fake_provider):
    response = await user_client.get("/api/search/coub", params={"q": "cats"})
    assert response.status_code == 200
    data = response.json()
    assert data["platform"] == "coub"
    assert len(data["items"]) == 5
    assert data["cached"] is False


async def test_unknown_platform(user_client):
    response = await user_client.get("/api/search/myspace", params={"q": "cats"})
    assert response.status_code == 404


@pytest.mark.parametrize("query", ["", "a", "x" * 101])
async def test_query_validation(user_client, fake_provider, query):
    response = await user_client.get("/api/search/coub", params={"q": query})
    assert response.status_code == 422
    assert "Запрос" in response.json()["detail"]


async def test_whitespace_query_rejected(user_client, fake_provider):
    response = await user_client.get("/api/search/coub", params={"q": "   "})
    assert response.status_code == 422


async def test_disabled_platform(user_client, fake_provider, db):
    platform = await db.get(Platform, "coub")
    platform.enabled = False
    await db.commit()
    response = await user_client.get("/api/search/coub", params={"q": "cats"})
    assert response.status_code == 503
    assert "технические работы" in response.json()["detail"]
    assert fake_provider.calls == []


async def test_seen_clips_are_hidden_per_user(user_client, other_client, fake_provider):
    response = await user_client.post("/api/history", json={"url": "https://x/1", "platform": "coub"})
    assert response.status_code == 204
    mine = (await user_client.get("/api/search/coub", params={"q": "cats"})).json()["items"]
    theirs = (await other_client.get("/api/search/coub", params={"q": "cats"})).json()["items"]
    assert "https://x/1" not in [i["url"] for i in mine]
    assert "https://x/1" in [i["url"] for i in theirs]


async def test_history_is_idempotent(user_client):
    for _ in range(3):
        assert (await user_client.post("/api/history", json={"url": "https://x/1"})).status_code == 204


async def test_history_requires_login(client):
    assert (await client.post("/api/history", json={"url": "https://x/1"})).status_code == 401


async def test_provider_error_returns_502(user_client, app):
    app.state.search.providers["coub"] = FakeProvider(error=ProviderError("Coub: сервис временно недоступен"))
    response = await user_client.get("/api/search/coub", params={"q": "cats"})
    assert response.status_code == 502
    assert response.json()["detail"] == "Coub: сервис временно недоступен"


async def test_rate_limit(user_client, fake_provider):
    from app.search.router import search_limiter

    search_limiter.limit = 3
    try:
        codes = [(await user_client.get("/api/search/coub", params={"q": f"q{i}x"})).status_code for i in range(4)]
    finally:
        search_limiter.limit = 30
    assert codes == [200, 200, 200, 429]


async def test_anonymous_search_when_auth_disabled(client, fake_provider, settings):
    settings.auth_required = False
    try:
        response = await client.get("/api/search/coub", params={"q": "cats"})
    finally:
        settings.auth_required = True
    assert response.status_code == 200


async def test_text_platform_items(user_client, app):
    provider = FakeProvider(items=[SearchItem(id="1", title="Post", url="https://t/1", kind="text", text="Body",
                                              tags=["a"], published_at=100)])
    app.state.search.providers["tumblr"] = provider
    items = (await user_client.get("/api/search/tumblr", params={"q": "cats"})).json()["items"]
    assert items == [{"id": "1", "title": "Post", "url": "https://t/1", "kind": "text", "text": "Body",
                      "published_at": 100, "tags": ["a"]}]
