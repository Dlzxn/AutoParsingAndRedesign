"""Начальные данные справочников (платформы, тарифы). Идемпотентно: добавляет только отсутствующее."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Platform, Tariff

DEFAULT_PLATFORMS: list[tuple[str, str]] = [
    ("vk", "ВКонтакте"),
    ("yt", "YouTube"),
    ("coub", "Coub"),
    ("reddit", "Reddit"),
    ("imgur", "Imgur"),
    ("tumblr", "Tumblr"),
]

DEFAULT_TARIFFS: list[dict] = [
    {"key": "free", "price": 0, "token_in_day": 0, "sale": False, "new_price": 0, "sort_order": 0},
    {"key": "standard", "price": 2000, "token_in_day": 5, "sale": True, "new_price": 50, "sort_order": 1},
    {"key": "pro", "price": 40000, "token_in_day": None, "sale": True, "new_price": 150, "sort_order": 2},
    {"key": "premium", "price": 15000, "token_in_day": 300, "sale": False, "new_price": 0, "sort_order": 3},
]


async def seed_defaults(session: AsyncSession) -> None:
    existing_platforms = set((await session.scalars(select(Platform.key))).all())
    for key, title in DEFAULT_PLATFORMS:
        if key not in existing_platforms:
            session.add(Platform(key=key, title=title, enabled=True))

    existing_tariffs = set((await session.scalars(select(Tariff.key))).all())
    for data in DEFAULT_TARIFFS:
        if data["key"] not in existing_tariffs:
            session.add(Tariff(**data))
    await session.commit()
