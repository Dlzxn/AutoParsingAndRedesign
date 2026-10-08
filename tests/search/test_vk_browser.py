"""VK через Google + headless Chrome: логика работы с браузером на подменённом драйвере (без реального Chrome)."""
import pytest
from selenium.common.exceptions import TimeoutException, WebDriverException

from app.search.base import ProviderError
from app.search.providers import vk


class FakeElement:
    def __init__(self, fail=False):
        self.fail = fail
        self.clicked = False

    def click(self):
        if self.fail:
            raise WebDriverException("not clickable")
        self.clicked = True


class FakeDriver:
    instances: list["FakeDriver"] = []
    pages: list[list[tuple[str, str]]] = []  # что возвращает execute_script при каждом сборе ссылок
    has_results = True
    current_url = "https://www.google.com/search?q=x"
    page_source = "<html></html>"
    consent_buttons: list[FakeElement] = []

    def __init__(self, options=None):
        self.options = options
        self.visited: list[str] = []
        self.scrolls = 0
        self.quit_called = False
        self.collects = 0
        FakeDriver.instances.append(self)

    def set_page_load_timeout(self, timeout):
        self.timeout = timeout

    def execute_cdp_cmd(self, cmd, params):
        self.cdp = cmd

    def get(self, url):
        self.visited.append(url)

    def find_elements(self, by, value):
        return list(self.consent_buttons)

    def execute_script(self, script, *args):
        if "scrollTo" in script:
            self.scrolls += 1
            return None
        page = self.pages[min(self.collects, len(self.pages) - 1)]
        self.collects += 1
        return page

    def implicitly_wait(self, seconds):
        pass

    def quit(self):
        self.quit_called = True


class FakeWait:
    def __init__(self, driver, timeout):
        self.driver = driver

    def until(self, condition):
        if not self.driver.has_results:
            raise TimeoutException()
        return True


@pytest.fixture
def browser(monkeypatch):
    from selenium import webdriver
    from selenium.webdriver.support import ui

    FakeDriver.instances = []
    FakeDriver.has_results = True
    FakeDriver.current_url = "https://www.google.com/search?q=x"
    FakeDriver.page_source = "<html></html>"
    FakeDriver.consent_buttons = []
    FakeDriver.pages = [[("https://vk.com/video-1_2", "Клип 1")]]
    monkeypatch.setattr(webdriver, "Chrome", FakeDriver)
    monkeypatch.setattr(ui, "WebDriverWait", FakeWait)
    return FakeDriver


def test_collects_links_and_scrolls_until_enough(browser):
    few = [(f"https://vk.com/video-1_{i}", f"Клип {i}") for i in range(5)]
    many = [(f"https://vk.com/video-1_{i}", f"Клип {i}") for i in range(25)]
    browser.pages = [few, few, many]
    links = vk._google_links_sync("котики", "", 30)
    driver = browser.instances[0]
    assert len(links) == 25
    assert driver.scrolls == 2  # прокрутили дважды, на третьем сборе ссылок хватило
    assert driver.quit_called  # браузер всегда закрывается
    assert "q=%D0%BA%D0%BE%D1%82%D0%B8%D0%BA%D0%B8+%D0%B2%D0%BA+%D0%BA%D0%BB%D0%B8%D0%BF%D1%8B" in driver.visited[0]
    assert driver.timeout == 30


def test_consent_dialog_is_dismissed(browser):
    first, second = FakeElement(fail=True), FakeElement()
    browser.consent_buttons = [first, second]
    vk._google_links_sync("x", "", 30)
    assert second.clicked  # первая кнопка не кликнулась — пробуем следующую


def test_captcha_is_reported(browser):
    browser.has_results = False
    browser.current_url = "https://www.google.com/sorry/index"
    with pytest.raises(ProviderError, match="ограничил"):
        vk._google_links_sync("x", "", 30)
    assert browser.instances[0].quit_called


def test_no_results_without_captcha(browser):
    browser.has_results = False
    assert vk._google_links_sync("x", "", 30) == []


def test_chrome_start_failure(monkeypatch):
    from selenium import webdriver

    def broken(options=None):
        raise WebDriverException("chrome not found")

    monkeypatch.setattr(webdriver, "Chrome", broken)
    with pytest.raises(ProviderError, match="временно недоступен"):
        vk._google_links_sync("x", "", 30)


def test_custom_chrome_binary(browser):
    vk._google_links_sync("x", "/opt/chromium/chrome", 30)
    assert browser.instances[0].options.binary_location == "/opt/chromium/chrome"


async def test_provider_limits_parallel_browsers(browser, monkeypatch):
    import asyncio
    import threading

    active, peak, lock = [0], [0], threading.Lock()

    def slow_links(query, chrome_binary, timeout):
        import time

        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        time.sleep(0.1)
        with lock:
            active[0] -= 1
        return [("https://vk.com/video-1_2", "Клип")]

    monkeypatch.setattr(vk, "_google_links_sync", slow_links)
    provider = vk.VKProvider(session=None, max_browsers=2)
    await asyncio.gather(*(provider.search(f"q{i}", 10) for i in range(6)))
    assert peak[0] == 2  # одновременно не больше двух браузеров
