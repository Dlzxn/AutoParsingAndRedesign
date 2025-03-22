from fastapi import APIRouter
from starlette.responses import JSONResponse

from VkParsing.main import parse_vk_video

search_router = APIRouter(prefix="/search", tags=["Search"])



@search_router.get("/")
async def search(tag: str):
    status, url_list = parse_vk_video(tag)
    if not status:
        return JSONResponse({"status": "error", "message": "No video found"})
    else:
        return url_list
