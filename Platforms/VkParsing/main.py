import aiohttp
import asyncio

# Ваш токен доступа для API ВКонтакте
access_token = ''
vk_api_url = 'https://api.vk.com/method/video.search'


# Функция для поиска видео по тегу
async def search_vk_videos(tag):
    async with aiohttp.ClientSession() as session:
        params = {
            'q': tag,  # Тег для поиска
            'count': 50,  # Количество видео
            'access_token': access_token,  # Ваш токен доступа
            'v': '5.131'  # Версия API
        }

        async with session.get(vk_api_url, params=params) as response:
            data = await response.json()

            if 'response' not in data:
                print("Ошибка при получении данных:", data)
                return []

            videos = data['response']['items']
            return videos


# Функция для фильтрации видео по длительности
def filter_videos_by_duration(videos, max_duration=60):
    filtered_videos = [video for video in videos if video.get('duration', 0) <= max_duration]
    return filtered_videos


# Функция для создания iframe для видео
async def create_iframe(videos):
    iframe_videos = []

    for video in videos:
        owner_id = video['owner_id']
        video_id = video['id']
        title = video.get('title', 'Без названия')

        # Сформируем ссылку на встроенный плеер для ВКонтакте
        iframe_url = f"https://vk.com/video_ext.php?oid={owner_id}&id={video_id}&hd=1"

        iframe_video = {
            'title': title,
            'iframe': iframe_url
        }

        iframe_videos.append(iframe_video)

    return iframe_videos


# Основная асинхронная функция
async def main(tag):
    # Ищем видео по тегу
    videos = await search_vk_videos(tag)

    if not videos:
        print("Видео не найдены.")
        return

    # Фильтруем видео по длительности
    filtered_videos = filter_videos_by_duration(videos)

    if not filtered_videos:
        print("Нет видео до 1 минуты.")
        return

    # Создаем iframe для встраивания видео
    iframe_videos = await create_iframe(filtered_videos)

    # Выводим ссылки на видео
    for video in iframe_videos:
        print(f"Заголовок: {video['title']}")
        print(
            f"Встроенный плеер: <iframe src='{video['iframe']}' width='640' height='360' frameborder='0' allowfullscreen='true'></iframe>")
