import pytumblr

# 🔑 Ключи доступа
client = pytumblr.TumblrRestClient(
    'plqKbbtkiJQN0TWO2mjx8kHg5J9yWm28PpyK82NBVMkESNG4iK',
    'SWosE8lRDLH4PD3pYjd7hvoCVpcBnTVPi7JdiXhykl7q7xpyQC',
    'xUnUdemqpex63N8un5pMk6SUnyiCnaXqEBa3oqTNxWe9eO42hX',
    'cyycRMfChvva4utwkih2yMz9QLxy9YzyZYLxdVXi1BVmGQ8F88'
)


def get_tumblr_posts_by_tag(tag, limit=100):
    """
    Возвращает список постов с Tumblr, соответствующих указанному тегу.

    :param tag: Тег для поиска.
    :param limit: Максимальное количество постов.
    :return: Список словарей с данными постов.
    """
    posts = []
    before = None

    while len(posts) < limit:
        response = client.tagged(tag=tag, limit=20, before=before)
        if not response:
            break

        posts.extend(response)

        if len(response) < 20:
            break

        before = response[-1]['id']

    # Обрезаем, если постов больше, чем нужно
    posts = posts[:limit]

    result = []
    for post in posts:
        post_data = {
            "type": post.get("type"),
            "summary": post.get("summary"),
            "post_url": post.get("post_url"),
            "blog_name": post.get("blog_name"),
            "timestamp": post.get("timestamp"),
            "tags": post.get("tags"),
            "id": post.get("id"),
        }

        if post["type"] == "video":
            post_data["video_url"] = post.get("video_url")
        elif post["type"] == "photo":
            post_data["photos"] = [p.get("original_size", {}).get("url") for p in post.get("photos", [])]
        elif post["type"] == "text":
            post_data["title"] = post.get("title")
            post_data["body"] = post.get("body")

        result.append(post_data)

    return result
