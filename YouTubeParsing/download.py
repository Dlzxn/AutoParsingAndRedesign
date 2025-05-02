import yt_dlp
from urllib.parse import quote

def download_yt(url, file_path):
    username = "root"
    password = "qiHH^VVy4m@Q?_"
    proxy_host = "185.104.115.35"
    proxy_port = "3128"

    proxy = f"http://{quote(username)}:{quote(password)}@{proxy_host}:{proxy_port}"

    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': file_path,
        'proxy': proxy
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([url])
        except yt_dlp.utils.DownloadError as e:
            print(f"Ошибка загрузки: {e}")
            # Получаем список доступных форматов
            info_dict = ydl.extract_info(url, download=False)
            formats = info_dict.get('formats', [])
            print("Доступные форматы:")
            for format_info in formats:
                print(f"{format_info['format_id']} - {format_info['format_note']}")
            ydl_opts['format'] = '137'
            ydl.download([url])


