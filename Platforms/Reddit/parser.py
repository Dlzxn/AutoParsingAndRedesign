import praw

reddit = praw.Reddit(
    client_id="t5Q8V3mokjFBaNCfyTU5wA",          # короткая строка
    client_secret="YQiXwMWsITnXBIUGWe7FNHLCd4HcvQ",      # длинная строка
    user_agent="MyRedditScraperScript/0.1"
)

def find_vertical_shorts_by_tag(tag: str, used_videos: list[str], limit: int = 500) \
        -> list[dict[str, str, str]]:
    """
    Function for search videos in Reddit
    :param tag: string tag for search
    :param used_videos: list with urls of videos? which we used
    :param limit: integer limit videos
    :return: list of dicts with dict with video info
    """
    results = []
    for post in reddit.subreddit("all").search(tag, sort="new", limit=limit):
        if not hasattr(post, "media") or not post.is_video:
            continue

        video = post.media.get("reddit_video")
        if not video:
            continue

        duration = video.get("duration", 0)
        height = video.get("height", 0)
        width = video.get("width", 1)  # избегаем деления на 0

        # is_vertical = height > width
        # is_short = duration <= 120

        if post.media["reddit_video"]["fallback_url"] not in used_videos: #is_vertical and is_short
            results.append({
                "title": post.title,
                "url": post.media["reddit_video"]["fallback_url"],
                "duration": duration,
            })

    return results