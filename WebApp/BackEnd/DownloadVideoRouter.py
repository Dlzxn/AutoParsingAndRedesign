from fastapi import APIRouter
from WebApp.BackEnd.Download.download_video import download_video
import json

router = APIRouter()

@router.get("/api/{video_id}")
async def get_video(video_id: str):
    with open("Data/clips.json", "r", encoding="utf-8") as f:
        href = json.load(f)
    for x in href:
        if str(x["id"]) == video_id:
            data = x
    download_video(data["url"], data["id"])
    return
