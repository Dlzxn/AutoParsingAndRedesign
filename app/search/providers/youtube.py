import html
import re

import aiohttp

from app.search.base import ProviderError, SearchItem, SearchProvider, fetch_json

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

_DURATION_RE = re.compile(r"^P(?:(?P<d>\d+)D)?(?:T(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+)S)?)?$")


def parse_iso_duration(value: str) -> int | None:
    """ISO 8601 (PT1M5S) -> секунды. None, если формат не распознан."""
    match = _DURATION_RE.match(value or "")
    if not match or value in ("P", "PT"):
        return None
    parts = {k: int(v) if v else 0 for k, v in match.groupdict().items()}
    return parts["d"] * 86400 + parts["h"] * 3600 + parts["m"] * 60 + parts["s"]


class YouTubeProvider(SearchProvider):
    key = "yt"
    title = "YouTube"

    def __init__(self, session: aiohttp.ClientSession, api_key: str, max_duration: int) -> None:
        self.session = session
        self.api_key = api_key
        self.max_duration = max_duration

    async def search(self, query: str, limit: int) -> list[SearchItem]:
        if not self.api_key:
            raise ProviderError("YouTube: не настроен ключ API")
        data = await fetch_json(
            self.session,
            SEARCH_URL,
            platform=self.title,
            params={
                "part": "snippet",
                "q": query,
                "type": "video",
                "videoDuration": "short",  # < 4 минут
                "maxResults": 50,
                "safeSearch": "moderate",
                "key": self.api_key,
            },
        )
        snippets: dict[str, dict] = {}
        for item in data.get("items", []):
            video_id = (item.get("id") or {}).get("videoId")
            if video_id:
                snippets[video_id] = item.get("snippet") or {}
        if not snippets:
            return []

        details = await fetch_json(
            self.session,
            VIDEOS_URL,
            platform=self.title,
            params={"part": "contentDetails", "id": ",".join(snippets), "key": self.api_key},
        )
        durations = {
            v["id"]: parse_iso_duration((v.get("contentDetails") or {}).get("duration", ""))
            for v in details.get("items", [])
        }

        results: list[SearchItem] = []
        for video_id, snippet in snippets.items():
            duration = durations.get(video_id)
            if duration is None or duration > self.max_duration:
                continue
            thumbs = snippet.get("thumbnails") or {}
            thumb = (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get("url")
            results.append(
                SearchItem(
                    id=video_id,
                    title=html.unescape(snippet.get("title") or ""),
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    page_url=f"https://www.youtube.com/shorts/{video_id}",
                    embed_url=f"https://www.youtube.com/embed/{video_id}",
                    thumbnail=thumb,
                    duration=duration,
                    author=snippet.get("channelTitle"),
                )
            )
            if len(results) >= limit:
                break
        return results
