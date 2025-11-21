from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from datetime import datetime
from typing import Optional
from WebApp.BackEnd.castomization.editor import VideoEditor

editvideo_router = APIRouter(prefix="/VideoEditor", tags=["Profile"])

editvideo_router.mount("/WebApp/FrontEnd", StaticFiles(directory="WebApp/FrontEnd"), name="static")

templates = Jinja2Templates(directory="WebApp/FrontEnd/templates")

@editvideo_router.get("/")
async def get_profile(request: Request):
    return templates.TemplateResponse("VideoEditor.html", {"request": request})

# Папка для временных файлов
UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


@editvideo_router.get("/editor/{url:path}")
async def editor(request: Request, url: str):
    print(url)
    return templates.TemplateResponse("VideoEditor.html", {"request": request})


@editvideo_router.post("/editor/getpar")
async def edit_video(
    videoFile: UploadFile = File(...),
    trim: Optional[str] = Form(None),
    resize: Optional[str] = Form(None),
    speed: Optional[float] = Form(None),
    rotate: Optional[float] = Form(None),
    scale: Optional[float] = Form(None),
    volume: Optional[float] = Form(None),
    text: Optional[str] = Form(None),
    overlay: Optional[UploadFile] = File(None),
    bg_audio: Optional[UploadFile] = File(None),
    subs: Optional[UploadFile] = File(None)
):
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    # Сохраняем видео
    if overlay:
        print("RAW FILENAME:", overlay.filename, repr(overlay.filename))

    video_path = UPLOAD_DIR / f"{timestamp}_video.mp4"
    with open(video_path, "wb") as f:
        f.write(await videoFile.read())

    # Создаём объект VideoEditor
    editor = VideoEditor(str(video_path))

    # Trim
    if trim:
        start, end = map(float, trim.split("-"))
        editor.trim((start, end))

    if resize:
        editor.resize(resize)
    if speed:
        editor.speed(speed)
    if rotate:
        editor.rotate(rotate)
    if scale:
        editor.scale(scale)
    if volume:
        editor.adjust_volume(volume)
    if text:
        editor.add_text(text)

    # Overlay
    if overlay is not None and overlay.filename:
        overlay_path = UPLOAD_DIR / f"{timestamp}_overlay.png"
        with open(overlay_path, "wb") as f:
            f.write(await overlay.read())
        editor.overlay_image(str(overlay_path))

    # Background audio
    if bg_audio is not None and bg_audio.filename:
        audio_path = UPLOAD_DIR / f"{timestamp}_bg.mp3"
        with open(audio_path, "wb") as f:
            f.write(await bg_audio.read())
        editor.add_background_audio(str(audio_path))

    # Subtitles
    if subs is not None and subs.filename:
        subs_path = UPLOAD_DIR / f"{timestamp}_subs.srt"
        with open(subs_path, "wb") as f:
            f.write(await subs.read())
        editor.add_subtitles(str(subs_path))

    # Экспорт готового видео
    output_path = OUTPUT_DIR / f"{timestamp}_final.mp4"
    editor.export(str(output_path))

    # Возвращаем ссылку
    return {"link": f"/VideoEditor/videos/{output_path.name}"}


@editvideo_router.get("/videos/{url:path}")
def get_video(request: Request, url: str):
    return FileResponse(str(f"outputs/{url}"), media_type="video/mp4", filename=url)

