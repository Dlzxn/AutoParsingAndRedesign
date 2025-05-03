import aiohttp, asyncio


async def get_video(tag: str, url_list: list, limit: int = 30) -> list[str]:
    new_list_videos: list = []
    for page in range(1, 8):
        print(page)
        if len(new_list_videos) < limit:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://coub.com/api/v2/smart_search/general_search?search_query={tag}&page={page}") as resp:
                    data = await resp.json()
                    coubs = data['coubs']
                    for coub in coubs:
                        url = ""
                        print(coub["file_versions"]["share"]["default"])
                        url = coub["file_versions"]["share"]["default"]
                        if url not in url_list and url != "":
                            new_list_videos.append(url)
        else:
            return new_list_videos
    return new_list_videos


#
# asyncio.run(get_video("car", []))
