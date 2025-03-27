from fastapi import APIRouter
from starlette.responses import JSONResponse

from VkParsing.main import parse_vk_video
from GoogleParsing.parser import GoogleBot
from WebApp.logger.log_cfg import logger

search_router = APIRouter(prefix="/search", tags=["Search"])



@search_router.get("/")
async def search(tag: str):
    try:
        logger.info(f"Searching for {tag} started...")
        bot = GoogleBot(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                                   "Chrome/91.0.4472.124 Safari/537.36")
        url_list = bot.get_video_links(tag)
        bot.close()
        print("URL: ", url_list)
        logger.info(f"Found {len(url_list)} videos.")
        return url_list
    except Exception as e:
        print(e)
        logger.error(e)
        return {"status": "ERROR"}
