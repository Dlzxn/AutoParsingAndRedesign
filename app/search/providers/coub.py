import asyncio

import aiohttp

from app.search.base import ProviderError, SearchItem, SearchProvider, fetch_json

SEARCH_URL = "https://coub.com/api/v2/smart_search/general_search"
MAX_PAGES = 5


def parse_coub(coub: dict) -> SearchItem | None:
    share = ((coub.get("file_versions") or {}).get("share") or {}).get("default")
    if not share:
        return None
    images = coub.get("image_versions") or {}
    thumbnail = None
    if images.get("template"):
        thumbnail = images["template"].replace("%{version}", "med")
    dims = (coub.get("dimensions") or {}).get("med") or (coub.get("dimensions") or {}).get("big")
    permalink = coub.get("permalink")
    return SearchItem(
        id=str(coub.get("id") or permalink),
        title=coub.get("title") or "Coub",
        url=share,  # видео со звуком, зацикленное — подходит и для скачивания, и для редактора
        page_url=f"https://coub.com/view/{permalink}" if permalink else None,
        preview_url=share,
        thumbnail=thumbnail,
        duration=coub.get("duration"),
        width=dims[0] if dims else None,
        height=dims[1] if dims else None,
    )


class CoubProvider(SearchProvider):
    key = "coub"
    title = "Coub"

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self.session = session

    async def _page(self, query: str, page: int) -> dict:
        return await fetch_json(
            self.session, SEARCH_URL, platform=self.title, params={"search_query": query, "page": page}
        )

    async def search(self, query: str, limit: int) -> list[SearchItem]:
        first = await self._page(query, 1)
        pages = [first]
        total_pages = min(int((first.get("meta") or {}).get("total_pages") or 1), MAX_PAGES)
        if total_pages > 1:
            rest = await asyncio.gather(
                *(self._page(query, p) for p in range(2, total_pages + 1)), return_exceptions=True
            )
            pages.extend(r for r in rest if isinstance(r, dict))

        results: list[SearchItem] = []
        seen: set[str] = set()
        for page in pages:
            for coub in page.get("coubs") or []:
                item = parse_coub(coub)
                if item and item.url not in seen:
                    seen.add(item.url)
                    results.append(item)
                    if len(results) >= limit:
                        return results
        if not results and "coubs" not in first:
            raise ProviderError("Coub: неожиданный ответ сервиса")
        return results
