from fastapi import APIRouter, Request, Form, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import moviepy as mp
import yt_dlp
import os
import uuid

editor = APIRouter()
templates = Jinja2Templates(directory="WebApp/FrontEnd/templates")

UPLOAD_DIR = "uploads/processed"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

@editor.get("/VideoEditor/editor/{video_url:path}")
async def open_video_editor(request: Request, video_url: str):
    return templates.TemplateResponse("VideoEditor.html", {
        "request": request,
        "video_url": video_url
    })

@editor.post("/process-video")
async def process_video(
    videoUrl: str = Form(None),
    videoFile: UploadFile = File(None),
    trim: str = Form(None),
    volume: str = Form(None),
    speed: str = Form(None),
    rotate: str = Form(None),
    scale: str = Form(None),
    text: str = Form(None)
):
    input_path = ""
    try:
        file_id = str(uuid.uuid4())
        input_path = os.path.join(UPLOAD_DIR, f"input_{file_id}.mp4")
        output_path = os.path.join(UPLOAD_DIR, f"output_{file_id}.mp4")

        if videoUrl and videoUrl.strip() != "":
            ydl_opts = {
                'format': 'best[ext=mp4]/best',
                'outtmpl': input_path,
                'socket_timeout': 60,
                'retries': 20,
                'nocheckcertificate': True,
                'quiet': True
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([videoUrl.split('&')[0]])
        elif videoFile:
            content = await videoFile.read()
            with open(input_path, "wb") as f:
                f.write(content)
        else:
            return JSONResponse({"message": "Источник не найден"}, status_code=400)

        if not os.path.exists(input_path) or os.path.getsize(input_path) == 0:
            return JSONResponse({"message": "Ошибка: Файл не скачан (Timeout)"}, status_code=500)

        clip = mp.VideoFileClip(input_path)

        if trim and "-" in trim:
            try:
                t_start, t_end = map(float, trim.split("-"))
                clip = clip.subclipped(t_start, t_end)
            except:
                try: clip = clip.subclip(float(trim.split("-")[0]), float(trim.split("-")[1]))
                except: pass

        if speed and float(speed) != 1.0:
            try:
                clip = clip.with_effects([mp.vfx.Speedx(float(speed))])
            except:
                try: clip = clip.fx(mp.vfx.speedx, float(speed))
                except: pass

        if rotate and int(rotate) != 0:
            try:
                clip = clip.rotated(int(rotate))
            except:
                try: clip = clip.rotate(int(rotate))
                except: pass

        if scale and int(scale) != 100:
            new_w = clip.w * (int(scale) / 100)
            try:
                clip = clip.resized(width=new_w)
            except:
                try: clip = clip.resize(width=new_w)
                except: pass

        if volume and int(volume) != 100:
            try:
                clip = clip.multiply_volume(int(volume) / 100)
            except:
                try: clip = clip.volumex(int(volume) / 100)
                except: pass

        if text:
            try:
                txt_clip = mp.TextClip(
                    text=text,
                    font_size=70,
                    color='white',
                    font='Arial'
                ).set_duration(clip.duration).set_position('center')
                clip = mp.CompositeVideoClip([clip, txt_clip])
            except:
                pass

        clip.write_videofile(output_path, codec="libx264", audio_codec="aac", temp_audiofile=f"temp_{file_id}.m4a", remove_temp=True)
        clip.close()

        if os.path.exists(input_path):
            os.remove(input_path)

        return FileResponse(output_path, media_type="video/mp4", filename="edited_video.mp4")

    except Exception as e:
        if input_path and os.path.exists(input_path):
            try: os.remove(input_path)
            except: pass
        return JSONResponse({"status": "error", "message": f"Ошибка: {str(e)}"}, status_code=500)