TOKEN = "AIzaSyCnvqnBZjZpo73E5evwgAe6zuWF02tNwlM"


from googleapiclient.discovery import build

# Ваш API ключ и CX (Custom Search Engine ID)
api_key = ''
cx = ''

# Инициализация Google Custom Search API
service = build("customsearch", "v1", developerKey=api_key)

# Поиск
res = service.cse().list(
    q='клипы шортс видео video site:https://vkvideo.ru',  # Добавляем "video" и ограничиваем по сайту vk.com
    cx=cx,
    num=10  # Количество результатов
).execute()

# Печатаем результаты
for item in res['items']:
    print(f"Название: {item['title']}")
    print(f"Ссылка: {item['link']}")
    print('---')
