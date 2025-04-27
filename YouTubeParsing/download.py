import yt_dlp

def download_yt(url, file_path):
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': file_path,
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


