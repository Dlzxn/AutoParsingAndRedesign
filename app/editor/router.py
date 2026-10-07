import json
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, ValidationError

from app.auth.deps import CurrentUser, DbSession, PageUser
from app.core.errors import humanize_validation_error
from app.editor.schemas import EditParams, JobOut, SourceOut
from app.editor.service import EditorService, job_out, source_out
from app.web.templating import render

router = APIRouter(tags=["editor"])


def get_editor(request: Request) -> EditorService:
    return request.app.state.editor


class SourceUrl(BaseModel):
    url: str


@router.get("/editor", include_in_schema=False)
async def editor_page(request: Request, user: PageUser, url: str | None = None):
    return render(request, "editor.html", initial_url=url or "")


@router.get("/VideoEditor", include_in_schema=False)
@router.get("/VideoEditor/", include_in_schema=False)
async def legacy_editor_redirect():
    return RedirectResponse("/editor", status.HTTP_301_MOVED_PERMANENTLY)


@router.post("/api/editor/sources/upload", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
async def upload_source(request: Request, db: DbSession, user: CurrentUser, file: UploadFile = File(...)):
    editor = get_editor(request)
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > editor.media.max_upload_bytes + 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            f"Файл слишком большой (максимум {editor.media.settings.max_upload_mb} МБ)")
    return source_out(await editor.create_source_from_upload(db, user, file))


@router.post("/api/editor/sources/url", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
async def source_from_url(data: SourceUrl, request: Request, db: DbSession, user: CurrentUser):
    return source_out(await get_editor(request).create_source_from_url(db, user, data.url))


@router.get("/api/editor/sources/{source_id}", response_model=SourceOut)
async def get_source(source_id: str, request: Request, db: DbSession, user: CurrentUser):
    return source_out(await get_editor(request).get_source(db, user, source_id))


@router.get("/api/editor/sources/{source_id}/file")
async def source_file(source_id: str, request: Request, db: DbSession, user: CurrentUser):
    editor = get_editor(request)
    source = await editor.get_source(db, user, source_id)
    path = editor.storage.absolute(source.path)
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Файл удалён")
    return FileResponse(path, media_type="video/mp4" if path.suffix == ".mp4" else None)


@router.post("/api/editor/jobs", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
async def create_job(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    source_id: Annotated[str, Form()],
    params: Annotated[str, Form()] = "{}",
    logo: UploadFile | None = File(None),
    music: UploadFile | None = File(None),
    subtitles: UploadFile | None = File(None),
):
    try:
        edit_params = EditParams.model_validate(json.loads(params or "{}"))
    except (json.JSONDecodeError, ValidationError) as exc:
        detail = humanize_validation_error(exc.errors()[0]) if isinstance(exc, ValidationError) else "Некорректные параметры"
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail) from exc
    editor = get_editor(request)
    source = await editor.get_source(db, user, source_id)
    job = await editor.create_job(db, user, source, edit_params, logo=logo, music=music, subtitles=subtitles)
    return job_out(job, editor.queue.progress.get(job.id))


@router.get("/api/editor/jobs", response_model=list[JobOut])
async def list_jobs(request: Request, db: DbSession, user: CurrentUser):
    editor = get_editor(request)
    return [job_out(j, editor.queue.progress.get(j.id)) for j in await editor.list_jobs(db, user)]


@router.get("/api/editor/jobs/{job_id}", response_model=JobOut)
async def get_job(job_id: str, request: Request, db: DbSession, user: CurrentUser):
    editor = get_editor(request)
    job = await editor.get_job(db, user, job_id)
    return job_out(job, editor.queue.progress.get(job.id))


@router.get("/api/editor/jobs/{job_id}/result")
async def job_result(job_id: str, request: Request, db: DbSession, user: CurrentUser, download: bool = False):
    editor = get_editor(request)
    job = await editor.get_job(db, user, job_id)
    if job.status != "done" or not job.output_path:
        raise HTTPException(status.HTTP_409_CONFLICT, "Видео ещё не готово")
    path = editor.storage.absolute(job.output_path)
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Срок хранения результата истёк")
    return FileResponse(
        path,
        media_type="video/mp4",
        filename=f"clip_{job.id[:8]}.mp4",
        content_disposition_type="attachment" if download else "inline",
    )
