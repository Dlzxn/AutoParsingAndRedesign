import aiohttp

from app.config import Settings
from app.search.base import SearchProvider
from app.search.providers.coub import CoubProvider
from app.search.providers.imgur import ImgurProvider
from app.search.providers.reddit import RedditProvider
from app.search.providers.tumblr import TumblrProvider
from app.search.providers.vk import VKProvider
from app.search.providers.youtube import YouTubeProvider
from app.search.service import SearchService


def build_search_service(settings: Settings, session: aiohttp.ClientSession) -> SearchService:
    providers: list[SearchProvider] = [
        VKProvider(
            session,
            access_token=settings.vk_access_token,
            max_duration=settings.max_clip_duration,
            chrome_binary=settings.chrome_binary,
            max_browsers=settings.vk_max_browsers,
            timeout=settings.vk_search_timeout,
        ),
        YouTubeProvider(session, settings.youtube_api_key, settings.max_clip_duration),
        CoubProvider(session),
        RedditProvider(session, settings.reddit_client_id, settings.reddit_client_secret, settings.reddit_user_agent),
        ImgurProvider(session, settings.imgur_client_id),
        TumblrProvider(session, settings.tumblr_keys),
    ]
    return SearchService({p.key: p for p in providers}, settings.search_cache_ttl, settings.search_timeout)
