import os
import yt_dlp

def download_video(url, id):
    # Получаем путь к корню проекта
    project_root = os.path.abspath(f"{os.path.dirname(__file__)}/../../..")  # Это путь к директории, где находится текущий скрипт
    download_folder = os.path.join(project_root, 'Data')  # Папка Data будет в корне проекта

    # Проверка, существует ли папка, если нет — создаем
    if not os.path.exists(download_folder):
        os.makedirs(download_folder)

    # Настройки для ydl
    ydl_opts = {
        'outtmpl': os.path.join(download_folder, f'%(title)s{id}.%(ext)s'),  # Путь к файлу с названием видео
    }

    # Скачиваем видео
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
