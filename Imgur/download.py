import asyncio

async def download_video_imgur(url: str, output_path: str):
    process = await asyncio.create_subprocess_exec(
        "yt-dlp",
        "-f", "mp4",
        "-o", output_path,
        url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {stderr.decode()}")
    else:
        print(f"Downloaded to {output_path}")

    return output_path