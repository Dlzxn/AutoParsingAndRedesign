import csv
import io
import math
from datetime import datetime, time, timedelta, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import asc, delete, desc, func, or_, select

from app.admin.schemas import (
    PlatformStatusIn,
    PromoIn,
    PromoOut,
    TariffIn,
    UserCreate,
    UserOut,
    UserPage,
    UserUpdate,
)
from app.auth import service as auth_service
from app.auth.deps import AdminUser, DbSession, LoginRequired, OptionalUser
from app.catalog import service as catalog
from app.db.models import ClipHistory, MediaSource, Promo, RenderJob, User
from app.web.templating import render


async def require_page_admin(request: Request, user: OptionalUser) -> User:
    if user is None:
        raise LoginRequired(request.url.path)
    if not user.is_admin:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return user


pages = APIRouter(prefix="/admin", include_in_schema=False, dependencies=[Depends(require_page_admin)])
api = APIRouter(prefix="/api/admin", tags=["admin"])


# ---------- Страницы ----------

@pages.get("")
@pages.get("/")
async def admin_index(request: Request):
    return render(request, "admin_panel.html")


@pages.get("/users")
async def admin_users(request: Request):
    return render(request, "users_list_adm.html")


@pages.get("/pricing")
async def admin_pricing(request: Request):
    return render(request, "tarif_adm.html")


@pages.get("/promocode")
async def admin_promo(request: Request):
    return render(request, "adm_promo.html")


@pages.get("/platforms")
async def admin_platforms(request: Request):
    return render(request, "platforms.html")


@pages.get("/stats")
async def admin_stats(request: Request):
    return render(request, "admin_stats.html")


@pages.get("/export")
async def admin_export(db: DbSession):
    """Выгрузка пользователей в CSV (без паролей)."""
    users = (await db.scalars(select(User).order_by(User.id))).all()
    buffer = io.StringIO()
    buffer.write("﻿")  # BOM — чтобы Excel корректно открыл кириллицу
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(["id", "email", "is_admin", "subscribe_status", "date_start", "date_end", "token_today", "created_at"])
    for u in users:
        writer.writerow([u.id, u.email, u.is_admin, u.subscribe_status, u.date_start or "", u.date_end or "",
                         u.token_today, u.created_at or ""])
    filename = f"users_{datetime.now():%Y%m%d_%H%M}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------- Пользователи ----------

SORT_FIELDS = {"id", "email", "subscribe_status", "date_end", "token_today", "is_admin", "created_at"}


@api.get("/users", response_model=UserPage)
async def list_users(
    db: DbSession,
    admin: AdminUser,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 10,
    sort: str = "id",
    order: Literal["asc", "desc"] = "asc",
    search: str | None = None,
):
    query = select(User)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.where(or_(User.email.ilike(pattern), User.subscribe_status.ilike(pattern)))
    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    column = getattr(User, sort if sort in SORT_FIELDS else "id")
    query = query.order_by((asc if order == "asc" else desc)(column), User.id)
    users = (await db.scalars(query.offset((page - 1) * per_page).limit(per_page))).all()
    return UserPage(users=users, total=total, page=page, per_page=per_page,
                    total_pages=max(1, math.ceil(total / per_page)))


def _date_to_datetime(value) -> datetime | None:
    return datetime.combine(value, time()) if value else None


@api.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(data: UserCreate, db: DbSession, admin: AdminUser):
    try:
        user = await auth_service.create_user(
            db, data.email, data.password, is_admin=data.is_admin, subscribe_status=data.subscribe_status,
            token_today=data.token_today, date_end=_date_to_datetime(data.date_end),
        )
    except auth_service.AuthError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return user


@api.put("/users/{user_id}", response_model=UserOut)
async def update_user(user_id: int, data: UserUpdate, db: DbSession, admin: AdminUser):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")
    values = data.model_dump(exclude_unset=True)
    if user.id == admin.id and values.get("is_admin") is False:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Нельзя снять права администратора с самого себя")
    if "email" in values and values["email"]:
        email = auth_service.normalize_identity(values["email"])
        try:
            auth_service.validate_identity(email)
        except auth_service.AuthError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
        taken = await db.scalar(select(User.id).where(User.email == email, User.id != user.id).limit(1))
        if taken:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Этот логин уже занят")
        user.email = email
    for field in ("subscribe_status", "token_today", "is_admin"):
        if values.get(field) is not None:
            setattr(user, field, values[field])
    if "date_end" in values:
        user.date_end = _date_to_datetime(values["date_end"])
    if values.get("password"):
        try:
            await auth_service.set_password(db, user, values["password"])
        except auth_service.AuthError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    await db.commit()
    await db.refresh(user)
    return user


@api.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, request: Request, db: DbSession, admin: AdminUser):
    if user_id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Нельзя удалить собственный аккаунт")
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")
    source_paths = (await db.scalars(select(MediaSource.id).where(MediaSource.user_id == user_id))).all()
    job_ids = (await db.scalars(select(RenderJob.id).where(RenderJob.user_id == user_id))).all()
    await db.delete(user)
    await db.commit()
    storage = request.app.state.storage
    for source_id in source_paths:
        storage.remove_dir(storage.source_dir(source_id))
    for job_id in job_ids:
        storage.remove_dir(storage.job_dir(job_id))


# ---------- Тарифы ----------

@api.get("/pricing")
async def get_pricing(db: DbSession, admin: AdminUser):
    return await catalog.get_tariffs(db)


@api.put("/pricing")
async def update_pricing(data: dict[str, TariffIn], db: DbSession, admin: AdminUser):
    return await catalog.update_tariffs(db, {k: v.model_dump() for k, v in data.items()})


# ---------- Промокоды ----------

@api.get("/promocodes", response_model=list[PromoOut])
async def list_promo(db: DbSession, admin: AdminUser):
    return (await db.scalars(select(Promo).order_by(Promo.id.desc()))).all()


@api.get("/promocodes/{promo_id}", response_model=PromoOut)
async def get_promo(promo_id: int, db: DbSession, admin: AdminUser):
    promo = await db.get(Promo, promo_id)
    if promo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Промокод не найден")
    return promo


@api.post("/promocodes", response_model=PromoOut, status_code=status.HTTP_201_CREATED)
async def create_promo(data: PromoIn, db: DbSession, admin: AdminUser):
    promo = Promo(**data.model_dump())
    db.add(promo)
    await db.commit()
    await db.refresh(promo)
    return promo


@api.put("/promocodes/{promo_id}", response_model=PromoOut)
async def update_promo(promo_id: int, data: PromoIn, db: DbSession, admin: AdminUser):
    promo = await db.get(Promo, promo_id)
    if promo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Промокод не найден")
    for field, value in data.model_dump().items():
        setattr(promo, field, value)
    await db.commit()
    await db.refresh(promo)
    return promo


@api.delete("/promocodes/{promo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_promo(promo_id: int, db: DbSession, admin: AdminUser):
    result = await db.execute(delete(Promo).where(Promo.id == promo_id))
    await db.commit()
    if not result.rowcount:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Промокод не найден")


# ---------- Платформы ----------

@api.get("/platforms")
async def list_platforms(db: DbSession, admin: AdminUser):
    return [{"key": p.key, "title": p.title, "enabled": p.enabled} for p in await catalog.list_platforms(db)]


@api.put("/platforms/{key}")
async def set_platform(key: str, data: PlatformStatusIn, db: DbSession, admin: AdminUser):
    platform = await catalog.set_platform_enabled(db, key, data.enabled)
    return {"key": platform.key, "title": platform.title, "enabled": platform.enabled}


# ---------- Статистика ----------

@api.get("/stats")
async def stats(request: Request, db: DbSession, admin: AdminUser):
    day_ago = datetime.now(timezone.utc) - timedelta(days=1)
    by_plan = dict((await db.execute(select(User.subscribe_status, func.count()).group_by(User.subscribe_status))).all())
    by_status = dict((await db.execute(select(RenderJob.status, func.count()).group_by(RenderJob.status))).all())
    renders_day = await db.scalar(select(func.count()).select_from(RenderJob).where(RenderJob.created_at >= day_ago))
    by_platform = dict(
        (await db.execute(select(ClipHistory.platform, func.count()).group_by(ClipHistory.platform))).all()
    )
    return {
        "users_total": await db.scalar(select(func.count()).select_from(User)),
        "admins": await db.scalar(select(func.count()).select_from(User).where(User.is_admin.is_(True))),
        "users_by_plan": by_plan,
        "renders_total": sum(by_status.values()),
        "renders_last_24h": renders_day,
        "renders_by_status": by_status,
        "render_queue": request.app.state.render_queue.queue.qsize(),
        "clips_by_platform": {k or "unknown": v for k, v in by_platform.items()},
    }
