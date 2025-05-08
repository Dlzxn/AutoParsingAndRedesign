from fastapi import APIRouter, HTTPException, FastAPI, Request, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from VkParsing.download import download_vkvideo, remove_file_on_close
from YouTubeParsing.download import download_video
from WebApp.BackEnd.auth_api.auth_api_router import list_with_tokens
from Imgur.download import download_video_imgur

import os, json, httpx


router = APIRouter(prefix = "/download")

def remove_file(file_path):
    os.remove(file_path)

@router.get("/vkvideo")
async def get_video(request: Request, background_tasks: BackgroundTasks):
    video_url = request.query_params.get("url")
    if not video_url:
        raise HTTPException(status_code=400, detail="URL не передан в параметрах запроса")

    # Определяем временный путь для сохранения видео
    video_filename = "downloaded_video.mp4"
    video_path = "video.mp4"

    # Скачиваем видео
    try:
        download_vkvideo(video_url, video_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка скачивания видео: {str(e)}")

    video_file = open(video_path, mode="rb")

    response = StreamingResponse(video_file, media_type="video/mp4")

    response.headers["Content-Disposition"] = f"attachment; filename={video_filename}"

    background_tasks.add_task(remove_file_on_close, video_file, video_path)

    token = request.cookies.get("token")
    with open("Data/clips_history.json", "r") as file:
        print("OPEN FILE AS JSON")
        clips = json.load(file)
        user = " "
    with open("Data/clips_history.json", "w") as file:
        for x in list_with_tokens:
            print(x["token"], token)
            if str(x["token"]) == str(token):
                user = x["user"]
                print(f"User: {user.password} {user.id}, {user.email}")
        clips_user = []
        try:
            clips_user = clips[str(user.id)]
            clips_user.append(video_url)
        except KeyError:
            print(KeyError)
            clips_user = [video_url]
        finally:
            clips[user.id] = clips_user
            json.dump(clips, file)
            print("Json Dumped")

    return response

@router.get("/yt")
async def get_video(request: Request, background_tasks: BackgroundTasks):
    video_url = request.query_params.get("url")
    if not video_url:
        raise HTTPException(status_code=400, detail="URL не передан в параметрах запроса")
    #
    # # Определяем временный путь для сохранения видео
    # video_filename = "downloaded_video.mp4"
    # video_path = os.path.join("/tmp", video_filename)  # Например, сохраняем в /tmp
    #
    # # Скачиваем видео
    # try:
    #     download_yt(video_url, video_path)
    # except Exception as e:
    #     raise HTTPException(status_code=500, detail=f"Ошибка скачивания видео: {str(e)}")
    #
    # video_file = open(video_path, mode="rb")
    #
    # response = StreamingResponse(video_file, media_type="video/mp4")
    #
    # response.headers["Content-Disposition"] = f"attachment; filename={video_filename}"
    #
    # background_tasks.add_task(remove_file_on_close, video_file, video_path)
    token = request.cookies.get("token")
    with open("Data/clips_history.json", "r") as file:
        print("OPEN FILE AS JSON")
        clips = json.load(file)
        user = " "

    with open("Data/clips_history.json", "w") as file:
        for x in list_with_tokens:
            print(x["token"], token)
            if str(x["token"]) == str(token):
                user = x["user"]
                print(f"User: {user.password} {user.id}, {user.email}")
        clips_user = []
        try:
            clips_user = clips[str(user.id)]
            clips_user.append(video_url)
        except KeyError:
            print(KeyError)
            clips_user = [video_url]
        finally:
            clips[user.id] = clips_user
            json.dump(clips, file)
            print("Json Dumped")
        # if user != " ":

    try:
        video_path = download_video(video_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка скачивания видео: {str(e)}")

        # Добавляем задачу удаления после отправки
    background_tasks.add_task(remove_file, video_path)
    print("PATH: ", video_path)
    return FileResponse(video_path, media_type='video/mp4', filename="downloaded_video.mp4")

@router.get("/imgur")
async def get_video(url: str, request: Request, background_tasks: BackgroundTasks):
    video_url = url
    if not video_url:
        raise HTTPException(status_code=400, detail="URL не передан в параметрах запроса")
    token = request.cookies.get("token")
    with open("Data/clips_history.json", "r") as file:
        print("OPEN FILE AS JSON")
        clips = json.load(file)
        user = " "

    with open("Data/clips_history.json", "w") as file:
        for x in list_with_tokens:
            print(x["token"], token)
            if str(x["token"]) == str(token):
                user = x["user"]
                print(f"User: {user.password} {user.id}, {user.email}")
        clips_user = []
        try:
            clips_user = clips[str(user.id)]
            clips_user.append(video_url)
        except KeyError:
            print(KeyError)
            clips_user = [video_url]
        finally:
            clips[user.id] = clips_user
            json.dump(clips, file)
            print("Json Dumped in imgur")
        # if user != " ":

    try:
        video_path = await download_video_imgur(video_url, "imgur_video.mp4")
        print("IMGUR READY")
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=f"Ошибка скачивания видео: {str(e)}")

        # Добавляем задачу удаления после отправки
    background_tasks.add_task(remove_file, video_path)
    print("PATH: ", video_path)
    return FileResponse(video_path, media_type='video/mp4', filename="downloaded_video.mp4")
