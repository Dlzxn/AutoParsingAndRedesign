"""Справочники в БД: статусы платформ и тарифы."""
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Platform, Tariff


async def list_platforms(db: AsyncSession) -> list[Platform]:
    return list((await db.scalars(select(Platform).order_by(Platform.key))).all())


async def is_platform_enabled(db: AsyncSession, key: str) -> bool:
    enabled = await db.scalar(select(Platform.enabled).where(Platform.key == key))
    return bool(enabled)


async def ensure_platform_enabled(db: AsyncSession, key: str) -> None:
    if not await is_platform_enabled(db, key):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Платформа временно отключена, ведутся технические работы")


async def set_platform_enabled(db: AsyncSession, key: str, enabled: bool) -> Platform:
    platform = await db.get(Platform, key)
    if platform is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Платформа не найдена")
    platform.enabled = enabled
    await db.commit()
    return platform


def tariff_to_dict(t: Tariff) -> dict:
    return {"price": t.price, "token_in_day": t.token_in_day, "sale": t.sale, "new_price": t.new_price}


async def get_tariffs(db: AsyncSession) -> dict[str, dict]:
    rows = (await db.scalars(select(Tariff).order_by(Tariff.sort_order, Tariff.key))).all()
    return {t.key: tariff_to_dict(t) for t in rows}


async def update_tariffs(db: AsyncSession, data: dict[str, dict]) -> dict[str, dict]:
    rows = {t.key: t for t in (await db.scalars(select(Tariff))).all()}
    unknown = set(data) - set(rows)
    if unknown:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Неизвестные тарифы: {', '.join(sorted(unknown))}")
    for key, values in data.items():
        tariff = rows[key]
        for field in ("price", "token_in_day", "sale", "new_price"):
            if field in values:
                setattr(tariff, field, values[field])
    await db.commit()
    return await get_tariffs(db)
