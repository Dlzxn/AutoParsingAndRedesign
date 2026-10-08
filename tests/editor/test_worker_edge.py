"""Очередь рендера и API редактора: ошибки, отмена, истёкшие файлы."""
import asyncio
import json
import shutil
import time

import pytest

from app.db.models import MediaSource, RenderJob
from app.editor import worker as worker_module
from app.media import fetch
from app.media.ffmpeg import MediaError, MediaInfo
from tests.conftest import requires_ffmpeg
from tests.editor.test_editor_api import create_job, upload, wait_job

pytestmark = [requires_ffmpeg, pytest.mark.ffmpeg]


@pytest.fixture
async def source(user_client, media_dir):
    return (await upload(user_client, media_dir / "landscape.mp4")).json()


async def test_worker_survives_crash_in_process(app, user_client, source, monkeypatch):
    queue = app.state.render_queue
    real = queue._process
    calls = []

    async def flaky(job_id):
        calls.append(job_id)
        if len(calls) == 1:
            raise RuntimeError("unexpected")
        await real(job_id)

    monkeypatch.setattr(queue, "_process", flaky)
    first = (await create_job(user_client, source["id"], {"quality": "draft"})).json()
    second = (await create_job(user_client, source["id"], {"quality": "draft"})).json()
    assert (await wait_job(user_client, second["id"]))["status"] == "done"
    assert first["id"] in calls  # первая задача упала, но воркер продолжил работу


async def test_unknown_job_is_ignored(app):
    queue = app.state.render_queue
    await queue.enqueue("0" * 32)
    await asyncio.wait_for(queue.queue.join(), 10)
    assert "0" * 32 not in queue.progress


async def test_job_fails_when_source_deleted(app, user_client, source, db):
    queue = app.state.render_queue
    await queue.stop()
    job = (await create_job(user_client, source["id"])).json()
    # источник удаляется (например, очисткой), а задача ещё в очереди
    await db.execute(MediaSource.__table__.update().where(MediaSource.id == source["id"]).values(id=source["id"]))
    await db.commit()

    async def no_source(db_, model, key):
        return None if model is MediaSource else await original_get(db_, model, key)

    original_get = type(db).get
    from sqlalchemy.ext.asyncio import AsyncSession

    async def patched_get(self, model, key, **kwargs):
        if model is MediaSource:
            return None
        return await original_get(self, model, key, **kwargs)

    AsyncSession.get, saved = patched_get, AsyncSession.get
    try:
        queue.queue = asyncio.Queue()
        await queue.start()
        result = await wait_job(user_client, job["id"])
    finally:
        AsyncSession.get = saved
    assert result["status"] == "failed" and "удалено" in result["error"]


async def test_output_without_video_is_failure(app, user_client, source, monkeypatch):
    real_probe = worker_module.probe

    def fake_probe(path, *args):
        if str(path).endswith("output.mp4"):
            return MediaInfo(duration=1, width=0, height=0, has_audio=True, has_video=False)
        return real_probe(path, *args)

    monkeypatch.setattr(worker_module, "probe", fake_probe)
    job = await wait_job(user_client, (await create_job(user_client, source["id"], {"quality": "draft"})).json()["id"])
    assert job["status"] == "failed" and job["error"] == "Не удалось обработать видео"


async def test_unexpected_render_error(app, user_client, source, monkeypatch):
    def boom(*args, **kwargs):
        raise KeyError("bug")

    monkeypatch.setattr(worker_module, "plan_render", boom)
    job = await wait_job(user_client, (await create_job(user_client, source["id"])).json()["id"])
    assert job["status"] == "failed" and job["error"] == "Внутренняя ошибка обработки видео"


async def test_shutdown_during_render_requeues_job(app, user_client, source, db, monkeypatch):
    def slow_ffmpeg(*args, **kwargs):
        time.sleep(1.0)
        raise MediaError("Обработка отменена")

    monkeypatch.setattr(worker_module, "run_ffmpeg", slow_ffmpeg)
    job = (await create_job(user_client, source["id"])).json()
    for _ in range(50):
        if (await user_client.get(f"/api/editor/jobs/{job['id']}")).json()["status"] == "processing":
            break
        await asyncio.sleep(0.1)
    await app.state.render_queue.stop()
    await db.close()
    row = await db.get(RenderJob, job["id"])
    assert row.status == "queued"  # после перезапуска задача будет выполнена заново
    await asyncio.sleep(1.2)  # даём фоновому потоку завершиться


async def test_source_file_deleted_from_disk(user_client, source, app):
    shutil.rmtree(app.state.storage.source_dir(source["id"]))
    response = await user_client.get(source["preview_url"])
    assert response.status_code == 404 and response.json()["detail"] == "Файл удалён"


async def test_result_file_expired(user_client, source, app):
    job = await wait_job(user_client, (await create_job(user_client, source["id"], {"quality": "draft"})).json()["id"])
    (app.state.storage.job_dir(job["id"]) / "output.mp4").unlink()
    response = await user_client.get(job["download_url"])
    assert response.status_code == 404 and "Срок хранения" in response.json()["detail"]


async def test_upload_rejected_by_content_length(user_client, settings):
    settings.max_upload_mb = 1
    response = await user_client.post(
        "/api/editor/sources/upload",
        content=b"x" * 10,
        headers={"content-type": "multipart/form-data; boundary=x", "content-length": str(50 * 1024 * 1024)},
    )
    # Ответ приходит до разбора тела запроса (иначе было бы 400 из-за некорректного multipart)
    assert response.status_code == 413
    assert "максимум 1 МБ" in response.json()["detail"]


async def test_empty_upload(user_client):
    response = await user_client.post("/api/editor/sources/upload", files={"file": ("empty.mp4", b"", "video/mp4")})
    assert response.status_code == 400 and response.json()["detail"] == "Файл пустой"


async def test_audio_file_is_not_a_video(user_client, media_dir):
    response = await upload(user_client, media_dir / "music.mp3", name="music.mp4")
    assert response.status_code == 400 and "не содержит видео" in response.json()["detail"]


async def test_failed_url_download_cleans_directory(user_client, app, monkeypatch):
    def failing(url, dest_dir, options, on_progress=None):
        dest_dir.mkdir(parents=True, exist_ok=True)
        (dest_dir / "source.part").write_bytes(b"partial")
        raise MediaError("Видео недоступно или удалено")

    monkeypatch.setattr(fetch, "download", failing)
    response = await user_client.post("/api/editor/sources/url", json={"url": "https://coub.com/view/x"})
    assert response.status_code == 400
    assert list((app.state.storage.root / "sources").iterdir()) == []
    response = await user_client.get("/api/download", params={"url": "https://coub.com/view/x"})
    assert response.status_code == 400
    assert list((app.state.storage.root / "tmp").iterdir()) == []


@pytest.mark.parametrize(
    ("content", "detail"),
    [(b"1\n00:00:00,000 --> 00:00:01,000\n" + b"x" * (1024 * 1024), "слишком большой"),
     (b"1\n00:00:00,000 --> 00:00:01,000\n\x98\x98", "Не удалось прочитать")],
    ids=["too-big", "bad-encoding"],
)
async def test_bad_subtitles(user_client, source, content, detail):
    response = await create_job(user_client, source["id"], {}, {"subtitles": ("s.srt", content, "text/plain")})
    assert response.status_code == 400 and detail in response.json()["detail"]


async def test_delete_user_removes_media(admin_client, user_client, source, app):
    job = await wait_job(user_client, (await create_job(user_client, source["id"], {"quality": "draft"})).json()["id"])
    storage = app.state.storage
    users = (await admin_client.get("/api/admin/users")).json()["users"]
    user_id = next(u["id"] for u in users if u["email"] == "user@example.com")
    assert (await admin_client.delete(f"/api/admin/users/{user_id}")).status_code == 204
    assert not storage.source_dir(source["id"]).exists()
    assert not storage.job_dir(job["id"]).exists()


async def test_params_json_must_be_object(user_client, source):
    response = await user_client.post("/api/editor/jobs", data={"source_id": source["id"], "params": json.dumps([1, 2])})
    assert response.status_code == 422
