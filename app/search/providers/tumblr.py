import logging

import aiohttp
from bs4 import BeautifulSoup

from app.search.base import ProviderError, SearchItem, SearchProvider, fetch_json

TAGGED_URL = "https://api.tumblr.com/v2/tagged"
PAGE_SIZE = 20
MAX_PAGES = 5

log = logging.getLogger(__name__)


def html_to_text(value: str) -> str:
    text = BeautifulSoup(value or "", "html.parser").get_text("\n")
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def parse_post(post: dict) -> SearchItem | None:
    if post.get("type") != "text":
        return None
    text = html_to_text(post.get("body") or "")
    if not text:
        return None
    return SearchItem(
        id=str(post.get("id_string") or post.get("id")),
        kind="text",
        title=(post.get("title") or "").strip() or post.get("blog_name") or "Tumblr",
        url=post.get("post_url") or "",
        page_url=post.get("post_url"),
        text=text,
        summary=(post.get("summary") or text[:300]).strip(),
        author=post.get("blog_name"),
        published_at=post.get("timestamp"),
        tags=list(post.get("tags") or []),
    )


class TumblrProvider(SearchProvider):
    key = "tumblr"
    title = "Tumblr"

    def __init__(self, session: aiohttp.ClientSession, api_keys: list[str]) -> None:
        self.session = session
        self.api_keys = api_keys

    async def _tagged(self, tag: str, before: int | None) -> list[dict]:
        last_error: ProviderError | None = None
        for key in self.api_keys:  # резервные ключи — на случай исчерпания лимита основного
            params = {"tag": tag, "api_key": key, "limit": PAGE_SIZE, "filter": "html"}
            if before:
                params["before"] = before
            try:
                data = await fetch_json(self.session, TAGGED_URL, platform=self.title, params=params)
                return data.get("response") or []
            except ProviderError as exc:
                log.warning("Tumblr key failed, trying next: %s", exc)
                last_error = exc
        raise last_error or ProviderError("Tumblr: не настроены ключи API")

    async def search(self, query: str, limit: int) -> list[SearchItem]:
        if not self.api_keys:
            raise ProviderError("Tumblr: не настроены ключи API")
        results: list[SearchItem] = []
        seen: set[str] = set()
        before = None
        for _ in range(MAX_PAGES):
            posts = await self._tagged(query, before)
            for post in posts:
                item = parse_post(post)
                if item and item.url and item.url not in seen:
                    seen.add(item.url)
                    results.append(item)
                    if len(results) >= limit:
                        return results
            if len(posts) < PAGE_SIZE:
                break
            before = posts[-1].get("timestamp")
            if not before:
                break
        return results
