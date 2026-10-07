"""Редактор через HTTP API: исходники, задачи рендера, очередь, права доступа."""
import asyncio
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.db.models import RenderJob
from app.media import fetch
from tests.conftest import requires_ffmpeg

pytestmark = [requires_ffmpeg, pytest.mark.ffmpeg]


async def upload(client, path: Path, name: str | None = None):
    with path.open("rb") as f:
        return await client.post("/api/editor/sources/upload", files={"file": (name or path.name, f, "video/mp4")})


async def wait_job(client, job_id: str, timeout: float = 60) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        job = (await client.get(f"/api/editor/jobs/{job_id}")).json()
        if job["status"] in ("done", "failed"):
            return job
        assert asyncio.get_running_loop().time() < deadline, f"job stuck: {job}"
        await asyncio.sleep(0.2)


async def create_job(client, source_id: str, params: dict | None = None, files: dict | None = None):
    return await client.post("/api/editor/jobs", data={"source_id": source_id, "params": json.dumps(params or {})},
                             files=files)


@pytest.fixture
async def source(user_client, media_dir):
    response = await upload(user_client, media_dir / "landscape.mp4")
    assert response.status_code == 201, response.text
    return response.json()


# ---------- Исходники ----------

async def test_upload_source(source):
    assert source["duration"] == pytest.approx(4, abs=0.1)
    assert (source["width"], source["height"]) == (640, 360)
    assert source["has_audio"] is True
    assert source["preview_url"] == f"/api/editor/sources/{source['id']}/file"


async def test_source_preview_supports_range(user_client, source):
    response = await user_client.get(source["preview_url"], headers={"Range": "bytes=0-99"})
    assert response.status_code == 206
    assert len(response.content) == 100


async def test_upload_requires_login(client, media_dir):
    assert (await upload(client, media_dir / "landscape.mp4")).status_code == 401


@pytest.mark.parametrize(("name", "detail"), [("video.exe", "формат"), ("broken.mp4", "повреждён")])
async def test_upload_rejects_bad_files(user_client, media_dir, name, detail):
    response = await upload(user_client, media_dir / "broken.mp4", name=name)
    assert response.status_code == 400
    assert detail in response.json()["detail"]


async def test_upload_size_limit(user_client, media_dir, settings):
    settings.max_upload_mb = 0
    response = await upload(user_client, media_dir / "landscape.mp4")
    assert response.status_code in (400, 413)
    assert "слишком большой" in response.json()["detail"]


async def test_upload_too_long_video(user_client, media_dir, settings):
    settings.max_source_duration = 2
    response = await upload(user_client, media_dir / "landscape.mp4")
    assert response.status_code == 400
    assert "длинное" in response.json()["detail"]


async def test_failed_upload_leaves_no_files(user_client, media_dir, settings):
    await upload(user_client, media_dir / "broken.mp4")
    assert list((settings.storage_dir / "sources").iterdir()) == []


async def test_source_from_url_marks_history(user_client, media_dir, monkeypatch, app):
    def fake_download(url, dest_dir, options):
        dest_dir.mkdir(parents=True, exist_ok=True)
        target = dest_dir / "source.mp4"
        shutil.copy(media_dir / "landscape.mp4", target)
        return target

    monkeypatch.setattr(fetch, "download", fake_download)
    url = "https://www.youtube.com/watch?v=abc"
    response = await user_client.post("/api/editor/sources/url", json={"url": url})
    assert response.status_code == 201, response.text
    assert response.json()["origin_url"] == url

    from tests.search.test_service import FakeProvider
    from app.search.base import SearchItem

    app.state.search.providers["yt"] = FakeProvider(items=[SearchItem(id="abc", title="t", url=url)])
    items = (await user_client.get("/api/search/yt", params={"q": "cats"})).json()["items"]
    assert items == []  # отредактированный клип больше не показывается


async def test_source_from_foreign_url_rejected(user_client):
    response = await user_client.post("/api/editor/sources/url", json={"url": "http://127.0.0.1/secret"})
    assert response.status_code == 400
    assert "не поддерживается" in response.json()["detail"]


async def test_sources_are_private(other_client, source):
    assert (await other_client.get(f"/api/editor/sources/{source['id']}")).status_code == 404
    assert (await other_client.get(source["preview_url"])).status_code == 404
    response = await create_job(other_client, source["id"])
    assert response.status_code == 404


# ---------- Задачи рендера ----------

async def test_render_job_full_cycle(user_client, source, media_dir):
    params = {"trim_start": 0.5, "trim_end": 3, "aspect": "9:16", "fit": "blur", "resolution": "480",
              "text": "Привет", "quality": "draft"}
    files = {
        "logo": ("logo.png", (media_dir / "logo.png").read_bytes(), "image/png"),
        "music": ("music.mp3", (media_dir / "music.mp3").read_bytes(), "audio/mpeg"),
        "subtitles": ("subs.srt", (media_dir / "subs_cp1251.srt").read_bytes(), "text/plain"),
    }
    response = await create_job(user_client, source["id"], params, files)
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["status"] == "queued"
    assert job["params"]["aspect"] == "9:16"
    assert not any(k.startswith("_") for k in job["params"])  # служебные поля не отдаются

    job = await wait_job(user_client, job["id"])
    assert job["status"] == "done", job
    assert job["progress"] == 1.0
    assert job["output_duration"] == pytest.approx(2.5, abs=0.15)
    assert job["output_size"] > 0

    inline = await user_client.get(job["result_url"])
    assert inline.status_code == 200
    assert inline.headers["content-type"] == "video/mp4"
    assert inline.headers["content-disposition"].startswith("inline")
    download = await user_client.get(job["download_url"])
    assert download.headers["content-disposition"].startswith("attachment")
    assert len(download.content) == job["output_size"]

    jobs = (await user_client.get("/api/editor/jobs")).json()
    assert [j["id"] for j in jobs] == [job["id"]]


async def test_parallel_jobs_from_different_users(user_client, other_client, media_dir):
    own = (await upload(user_client, media_dir / "landscape.mp4")).json()
    their = (await upload(other_client, media_dir / "vertical_silent.mp4")).json()
    jobs = [
        (await create_job(user_client, own["id"], {"speed": 2, "quality": "draft"})).json(),
        (await create_job(other_client, their["id"], {"aspect": "1:1", "quality": "draft"})).json(),
    ]
    results = await asyncio.gather(wait_job(user_client, jobs[0]["id"]), wait_job(other_client, jobs[1]["id"]))
    assert [r["status"] for r in results] == ["done", "done"]
    assert (await other_client.get(f"/api/editor/jobs/{jobs[0]['id']}")).status_code == 404
    assert (await other_client.get(f"/api/editor/jobs/{jobs[0]['id']}/result")).status_code == 404


@pytest.mark.parametrize(
    ("params", "detail"),
    [
        ({"speed": 10}, "Скорость: должно быть не больше 4"),
        ({"trim_start": 3, "trim_end": 1}, "Конец фрагмента должен быть позже начала"),
        ({"aspect": "2:1"}, "Формат кадра: недопустимое значение"),
        ({"bogus": 1}, "bogus: неизвестный параметр"),
    ],
)
async def test_invalid_params(user_client, source, params, detail):
    response = await create_job(user_client, source["id"], params)
    assert response.status_code == 422
    assert response.json()["detail"] == detail


async def test_invalid_params_json(user_client, source):
    response = await user_client.post("/api/editor/jobs", data={"source_id": source["id"], "params": "{oops"})
    assert response.status_code == 422


async def test_trim_beyond_source(user_client, source):
    response = await create_job(user_client, source["id"], {"trim_start": 100})
    assert response.status_code == 400


@pytest.mark.parametrize(
    ("field", "filename", "content", "detail"),
    [
        ("logo", "logo.gif", b"GIF89a", "формат"),
        ("music", "music.exe", b"MZ", "формат"),
        ("subtitles", "subs.txt", b"1\n00:00:00,000 --> 00:00:01,000\nx", ".srt"),
        ("subtitles", "subs.srt", b"just text without timings", "не похож"),
    ],
)
async def test_invalid_assets(user_client, source, field, filename, content, detail):
    response = await create_job(user_client, source["id"], {}, {field: (filename, content, "application/octet-stream")})
    assert response.status_code == 400
    assert detail in response.json()["detail"]


async def test_active_jobs_limit(user_client, source, app):
    await app.state.render_queue.stop()  # останавливаем воркеры, чтобы задачи копились
    for _ in range(3):
        assert (await create_job(user_client, source["id"])).status_code == 202
    response = await create_job(user_client, source["id"])
    assert response.status_code == 429


async def test_result_before_done(user_client, source, app):
    await app.state.render_queue.stop()
    job = (await create_job(user_client, source["id"])).json()
    response = await user_client.get(f"/api/editor/jobs/{job['id']}/result")
    assert response.status_code == 409


async def test_failed_render_is_reported(user_client, source, app, settings):
    settings.ffmpeg_path = "definitely-missing-ffmpeg"
    job = (await create_job(user_client, source["id"])).json()
    job = await wait_job(user_client, job["id"])
    assert job["status"] == "failed"
    assert job["error"]


async def test_unfinished_jobs_resume_after_restart(user_client, source, app, db):
    queue = app.state.render_queue
    await queue.stop()
    job = (await create_job(user_client, source["id"], {"quality": "draft"})).json()
    row = await db.get(RenderJob, job["id"])
    row.status = "processing"  # как будто сервер упал во время рендера
    await db.commit()
    queue.queue = asyncio.Queue()
    await queue.start()
    assert (await wait_job(user_client, job["id"]))["status"] == "done"


# ---------- Скачивание клипов ----------

async def test_download_endpoint(user_client, media_dir, monkeypatch):
    def fake_download(url, dest_dir, options):
        dest_dir.mkdir(parents=True, exist_ok=True)
        target = dest_dir / "source.mp4"
        shutil.copy(media_dir / "landscape.mp4", target)
        return target

    monkeypatch.setattr(fetch, "download", fake_download)
    response = await user_client.get("/api/download", params={"url": "https://coub.com/view/abc"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "video/mp4"
    assert 'filename="coub_clip.mp4"' in response.headers["content-disposition"]
    assert response.content == (media_dir / "landscape.mp4").read_bytes()


async def test_download_validation(user_client, client):
    assert (await client.get("/api/download", params={"url": "https://coub.com/view/abc"})).status_code == 401
    response = await user_client.get("/api/download", params={"url": "http://10.0.0.1/x.mp4"})
    assert response.status_code == 400


async def test_download_disabled_platform(user_client, db):
    from app.db.models import Platform

    (await db.get(Platform, "coub")).enabled = False
    await db.commit()
    response = await user_client.get("/api/download", params={"url": "https://coub.com/view/abc"})
    assert response.status_code == 503


# ---------- Очистка устаревших файлов ----------

async def test_cleanup_removes_expired_media(user_client, source, app, db, settings):
    from datetime import timedelta

    from app.db.models import MediaSource
    from app.maintenance import cleanup_once

    job = await wait_job(user_client, (await create_job(user_client, source["id"], {"quality": "draft"})).json()["id"])
    storage = app.state.storage
    assert storage.source_dir(source["id"]).exists() and storage.job_dir(job["id"]).exists()

    old = datetime.now(timezone.utc) - timedelta(hours=settings.media_ttl_hours + 1)
    (await db.get(MediaSource, source["id"])).created_at = old
    (await db.get(RenderJob, job["id"])).created_at = old
    await db.commit()

    result = await cleanup_once(settings, storage)
    assert result["sources"] == 1 and result["jobs"] == 1
    assert not storage.source_dir(source["id"]).exists()
    assert not storage.job_dir(job["id"]).exists()
    assert (await user_client.get(f"/api/editor/sources/{source['id']}")).status_code == 404
