"""Поиск клипов VK.

Два режима:
* VK API (video.search) — если задан VK_ACCESS_TOKEN (пользовательский токен). Быстро и стабильно.
* Google + headless Chrome — запасной вариант без токена: ищем ссылки vk.com/video в выдаче Google.
  Браузер работает в отдельном потоке, число одновременно запущенных браузеров ограничено.
"""
import asyncio
import logging
import re
import urllib.parse

import aiohttp

from app.search.base import ProviderError, SearchItem, SearchProvider, fetch_json

log = logging.getLogger(__name__)

VK_API_URL = "https://api.vk.com/method/video.search"
VK_API_VERSION = "5.199"
GOOGLE_URL = "https://www.google.com/search"

_VK_VIDEO_RE = re.compile(r"(?:^|[/.])(?:vk\.com|vk\.ru|vkvideo\.ru)/(?:video|clip)(-?\d+)_(\d+)")


def canonical_vk_url(url: str) -> str | None:
    match = _VK_VIDEO_RE.search(url or "")
    if not match:
        return None
    return f"https://vk.com/video{match.group(1)}_{match.group(2)}"


def vk_embed_url(owner_id: str, video_id: str) -> str:
    return f"https://vk.com/video_ext.php?oid={owner_id}&id={video_id}&hd=1"


def items_from_links(links: list[tuple[str, str]], limit: int) -> list[SearchItem]:
    """Превращает пары (href, текст ссылки) из выдачи Google в результаты поиска."""
    results: list[SearchItem] = []
    seen: set[str] = set()
    for href, text in links:
        # Google иногда отдаёт ссылки-редиректы вида /url?q=<target>
        parsed = urllib.parse.urlparse(href)
        if parsed.path == "/url":
            href = urllib.parse.parse_qs(parsed.query).get("q", [href])[0]
        url = canonical_vk_url(href)
        if not url or url in seen:
            continue
        seen.add(url)
        owner_id, video_id = url.rsplit("video", 1)[1].split("_")
        title = (text or "").strip().split("\n")[0][:120] or "Клип VK"
        results.append(
            SearchItem(id=f"{owner_id}_{video_id}", title=title, url=url, page_url=url,
                       embed_url=vk_embed_url(owner_id, video_id))
        )
        if len(results) >= limit:
            break
    return results


def _google_links_sync(query: str, chrome_binary: str, timeout: float) -> list[tuple[str, str]]:
    from selenium import webdriver
    from selenium.common.exceptions import TimeoutException, WebDriverException
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as ec
    from selenium.webdriver.support.ui import WebDriverWait

    options = webdriver.ChromeOptions()
    for arg in ("--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
                "--window-size=1920,1080", "--disable-blink-features=AutomationControlled", "--lang=ru-RU"):
        options.add_argument(arg)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    if chrome_binary:
        options.binary_location = chrome_binary

    url = GOOGLE_URL + "?" + urllib.parse.urlencode({"q": f"{query} вк клипы", "udm": 39, "num": 30, "hl": "ru"})
    try:
        driver = webdriver.Chrome(options=options)
    except WebDriverException as exc:
        log.error("Chrome start failed: %s", exc.msg if hasattr(exc, "msg") else exc)
        raise ProviderError("ВКонтакте: поиск временно недоступен") from exc
    try:
        driver.set_page_load_timeout(timeout)
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
        )
        driver.get(url)
        # Окно согласия с cookie (встречается в ЕС)
        for button in driver.find_elements(By.XPATH, "//button[.//div[contains(., 'Отклонить') or contains(., 'Reject')]]"):
            try:
                button.click()
                break
            except WebDriverException:
                pass
        try:
            WebDriverWait(driver, 10).until(
                ec.presence_of_element_located((By.CSS_SELECTOR, "a[href*='vk.com/video'], a[href*='vkvideo.ru/']"))
            )
        except TimeoutException:
            if "sorry" in driver.current_url or "captcha" in driver.page_source.lower():
                raise ProviderError("ВКонтакте: поисковик временно ограничил запросы, попробуйте позже")
            return []
        links: list[tuple[str, str]] = []
        for _ in range(3):
            links = driver.execute_script(
                "return Array.from(document.querySelectorAll('#search a[href], #rso a[href]'))"
                ".map(a => [a.href, a.innerText || a.getAttribute('aria-label') || ''])"
            )
            if len({canonical_vk_url(h) for h, _ in links} - {None}) >= 20:
                break
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            driver.implicitly_wait(1.5)
        return links
    finally:
        driver.quit()


class VKProvider(SearchProvider):
    key = "vk"
    title = "ВКонтакте"

    def __init__(
        self,
        session: aiohttp.ClientSession,
        access_token: str = "",
        max_duration: int = 180,
        chrome_binary: str = "",
        max_browsers: int = 2,
        timeout: float = 60.0,
    ) -> None:
        self.session = session
        self.access_token = access_token
        self.max_duration = max_duration
        self.chrome_binary = chrome_binary
        self._browsers = asyncio.Semaphore(max(1, max_browsers))
        self.timeout = timeout

    async def search(self, query: str, limit: int) -> list[SearchItem]:
        if self.access_token:
            return await self._search_api(query, limit)
        return await self._search_google(query, limit)

    async def _search_api(self, query: str, limit: int) -> list[SearchItem]:
        data = await fetch_json(
            self.session,
            VK_API_URL,
            platform=self.title,
            params={"q": query, "count": 200, "adult": 0, "sort": 2, "access_token": self.access_token,
                    "v": VK_API_VERSION},
        )
        if "error" in data:
            err = data["error"]
            log.error("VK API error: %s", err)
            raise ProviderError(f"ВКонтакте: ошибка API ({err.get('error_msg', 'unknown')})")
        results = []
        for video in (data.get("response") or {}).get("items") or []:
            duration = video.get("duration") or 0
            if not duration or duration > self.max_duration:
                continue
            owner_id, video_id = video.get("owner_id"), video.get("id")
            images = video.get("image") or []
            url = f"https://vk.com/video{owner_id}_{video_id}"
            results.append(
                SearchItem(
                    id=f"{owner_id}_{video_id}",
                    title=video.get("title") or "Клип VK",
                    url=url,
                    page_url=url,
                    embed_url=video.get("player") or vk_embed_url(str(owner_id), str(video_id)),
                    thumbnail=images[-1].get("url") if images else None,
                    duration=duration,
                    width=video.get("width"),
                    height=video.get("height"),
                )
            )
            if len(results) >= limit:
                break
        return results

    async def _search_google(self, query: str, limit: int) -> list[SearchItem]:
        async with self._browsers:
            links = await asyncio.to_thread(_google_links_sync, query, self.chrome_binary, self.timeout)
        return items_from_links(links, limit)
