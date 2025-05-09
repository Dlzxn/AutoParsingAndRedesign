import aiohttp
import asyncio

IMGUR_CLIENT_ID = "62dd15c413a0dd4"

headers = {
    "Authorization": f"Client-ID {IMGUR_CLIENT_ID}"
}

async def find_imgur_shorts_by_tag(tag: str, used_links: list[str], limit: int = 200) -> list[dict[str, str]]:
    """
    Асинхронный поиск коротких вертикальных клипов по тегу на Imgur.
    """
    results = []
    url = f"https://api.imgur.com/3/gallery/search?q={tag}"

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as response:
            data = await response.json()
            print("Raw data keys:", data.keys())

            for item in data.get("data", []):
                images = item.get("images") if item.get("is_album") else [item]

                if not images:
                    continue

                for img in images:
                    if img.get("type", "").startswith("video") and img.get("link") not in used_links:
                        height = img.get("height", 1)
                        width = img.get("width", 1)
                        if height > width:  # вертикальное видео
                            results.append({
                                "title": item.get("title", ""),
                                "url": img["mp4"]
                            })

                            # если лимит не None — останавливаемся, когда достигли нужного количества
                            if limit and len(results) >= limit:
                                return results

    return results

#
# # Пример запуска
# if __name__ == "__main__":
#     used = []
#     videos = asyncio.run(find_imgur_shorts_by_tag("funny", used))
#     print("Ready:", len(videos))
#     for x in videos:
#         print(x)
