import asyncio
import aiohttp
import pytumblr
from typing import List

# 🔐 Первый клиент (основной)
client_primary = pytumblr.TumblrRestClient(
    'plqKbbtkiJQN0TWO2mjx8kHg5J9yWm28PpyK82NBVMkESNG4iK',
    'SWosE8lRDLH4PD3pYjd7hvoCVpcBnTVPi7JdiXhykl7q7xpyQC',
    'xUnUdemqpex63N8un5pMk6SUnyiCnaXqEBa3oqTNxWe9eO42hX',
    'cyycRMfChvva4utwkih2yMz9QLxy9YzyZYLxdVXi1BVmGQ8F88'
)

# 🔐 Второй клиент (резерв)
client_backup = pytumblr.TumblrRestClient(
    'VZkceLUE4MkQBuAL7h8xMALUlB5ySJTHjDwqOgIteYelmi3Lal',
    'BlJv13NYW5JlQ8RX7gzsuVwwxf6BWLvCCDyeSuiqZ8wAEvYPjg',
    'bT78woryaO3vKsw8C5N1nwlOyFAbwd1BfAMrOLYsa4lohsxJSu',
    'ODAE5OaoQVnD5SyVVZhzITrME0ysxFQhThd7vnJpJhqtj9QoBu'
)


async def fetch_posts(client, tag, seen_urls, session, limit=100):
    posts = []
    before = None

    try:
        while len(posts) < limit:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.tagged(tag=tag, limit=20, before=before)
            )

            if not isinstance(response, list):
                break

            for post in response:
                if post.get("type") != "text":
                    continue

                body = post.get("body", "")
                if not body:
                    continue

                if tag.lower() not in body.lower():
                    continue

                post_url = post.get("post_url")
                if post_url in seen_urls:
                    continue

                posts.append({
                    "type": post.get("type"),
                    "summary": post.get("summary"),
                    "post_url": post_url,
                    "blog_name": post.get("blog_name"),
                    "timestamp": post.get("timestamp"),
                    "tags": post.get("tags"),
                    "id": post.get("id"),
                    "title": post.get("title"),
                    "body": body
                })

                if len(posts) >= limit:
                    break

            if len(response) < 20:
                break

            before = response[-1]["id"]

    except Exception as e:
        print(f"Ошибка при запросе: {e}")

    return posts


async def get_tumblr_posts_by_tag(tag: str, seen_urls: List[str], limit: int = 100) -> List[dict]:
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=40)) as session:
            posts = await fetch_posts(client_primary, tag, seen_urls, session, limit)
            if posts:
                return posts
            print("Пробуем резервный клиент...")
            return await fetch_posts(client_backup, tag, seen_urls, session, limit)
    except asyncio.TimeoutError:
        print("⏱ Превышено время ожидания Tumblr API.")
        return []
    except Exception as e:
        print(f"❌ Общая ошибка: {e}")
        return []


