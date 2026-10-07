import asyncio

import aiohttp

from app.search.base import ProviderError, SearchItem, SearchProvider, fetch_json

SEARCH_URL = "https://api.imgur.com/3/gallery/search/viral/all/{page}"
PAGES = 3


def parse_gallery_item(item: dict) -> list[SearchItem]:
    """Достаёт вертикальные видео из элемента галереи (одиночного поста или альбома)."""
    if item.get("nsfw"):
        return []
    media = item.get("images") if item.get("is_album") else [item]
    results = []
    for img in media or []:
        if not str(img.get("type", "")).startswith("video"):
            continue
        link = img.get("mp4") or img.get("link")
        width, height = img.get("width") or 0, img.get("height") or 0
        if not link or height <= width:  # только вертикальные ролики
            continue
        results.append(
            SearchItem(
                id=str(img.get("id")),
                title=item.get("title") or img.get("title") or "Imgur",
                url=link,
                page_url=item.get("link"),
                preview_url=link,
                thumbnail=f"https://i.imgur.com/{img.get('id')}h.jpg" if img.get("id") else None,
                duration=None,
                width=width,
                height=height,
            )
        )
    return results


class ImgurProvider(SearchProvider):
    key = "imgur"
    title = "Imgur"

    def __init__(self, session: aiohttp.ClientSession, client_id: str) -> None:
        self.session = session
        self.client_id = client_id

    async def _page(self, query: str, page: int) -> dict:
        return await fetch_json(
            self.session,
            SEARCH_URL.format(page=page),
            platform=self.title,
            params={"q": query},
            headers={"Authorization": f"Client-ID {self.client_id}"},
        )

    async def search(self, query: str, limit: int) -> list[SearchItem]:
        if not self.client_id:
            raise ProviderError("Imgur: не настроен Client ID")
        pages = await asyncio.gather(*(self._page(query, p) for p in range(PAGES)), return_exceptions=True)
        if all(isinstance(p, BaseException) for p in pages):
            first_error = pages[0]
            raise first_error if isinstance(first_error, ProviderError) else ProviderError("Imgur: ошибка запроса")

        results: list[SearchItem] = []
        seen: set[str] = set()
        for page in pages:
            if isinstance(page, BaseException):
                continue
            for item in page.get("data") or []:
                for found in parse_gallery_item(item):
                    if found.url not in seen:
                        seen.add(found.url)
                        results.append(found)
                        if len(results) >= limit:
                            return results
        return results
