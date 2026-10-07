import asyncio
import base64
import html
import time

import aiohttp

from app.search.base import ProviderError, SearchItem, SearchProvider, fetch_json

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
SEARCH_URL = "https://oauth.reddit.com/r/all/search"
MAX_PAGES = 3


def parse_post(post: dict) -> SearchItem | None:
    if not post.get("is_video") or post.get("over_18"):
        return None
    video = ((post.get("secure_media") or post.get("media")) or {}).get("reddit_video") or {}
    fallback = video.get("fallback_url")
    permalink = post.get("permalink")
    if not fallback or not permalink:
        return None
    thumb = post.get("thumbnail")
    images = (post.get("preview") or {}).get("images") or []
    if images:
        thumb = html.unescape(images[0].get("source", {}).get("url") or "") or thumb
    return SearchItem(
        id=str(post.get("id")),
        title=html.unescape(post.get("title") or ""),
        # Страница поста: yt-dlp скачивает с неё видео вместе со звуком (fallback_url — без звука)
        url=f"https://www.reddit.com{permalink}",
        page_url=f"https://www.reddit.com{permalink}",
        preview_url=fallback,
        thumbnail=thumb if thumb and thumb.startswith("http") else None,
        duration=video.get("duration"),
        width=video.get("width"),
        height=video.get("height"),
        author=post.get("subreddit_name_prefixed"),
    )


class RedditProvider(SearchProvider):
    key = "reddit"
    title = "Reddit"

    def __init__(self, session: aiohttp.ClientSession, client_id: str, client_secret: str, user_agent: str) -> None:
        self.session = session
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent
        self._token: str | None = None
        self._token_expires = 0.0
        self._token_lock = asyncio.Lock()

    async def _get_token(self) -> str:
        async with self._token_lock:
            if self._token and time.monotonic() < self._token_expires:
                return self._token
            credentials = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
            data = await fetch_json(
                self.session,
                TOKEN_URL,
                platform=self.title,
                method="POST",
                data={"grant_type": "client_credentials"},
                headers={"Authorization": f"Basic {credentials}", "User-Agent": self.user_agent},
            )
            token = data.get("access_token")
            if not token:
                raise ProviderError("Reddit: не удалось получить токен доступа")
            self._token = token
            self._token_expires = time.monotonic() + max(60, int(data.get("expires_in", 3600)) - 60)
            return token

    async def search(self, query: str, limit: int) -> list[SearchItem]:
        if not (self.client_id and self.client_secret):
            raise ProviderError("Reddit: не настроены ключи API")
        token = await self._get_token()
        headers = {"Authorization": f"bearer {token}", "User-Agent": self.user_agent}
        results: list[SearchItem] = []
        seen: set[str] = set()
        after = None
        for _ in range(MAX_PAGES):
            params = {"q": query, "sort": "relevance", "t": "year", "limit": 100, "type": "link",
                      "raw_json": 1, "include_over_18": "off"}
            if after:
                params["after"] = after
            data = await fetch_json(self.session, SEARCH_URL, platform=self.title, params=params, headers=headers)
            listing = data.get("data") or {}
            for child in listing.get("children") or []:
                item = parse_post(child.get("data") or {})
                if item and item.url not in seen:
                    seen.add(item.url)
                    results.append(item)
                    if len(results) >= limit:
                        return results
            after = listing.get("after")
            if not after:
                break
        return results
