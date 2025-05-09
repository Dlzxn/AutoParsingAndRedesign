import yt_dlp
import os


def download_vkvideo(url, download_path):
    ydl_opts = {
        'format': 'best',
        # 'quiet': True,
        'outtmpl': "video.mp4",
        'socket_timeout': 60,  # Увеличиваем тайм-аут сокета
        'timeout': 60,  # Увеличиваем общий тайм-аут
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        print("начинаем загрузку вк видео", url)
        ydl.download([url])

def remove_file_on_close(video_file, video_path):
    video_file.close()
    os.remove(video_path)

#download_vkvideo("https://vk.com/video-47347778_456245937", "asgaaa.mp4")