from fastapi import APIRouter, Request

from app.auth.deps import DbSession, OptionalUser, PageUser
from app.catalog.service import get_tariffs, is_platform_enabled
from app.web.templating import render

router = APIRouter(include_in_schema=False)

# Страницы поиска: URL -> настройки страницы
SEARCH_PAGES: dict[str, dict] = {
    "vk": {"key": "vk", "title": "VK Клипы", "description": "Поиск коротких роликов ВКонтакте", "loading": "Ищем клипы ВКонтакте...", "kind": "video"},
    "youtube": {"key": "yt", "title": "YouTube Shorts", "description": "Поиск коротких видео на YouTube", "loading": "Сканируем YouTube...", "kind": "video"},
    "coub": {"key": "coub", "title": "Coub", "description": "Зацикленные ролики со звуком с Coub", "loading": "Ищем на Coub...", "kind": "video"},
    "reddit": {"key": "reddit", "title": "Reddit", "description": "Видео из сообществ Reddit", "loading": "Ищем на Reddit...", "kind": "video"},
    "imgur": {"key": "imgur", "title": "Imgur", "description": "Вертикальные ролики с Imgur", "loading": "Ищем на Imgur...", "kind": "video"},
    "tumblr": {"key": "tumblr", "title": "Tumblr", "description": "Текстовые посты Tumblr по тегу", "loading": "Ищем посты Tumblr...", "kind": "text"},
}


@router.get("/")
async def index(request: Request, user: OptionalUser):
    return render(request, "mainString.html")


@router.get("/tariffs")
async def tariffs(request: Request, user: OptionalUser):
    return render(request, "tariffs.html")


@router.get("/features")
async def features(request: Request, user: OptionalUser):
    return render(request, "features.html")


@router.get("/video")
async def video_platforms(request: Request, user: OptionalUser):
    return render(request, "videos.html")


@router.get("/text")
async def text_platforms(request: Request, user: OptionalUser):
    return render(request, "text.html")


@router.get("/profile")
async def profile(request: Request, user: PageUser, db: DbSession):
    return render(request, "profile.html", tariffs=await get_tariffs(db))


@router.get("/text-editor")
async def text_editor(request: Request, user: PageUser):
    return render(request, "text_editor.html")


def _search_page(slug: str):
    page = SEARCH_PAGES[slug]

    async def handler(request: Request, db: DbSession, user: PageUser):
        if not await is_platform_enabled(db, page["key"]):
            return render(request, "tex_platform.html")
        return render(request, "search.html", page=page)

    handler.__name__ = f"search_page_{slug}"
    return handler


for _slug in SEARCH_PAGES:
    router.add_api_route(f"/{_slug}", _search_page(_slug), methods=["GET"])
