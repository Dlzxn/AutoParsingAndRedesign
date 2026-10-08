"""Анализ файлов (ffprobe) и скачивание по ссылкам (yt-dlp)."""
from pathlib import Path

import pytest

from app.media import fetch
from app.media.ffmpeg import MediaError, parse_probe, probe, resolve_binary
from tests.conftest import requires_ffmpeg

# ---------- ffprobe ----------


def _probe_data(rotation=None, tags_rotate=None, attached_pic=False, duration="5.5"):
    video = {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080, "avg_frame_rate": "30000/1001"}
    if rotation is not None:
        video["side_data_list"] = [{"side_data_type": "Display Matrix", "rotation": rotation}]
    if tags_rotate is not None:
        video["tags"] = {"rotate": tags_rotate}
    streams = [video, {"codec_type": "audio", "codec_name": "aac"}]
    if attached_pic:
        streams.insert(0, {"codec_type": "video", "width": 300, "height": 300, "disposition": {"attached_pic": 1}})
    return {"streams": streams, "format": {"duration": duration}}


def test_parse_probe_basic():
    info = parse_probe(_probe_data())
    assert (info.width, info.height, info.duration) == (1920, 1080, 5.5)
    assert info.has_audio and info.has_video
    assert info.fps == pytest.approx(29.97, abs=0.01)


@pytest.mark.parametrize("data", [_probe_data(rotation=-90), _probe_data(rotation=90), _probe_data(tags_rotate="270")])
def test_parse_probe_rotated_phone_video(data):
    info = parse_probe(data)
    assert (info.width, info.height) == (1080, 1920)


def test_parse_probe_ignores_cover_art():
    assert parse_probe(_probe_data(attached_pic=True)).width == 1920


def test_parse_probe_audio_only_and_missing_duration():
    info = parse_probe({"streams": [{"codec_type": "audio"}], "format": {}})
    assert not info.has_video and info.duration == 0


@requires_ffmpeg
def test_probe_real_files(media_dir):
    landscape = probe(media_dir / "landscape.mp4")
    assert (landscape.width, landscape.height) == (640, 360)
    assert landscape.has_audio and landscape.duration == pytest.approx(4, abs=0.1)
    silent = probe(media_dir / "vertical_silent.mp4")
    assert not silent.has_audio and silent.height > silent.width


@requires_ffmpeg
def test_probe_broken_file(media_dir):
    with pytest.raises(MediaError, match="повреждён"):
        probe(media_dir / "broken.mp4")


def test_missing_binary():
    with pytest.raises(MediaError, match="Не найден"):
        resolve_binary("definitely-not-ffmpeg-binary")


# ---------- Разрешённые ссылки (защита от SSRF) ----------

@pytest.mark.parametrize(
    ("url", "platform"),
    [
        ("https://www.youtube.com/watch?v=abc", "yt"),
        ("https://youtu.be/abc", "yt"),
        ("https://m.youtube.com/shorts/abc", "yt"),
        ("https://vk.com/video-1_2", "vk"),
        ("https://vkvideo.ru/clip-1_2", "vk"),
        ("https://coub.com/view/abc", "coub"),
        ("https://attachments-cdn-s.coub.com/x/y.mp4", "coub"),
        ("https://www.reddit.com/r/a/comments/b/", "reddit"),
        ("https://v.redd.it/abc", "reddit"),
        ("https://i.imgur.com/abc.mp4", "imgur"),
        ("https://blog.tumblr.com/post/1", "tumblr"),
        ("HTTPS://WWW.YOUTUBE.COM/watch?v=abc", "yt"),
    ],
)
def test_allowed_urls(url, platform):
    assert fetch.platform_for_url(url) == platform
    assert fetch.validate_url(f"  {url}  ") == url


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/admin",
        "http://localhost/video.mp4",
        "http://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
        "ftp://youtube.com/video",
        "https://evilyoutube.com/watch",
        "https://youtube.com.evil.example/watch",
        "https://user:pass@youtube.com/watch",
        "https://youtube.com:8443/watch",
        "javascript:alert(1)",
        "",
        "https://youtube.com/" + "a" * 3000,
    ],
)
def test_rejected_urls(url):
    with pytest.raises(MediaError, match="не поддерживается"):
        fetch.validate_url(url)


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("ERROR: Video too long: duration 9999s", "длинное"),
        ("ERROR: File is larger than max-filesize", "большое"),
        ("ERROR: This video is private", "приватное"),
        ("ERROR: Sign in to confirm your age", "приватное"),
        ("ERROR: Video unavailable", "недоступно"),
        ("ERROR: HTTP Error 404: Not Found", "недоступно"),
        ("ERROR: Read timed out", "ожидания"),
        ("ERROR: something weird", "Не удалось скачать"),
    ],
)
def test_friendly_download_errors(message, expected):
    assert expected in fetch._friendly_error(message)


# ---------- yt-dlp (подменённый) ----------

class FakeYDL:
    """Минимальная подмена yt_dlp.YoutubeDL (двухфазное извлечение: метаданные, затем скачивание)."""

    instances: list[dict] = []
    info: dict = {"duration": 10, "title": "Котики"}
    error: Exception | None = None
    write_file = True

    def __init__(self, params):
        FakeYDL.instances.append(params)

    @property
    def last_params(self):
        return FakeYDL.instances[-1]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download=True, process=True):
        assert download is False and process is False  # сначала только метаданные
        if FakeYDL.error:
            raise FakeYDL.error
        return dict(FakeYDL.info)

    def process_ie_result(self, info, download=True):
        params = FakeYDL.instances[-1]
        path = Path(params["outtmpl"].replace("%(ext)s", "mp4"))
        for hook in params["progress_hooks"]:
            hook({"status": "downloading", "filename": str(path), "downloaded_bytes": 50, "total_bytes": 100})
        if FakeYDL.write_file:
            path.write_bytes(b"video-bytes")
        return {**info, "requested_downloads": [{"filepath": str(path)}]}


@pytest.fixture
def fake_ydl(monkeypatch):
    import yt_dlp

    FakeYDL.info, FakeYDL.error, FakeYDL.write_file = {"duration": 10, "title": "Котики"}, None, True
    FakeYDL.instances = []
    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYDL)
    return FakeYDL


OPTIONS = fetch.FetchOptions(max_duration=60, max_bytes=1000, timeout=30, proxy="http://proxy:3128",
                             js_runtimes=("node",))


def test_download_success_and_options(fake_ydl, tmp_path):
    progress: list[float] = []
    result = fetch.download("https://www.youtube.com/watch?v=abc", tmp_path / "dl", OPTIONS, progress.append)
    assert result.path.read_bytes() == b"video-bytes"
    assert result.title == "Котики"
    assert progress[0] == 0.02 and 0.4 < progress[1] < 0.6 and progress[-1] == 1.0
    params = fake_ydl.instances[-1]
    assert params["noplaylist"] is True
    assert params["max_filesize"] == 1000
    assert params["proxy"] == "http://proxy:3128"
    assert params["js_runtimes"] == {"node": {}}
    assert params["merge_output_format"] == "mp4"
    assert params["format"] == fetch.format_for(10)


def test_format_depends_on_duration():
    assert "[height<=?1920][width<=?1920]" in fetch.format_for(30)  # вертикальный 1080x1920 тоже проходит
    assert "[height<=?1280][width<=?1280]" in fetch.format_for(600)  # длинные — 720p, быстрее
    assert fetch.format_for(None).endswith("/b")


def test_playlist_rejected(fake_ydl, tmp_path):
    fake_ydl.info = {"_type": "playlist", "entries": []}
    with pytest.raises(MediaError, match="плейлист"):
        fetch.download("https://www.youtube.com/playlist?list=x", tmp_path / "dl", OPTIONS)


def test_download_rejects_long_video_before_downloading(fake_ydl, tmp_path):
    fake_ydl.info = {"duration": 3600}
    with pytest.raises(MediaError, match="длинное"):
        fetch.download("https://www.youtube.com/watch?v=abc", tmp_path / "dl", OPTIONS)
    assert len(fake_ydl.instances) == 1  # до второй фазы (скачивания) не дошло


def test_download_error_is_translated(fake_ydl, tmp_path):
    from yt_dlp.utils import DownloadError

    fake_ydl.error = DownloadError("ERROR: [youtube] abc: Private video")
    with pytest.raises(MediaError, match="приватное"):
        fetch.download("https://www.youtube.com/watch?v=abc", tmp_path / "dl", OPTIONS)


def test_download_unexpected_crash(fake_ydl, tmp_path):
    fake_ydl.error = RuntimeError("extractor exploded")
    with pytest.raises(MediaError, match="Не удалось скачать"):
        fetch.download("https://www.youtube.com/watch?v=abc", tmp_path / "dl", OPTIONS)


def test_download_without_file(fake_ydl, tmp_path):
    fake_ydl.write_file = False
    with pytest.raises(MediaError, match="недоступно"):
        fetch.download("https://www.youtube.com/watch?v=abc", tmp_path / "dl", OPTIONS)


def test_download_refuses_foreign_url(fake_ydl, tmp_path):
    with pytest.raises(MediaError):
        fetch.download("http://192.168.0.1/router", tmp_path / "dl", OPTIONS)
    assert fake_ydl.instances == []
