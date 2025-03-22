import yt_dlp

def download_video(url, id):
    ydl_opts = {
        'outtmpl': f'%(title)s{id}.%(ext)s',  # Название файла - будет сохранено по названию видео
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

