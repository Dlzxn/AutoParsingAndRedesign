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
        bot = GoogleBot()
        url_list = await bot.get_video_links(tag)
        bot.close()
        print("URL: ", url_list)
        logger.info(f"Found {len(url_list)} videos.")
        return url_list
    except Exception as e:
        print(e)
        logger.error(e)
        return {"status": "ERROR"}
