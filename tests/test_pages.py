import re

import pytest

from app.db.models import Platform

PUBLIC = ["/", "/video", "/text", "/tariffs", "/features", "/login", "/registration"]
PROTECTED = ["/vk", "/youtube", "/coub", "/reddit", "/imgur", "/tumblr", "/editor", "/profile", "/text-editor"]


@pytest.mark.parametrize("path", PUBLIC)
async def test_public_pages(client, path):
    response = await client.get(path)
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "WebApp/FrontEnd" not in response.text  # старые пути к статике не остались


@pytest.mark.parametrize("path", PROTECTED)
async def test_protected_pages_redirect_to_login(client, path):
    response = await client.get(path)
    assert response.status_code == 303
    assert response.headers["location"] == f"/login?next={path}"


@pytest.mark.parametrize("path", PROTECTED)
async def test_protected_pages_for_user(user_client, path):
    response = await user_client.get(path)
    assert response.status_code == 200
    assert "user@example.com" in response.text  # меню профиля отрисовано сервером


async def test_all_static_assets_exist(user_client):
    """Каждая ссылка на /static/ в шаблонах указывает на существующий файл."""
    for path in PUBLIC + PROTECTED:
        html = (await user_client.get(path)).text
        for asset in set(re.findall(r'(/static/[^"\'?]+)', html)):
            response = await user_client.get(asset)
            assert response.status_code == 200, f"{path}: {asset}"


async def test_static_urls_are_versioned(client):
    html = (await client.get("/")).text
    assert re.search(r'/static/css/base\.css\?v=[0-9a-f]{10}', html)


async def test_search_page_config(user_client):
    html = (await user_client.get("/youtube")).text
    assert 'data-platform="yt"' in html and 'data-kind="video"' in html
    assert "data-clip-editor" in html  # редактор в модальном окне
    html = (await user_client.get("/tumblr")).text
    assert 'data-kind="text"' in html and "data-clip-editor" not in html


async def test_disabled_platform_shows_maintenance(user_client, db):
    (await db.get(Platform, "reddit")).enabled = False
    await db.commit()
    html = (await user_client.get("/reddit")).text
    assert "Технические работы" in html


async def test_editor_page_with_url(user_client):
    html = (await user_client.get("/editor", params={"url": "https://coub.com/view/x"})).text
    assert 'data-initial-url="https://coub.com/view/x"' in html


async def test_editor_page_escapes_url(user_client):
    html = (await user_client.get("/editor", params={"url": '"><script>alert(1)</script>'})).text
    assert "<script>alert(1)</script>" not in html


async def test_legacy_editor_url_redirects(client):
    response = await client.get("/VideoEditor")
    assert response.status_code == 301 and response.headers["location"] == "/editor"


async def test_404_html_and_json(client):
    page = await client.get("/no-such-page")
    assert page.status_code == 404 and "text/html" in page.headers["content-type"]
    api = await client.get("/api/no-such-endpoint")
    assert api.status_code == 404 and api.json() == {"detail": "Not Found"}


async def test_pricing_api(client):
    data = (await client.get("/api/user/pricing")).json()
    assert list(data) == ["free", "standard", "pro", "premium"]
    assert data["standard"] == {"price": 2000, "token_in_day": 5, "sale": True, "new_price": 50}


async def test_healthz(client):
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["db"] is True


async def test_security_headers(client):
    response = await client.get("/")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "SAMEORIGIN"


async def test_api_docs_hidden_outside_debug(client):
    assert (await client.get("/api/docs")).status_code == 404
