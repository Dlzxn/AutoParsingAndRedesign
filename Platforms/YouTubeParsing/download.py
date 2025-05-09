from yt_dlp import YoutubeDL, DownloadError
import tempfile
import os

def download_video(url: str):

    try:
        # Ищем доступные форматы видео
        with YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])

            # Логирование доступных форматов
            print(f"Доступные форматы для {url}:")
            for f in formats:
                print(f"ID: {f.get('format_id')}, Видео: {f.get('vcodec')}, Аудио: {f.get('acodec')}, Разрешение: {f.get('width', 'N/A')}x{f.get('height', 'N/A')}")

            # Находим первый подходящий формат (видео и аудио)
            best_format = None
            for f in formats:
                if f.get('vcodec') != 'none' and f.get('acodec') != 'none':  # Видео и аудио
                    best_format = f
                    break  # Прерываем цикл, если нашли первый подходящий формат

            if best_format is None:
                # Если нет подходящего формата, пробуем загрузить только аудио или видео
                for f in formats:
                    if f.get('acodec') != 'none':  # Только аудио
                        best_format = f
                        break
                    if f.get('vcodec') != 'none':  # Только видео
                        best_format = f
                        break

            if best_format is None:
                raise DownloadError("Не найден подходящий формат для скачивания.")

            # Загружаем видео с найденным форматом
            proxy = "http://root:qiHH^VVy4m@Q?_@185.104.115.35:3128"

            # Настройки YDL
            ydl_opts = {
                'format': best_format['format_id'],
                'outtmpl': "naiticlip_video.%(ext)s",
                'merge_output_format': 'webm',
                'quiet': True,
                'proxy': proxy,
                'socket_timeout': 120,
                'nocheckcertificate': True  # если self-signed или проблемы SSL
            }

            print(f"Загружаем видео с форматом {best_format['format_id']}...")
            ydl.download([url])
            info = ydl.extract_info(url, download=False)
            file_name = ydl.prepare_filename(info)
            print(f"FILENAME: {file_name}")


    except DownloadError as e:
        raise Exception(f"Ошибка при загрузке: {str(e)}")

    finally:
        # Если файл был успешно скачан, возвращаем его путь
        return file_name

# download_video("https://www.youtube.com/watch?v=C_JT7_I1lhQ")