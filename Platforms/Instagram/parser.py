import instaloader

parser = instaloader.Instaloader()

def get_videos_from_instagram(tag: str, list_videos: list[str], par = parser) -> list[str]:
    for post in instaloader.Hashtag.from_name(par.context, tag).get_posts():
        print(post.url)

get_videos_from_instagram("mother", [])
