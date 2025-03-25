from fastapi import APIRouter, HTTPException, FastAPI, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
import yt_dlp
import os

router = APIRouter()

def download_video(url, download_path):
    ydl_opts = {
        'format': 'best',  # Выбираем лучшее качество
        'quiet': True,  # Убираем лишний вывод в консоль
        'outtmpl': download_path,  # Указываем путь для сохранения файла
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

def remove_file_on_close(video_file, video_path):
    video_file.close()
    os.remove(video_path)

@router.get("/api/download")
async def get_video(request: Request, background_tasks: BackgroundTasks):
    video_url = request.headers.get('x-video-url')

    if not video_url:
        raise HTTPException(status_code=400, detail="URL не передан в параметрах запроса")

    # Определяем временный путь для сохранения видео
    video_filename = "downloaded_video.mp4"
    video_path = os.path.join("/tmp", video_filename)  # Например, сохраняем в /tmp

    # Скачиваем видео
    try:
        download_video(video_url, video_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка скачивания видео: {str(e)}")

    # Открываем видеофайл для передачи через StreamingResponse
    video_file = open(video_path, mode="rb")

    # Используем StreamingResponse для потока видео
    response = StreamingResponse(video_file, media_type="video/mp4")

    # После передачи файла, удаляем его
    response.headers["Content-Disposition"] = f"attachment; filename={video_filename}"

    # Добавляем функцию для удаления файла после завершения передачи
    background_tasks.add_task(remove_file_on_close, video_file, video_path)

    return response
