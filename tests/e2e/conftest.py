"""Сквозные браузерные тесты: живой сервер в отдельном потоке + headless Chrome (Selenium).

Внешние площадки подменяются (поиск и скачивание), всё остальное — настоящее: БД, ffmpeg, фронтенд.
Пропускаются, если нет Chrome или ffmpeg.
"""
import asyncio
import shutil
import socket
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn

from tests.conftest import HAS_FFMPEG

CHROME = any(
    Path(p).exists()
    for p in (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/Applications/Google Chrome.app",
    )
) or shutil.which("chrome") or shutil.which("google-chrome") or shutil.which("chromium")


def pytest_collection_modifyitems(items):
    for item in items:
        if "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
            if not CHROME:
                item.add_marker(pytest.mark.skip(reason="Chrome не установлен"))
            elif not HAS_FFMPEG:
                item.add_marker(pytest.mark.skip(reason="ffmpeg не установлен"))


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class LiveServer:
    def __init__(self, app, port: int) -> None:
        self.app = app
        self.url = f"http://127.0.0.1:{port}"
        self.server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=lambda: self.loop.run_until_complete(self.server.serve()), daemon=True)

    def run(self, coro):
        """Выполнить корутину в цикле событий сервера (там живут БД-подключения приложения)."""
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(30)

    def start(self) -> None:
        self.thread.start()
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                if httpx.get(f"{self.url}/healthz", timeout=1).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.2)
        raise RuntimeError("Live server did not start")

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=30)
        if not self.thread.is_alive():
            self.loop.close()


@pytest.fixture
def live(settings):
    from app.main import create_app

    server = LiveServer(create_app(settings), _free_port())
    server.start()
    yield server
    server.stop()  # БД закрывается в lifespan приложения


@pytest.fixture
def account(live):
    """Зарегистрированный пользователь: возвращает cookie сессии."""
    with httpx.Client(base_url=live.url) as c:
        assert c.post("/api/registration", json={"identity": "e2e@example.com", "password": "secret123"}).status_code == 201
        return c.cookies["session"]


@pytest.fixture
def browser():
    from selenium import webdriver

    options = webdriver.ChromeOptions()
    for arg in ("--headless=new", "--window-size=1440,1000", "--autoplay-policy=no-user-gesture-required",
                "--mute-audio"):
        options.add_argument(arg)
    options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(0)
    yield driver
    driver.quit()


@pytest.fixture
def mobile_browser():
    from selenium import webdriver

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_experimental_option("mobileEmulation", {"deviceMetrics": {"width": 390, "height": 844, "pixelRatio": 2}})
    driver = webdriver.Chrome(options=options)
    yield driver
    driver.quit()


class Page:
    """Небольшие помощники поверх Selenium."""

    def __init__(self, driver, base_url: str) -> None:
        self.d = driver
        self.base = base_url

    def open(self, path: str) -> "Page":
        self.d.get(self.base + path)
        return self

    def login(self, session_cookie: str) -> "Page":
        self.d.get(self.base + "/static/img/logo.svg")
        self.d.add_cookie({"name": "session", "value": session_cookie, "path": "/"})
        return self

    def q(self, css: str):
        from selenium.webdriver.common.by import By

        return self.d.find_element(By.CSS_SELECTOR, css)

    def qa(self, css: str):
        from selenium.webdriver.common.by import By

        return self.d.find_elements(By.CSS_SELECTOR, css)

    def click(self, css: str) -> None:
        self.d.execute_script("arguments[0].scrollIntoView({block:'center'}); arguments[0].click()", self.q(css))

    def js(self, script: str, *args):
        return self.d.execute_script(script, *args)

    def wait(self, condition, timeout: float = 30, message: str = ""):
        from selenium.webdriver.support.ui import WebDriverWait

        return WebDriverWait(self.d, timeout, poll_frequency=0.1).until(lambda _: condition(), message)

    def visible(self, css: str) -> bool:
        els = self.qa(css)
        return bool(els) and els[0].is_displayed()

    def console_errors(self) -> list[str]:
        return [e["message"] for e in self.d.get_log("browser")
                if e["level"] == "SEVERE" and "favicon" not in e["message"]]


@pytest.fixture
def page(browser, live):
    return Page(browser, live.url)


@pytest.fixture
def fake_download(monkeypatch, media_dir):
    """Подмена скачивания по ссылке: отдаёт тестовое видео; можно заставить первые N вызовов падать."""
    from app.media import fetch
    from app.media.ffmpeg import MediaError

    state = {"fail": 0, "calls": 0}

    def download(url, dest_dir, options, on_progress=None):
        state["calls"] += 1
        if state["fail"] > 0:
            state["fail"] -= 1
            raise MediaError("Видео недоступно или удалено")
        if on_progress:
            on_progress(0.5)
        dest_dir.mkdir(parents=True, exist_ok=True)
        target = dest_dir / "source.mp4"
        shutil.copy(media_dir / "landscape.mp4", target)
        return fetch.DownloadResult(target, "Тестовый ролик")

    monkeypatch.setattr(fetch, "download", download)
    return state
