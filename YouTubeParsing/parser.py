import asyncio
import aiohttp
import os
import re

YOUTUBE_API_KEY = 'AIzaSyDLrxOicXiRkPBdg-8R-6Fqirpa-W4pfAU'  # 🔒 Вставь свой ключ здесь
SEARCH_URL = 'https://www.googleapis.com/youtube/v3/search'
VIDEOS_URL = 'https://www.googleapis.com/youtube/v3/videos'

def parse_duration(duration_str):
    pattern = r'PT((?P<hours>\d+)H)?((?P<minutes>\d+)M)?((?P<seconds>\d+)S)?'
    match = re.match(pattern, duration_str)
    if not match:
        return 0
    parts = match.groupdict()
    hours = int(parts['hours']) if parts['hours'] else 0
    minutes = int(parts['minutes']) if parts['minutes'] else 0
    seconds = int(parts['seconds']) if parts['seconds'] else 0
    return hours * 3600 + minutes * 60 + seconds

async def get_video_details(session, video_ids):
    params = {
        'part': 'contentDetails',
        'id': ','.join(video_ids),
        'key': YOUTUBE_API_KEY
    }
    async with session.get(VIDEOS_URL, params=params) as resp:
        data = await resp.json()
        durations = {}
        for item in data.get('items', []):
            vid = item['id']
            duration_str = item['contentDetails']['duration']
            total_seconds = parse_duration(duration_str)
            durations[vid] = total_seconds
        return durations

async def search_youtube(tag, clips):
    async with aiohttp.ClientSession() as session:
        params = {
            'part': 'snippet',
            'q': tag,
            'type': 'video',
            'maxResults': 20,
            'key': YOUTUBE_API_KEY
        }
        async with session.get(SEARCH_URL, params=params) as resp:
            data = await resp.json()
            video_items = data.get('items', [])
            video_ids = [item['id']['videoId'] for item in video_items]

        durations = await get_video_details(session, video_ids)

        # Отфильтруем по длительности <= 60 секунд
        results = []
        for item in video_items:
            vid = item['id']['videoId']
            if durations.get(vid, 9999) <= 60 and f'https://www.youtube.com/watch?v={vid}' not in clips:
                video_data = {
                    'title': item['snippet']['title'],
                    'url': f'https://www.youtube.com/watch?v={vid}',
                    'duration': durations[vid]
                }
                results.append(video_data)

        return results


