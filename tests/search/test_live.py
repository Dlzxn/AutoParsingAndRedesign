"""Проверка реальных API платформ. По умолчанию пропускаются.

Запуск (нужен .env с ключами):  pytest -m live
"""
import ssl

import aiohttp
import pytest
from dotenv import dotenv_values

from app.config import BASE_DIR, Settings
from app.search.factory import build_search_service

pytestmark = pytest.mark.live


@pytest.fixture
async def live_service():
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        pytest.skip("Нет файла .env с ключами платформ")
    # Значения из .env передаются явно: переменные окружения тестов содержат фиктивные ключи
    values = {k.lower(): v for k, v in dotenv_values(env_path).items() if v is not None}
    settings = Settings(**values)
    connector = aiohttp.TCPConnector(ssl=ssl.create_default_context())
    async with aiohttp.ClientSession(connector=connector) as session:
        yield build_search_service(settings, session), settings


@pytest.mark.parametrize("platform", ["yt", "coub", "reddit", "imgur", "tumblr"])
async def test_platform_returns_results(live_service, platform):
    service, _ = live_service
    items, _ = await service.search(platform, "cats")
    assert items, f"{platform}: пустая выдача"
    for item in items:
        assert item["url"].startswith("https://")
        assert item["title"]


async def test_vk(live_service):
    service, settings = live_service
    if not settings.vk_access_token:
        pytest.skip("VK_ACCESS_TOKEN не задан: поиск через Google нестабилен и не проверяется")
    items, _ = await service.search("vk", "котики")
    assert items
