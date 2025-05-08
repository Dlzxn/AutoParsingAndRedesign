from fastapi import APIRouter, Request
from starlette.responses import JSONResponse
import json

from GoogleParsing.parser import GoogleBot
from WebApp.logger.log_cfg import logger
from YouTubeParsing.parser import search_youtube
from WebApp.BackEnd.auth_api.auth_api_router import list_with_tokens
from Tumblr.parser import get_tumblr_posts_by_tag
from coub.parser import get_video
from Reddit.parser import find_vertical_shorts_by_tag
from Imgur.parser import find_imgur_shorts_by_tag

search_router = APIRouter(prefix="/search", tags=["Search"])

@search_router.get("/Vk")
async def search(tag: str, request: Request):
    try:
        token = request.cookies.get("token")
        for x in list_with_tokens:
            if str(x["token"]) == str(token):
                user = x["user"]
        with open("Data/clips_history.json", "r") as file:
            print("OPEN FILE AS JSON")
            clips = json.load(file)
            clips_of_user = clips[f"{str(user.id)}"]
            print(clips_of_user)
        logger.info(f"Searching for {tag} started...")
        bot = GoogleBot()
        print("start parsing")
        url_list = await bot.get_video_links(tag, clips_of_user)
        print("URL: ", url_list)
        logger.info(f"Found {len(url_list)} videos.")
        return url_list
    except KeyError:
        logger.info(f"Searching for {tag} started...")
        bot = GoogleBot()
        print("start parsing")
        url_list = await bot.get_video_links(tag, [])
        print("URL: ", url_list)
        logger.info(f"Found {len(url_list)} videos.")
        return url_list

    except Exception as e:
        print(e)
        logger.error(e)
        return {"status": "ERROR"}

@search_router.get("/YT")
async def search(tag: str, request: Request):
    try:
        token = request.cookies.get("token")
        for x in list_with_tokens:
            if str(x["token"]) == str(token):
                user = x["user"]
        with open("Data/clips_history.json", "r") as file:
            print("OPEN FILE AS JSON")
            clips = json.load(file)
            clips_of_user = clips[f"{str(user.id)}"]
            print(clips_of_user)
        result = await search_youtube(tag, clips_of_user)
        print(result)
        return result
    except KeyError:
        result = await search_youtube(tag, [])
        print(result)
        return result

    except Exception as e:
        print("ERROR", e)
        logger.error(e)
        return {"status": "ERROR"}


@search_router.get("/tumblr")
async def search(tag: str, request: Request):
    clips_of_user = []
    try:
        token = request.cookies.get("token")
        for x in list_with_tokens:
            if str(x["token"]) == str(token):
                user = x["user"]
        with open("Data/clips_history.json", "r") as file:
            print("OPEN FILE AS JSON")
            clips = json.load(file)
            clips_of_user = clips[f"{str(user.id)}"]
            print(clips_of_user)
        logger.info(f"Searching for {tag} started...")
        url_list = await get_tumblr_posts_by_tag(tag, clips_of_user)
        print("start parsing")
        logger.info(f"Found {len(url_list)} videos.")
        return url_list
    except KeyError:
        logger.info(f"Searching for {tag} started...")
        print("start parsing")
        url_list = await get_tumblr_posts_by_tag(tag, clips_of_user)
        logger.info(f"Found {len(url_list)} videos.")
        return url_list

@search_router.get("/Coub")
async def search(tag: str, request: Request):
    clips_of_user = []
    try:
        token = request.cookies.get("token")
        for x in list_with_tokens:
            if str(x["token"]) == str(token):
                user = x["user"]
        with open("Data/clips_history.json", "r") as file:
            print("OPEN FILE AS JSON")
            clips = json.load(file)
            clips_of_user = clips[f"{str(user.id)}"]
            print(clips_of_user)
        logger.info(f"Searching for {tag} started...")
        url_list = await get_video(tag, clips_of_user)
        print("start parsing")
        logger.info(f"Found {len(url_list)} videos.")
        print(url_list)
        return url_list
    except KeyError:
        logger.info(f"Searching for {tag} started...")
        print("start parsing")
        url_list = await get_video(tag, clips_of_user)
        logger.info(f"Found {len(url_list)} videos.")
        return url_list

@search_router.get("/Reddit")
async def search(tag: str, request: Request):
    clips_of_user = []
    try:
        token = request.cookies.get("token")
        for x in list_with_tokens:
            if str(x["token"]) == str(token):
                user = x["user"]
        with open("Data/clips_history.json", "r") as file:
            print("OPEN FILE AS JSON")
            clips = json.load(file)
            clips_of_user = clips[f"{str(user.id)}"]
            print(clips_of_user)
        logger.info(f"Searching for {tag} started...")
        url_list = find_vertical_shorts_by_tag(tag, clips_of_user)
        print("start parsing")
        logger.info(f"Found {len(url_list)} videos.")
        print(url_list)
        return url_list
    except KeyError:
        logger.info(f"Searching for {tag} started...")
        print("start parsing")
        url_list = find_vertical_shorts_by_tag(tag, clips_of_user)
        logger.info(f"Found {len(url_list)} videos.")
        return url_list

@search_router.get("/Imgur")
async def search(tag: str, request: Request):
    clips_of_user = []
    try:
        token = request.cookies.get("token")
        for x in list_with_tokens:
            if str(x["token"]) == str(token):
                user = x["user"]
        with open("Data/clips_history.json", "r") as file:
            print("OPEN FILE AS JSON")
            clips = json.load(file)
            clips_of_user = clips[f"{str(user.id)}"]
            print(clips_of_user)
        logger.info(f"Searching for {tag} started...")
        url_list = await find_imgur_shorts_by_tag(tag, clips_of_user)
        print("start parsing")
        logger.info(f"Found {len(url_list)} videos.")
        print(url_list)
        return url_list
    except KeyError:
        logger.info(f"Searching for {tag} started...")
        print("start parsing")
        url_list = await find_imgur_shorts_by_tag(tag, clips_of_user)
        logger.info(f"Found {len(url_list)} videos.")
        return url_list