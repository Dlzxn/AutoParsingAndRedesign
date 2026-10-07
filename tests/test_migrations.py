"""Обновление базы старой версии проекта и перенос legacy-данных."""
import json

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import create_async_engine

from app import cli
from app.core.security import is_password_hash, verify_password
from app.db.base import Base, dispose_engine, init_engine, session_factory
from app.db.migrate import upgrade_to_head
from app.db.models import ClipHistory, Platform, Tariff, User
from tests.conftest import TEST_DATABASE_URL

# Схема и данные в том виде, в каком их создавала старая версия (create_all без Alembic)
LEGACY_SCHEMA = [
    """CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, email VARCHAR(100) NOT NULL,
       password VARCHAR(100) NOT NULL, is_admin BOOLEAN NOT NULL, subscribe_status VARCHAR(20) NOT NULL,
       date_start DATETIME, date_end DATETIME, token_today INTEGER NOT NULL)""",
    """CREATE TABLE promo (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL, status BOOLEAN NOT NULL, type VARCHAR NOT NULL,
       date_ended DATETIME, count_activated INTEGER NOT NULL, bonus_count INTEGER NOT NULL, description VARCHAR)""",
    "INSERT INTO users VALUES (2, 'old@example.com', 'plain-pass', 1, 'Free', NULL, NULL, 0)",
    "INSERT INTO users VALUES (3, 'old@example.com', 'plain-pass', 0, 'Pro', NULL, '2026-12-31 00:00:00', 4)",
    "INSERT INTO promo VALUES (1, 'OLD', 1, 'sale', NULL, 5, 2, 'legacy promo')",
]


@pytest.fixture
def legacy_db_url(tmp_path):
    return TEST_DATABASE_URL or f"sqlite+aiosqlite:///{(tmp_path / 'legacy.db').as_posix()}"


async def _create_legacy(url: str) -> None:
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        for statement in LEGACY_SCHEMA:
            if url.startswith("postgresql"):
                statement = statement.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
                statement = statement.replace("DATETIME", "TIMESTAMP")
                statement = statement.replace("VALUES (2, 'old@example.com', 'plain-pass', 1,", "VALUES (2, 'old@example.com', 'plain-pass', true,")
                statement = statement.replace("VALUES (3, 'old@example.com', 'plain-pass', 0,", "VALUES (3, 'old@example.com', 'plain-pass', false,")
                statement = statement.replace("VALUES (1, 'OLD', 1,", "VALUES (1, 'OLD', true,")
            await conn.execute(text(statement))
        if url.startswith("postgresql"):
            await conn.execute(text("SELECT setval('users_id_seq', 3)"))
    await engine.dispose()


async def test_migration_keeps_legacy_data(legacy_db_url):
    await _create_legacy(legacy_db_url)
    engine = init_engine(legacy_db_url)
    try:
        await upgrade_to_head(engine)
        await upgrade_to_head(engine)  # повторный запуск безопасен
        async with engine.connect() as conn:
            tables = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
            columns = await conn.run_sync(lambda c: {col["name"] for col in inspect(c).get_columns("users")})
        assert {"users", "promo", "user_sessions", "clip_history", "platforms", "tariffs", "media_sources",
                "render_jobs", "alembic_version"} <= tables
        assert "created_at" in columns
        async with session_factory()() as db:
            users = (await db.scalars(select(User).order_by(User.id))).all()
            assert [(u.id, u.subscribe_status, u.token_today) for u in users] == [(2, "Free", 0), (3, "Pro", 4)]
            assert (await db.execute(text("SELECT name FROM promo"))).scalar() == "OLD"
    finally:
        await dispose_engine()


async def test_fresh_database_matches_models(tmp_path):
    url = TEST_DATABASE_URL or f"sqlite+aiosqlite:///{(tmp_path / 'fresh.db').as_posix()}"
    engine = init_engine(url)
    try:
        await upgrade_to_head(engine)
        async with engine.connect() as conn:
            migrated = await conn.run_sync(
                lambda c: {t: {col["name"] for col in inspect(c).get_columns(t)} for t in inspect(c).get_table_names()}
            )
        for table in Base.metadata.sorted_tables:
            assert table.name in migrated, table.name
            assert {c.name for c in table.columns} == migrated[table.name], table.name
    finally:
        await dispose_engine()


async def test_import_legacy_cli(legacy_db_url, tmp_path, monkeypatch, settings):
    await _create_legacy(legacy_db_url)
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / "clips_history.json").write_text(json.dumps({
        "3": ["https://www.youtube.com/watch?v=a", "https://vk.com/video-1_2", "https://www.youtube.com/watch?v=a"],
        "99": ["https://coub.com/x"],  # пользователя нет
        " ": ["https://coub.com/y"],
    }), encoding="utf-8")
    (legacy / "tarifs.json").write_text(json.dumps({
        "standard": {"price": 2500, "token_in_day": 7, "sale": "False", "new_price": "0"},
    }), encoding="utf-8")
    (legacy / "platforms.json").write_text(json.dumps({"vk": {"status": "off"}, "tg": {"status": "on"}}),
                                           encoding="utf-8")
    settings.database_url = legacy_db_url

    await cli.cmd_import_legacy(type("Args", (), {"directory": str(legacy)})())
    await cli.cmd_import_legacy(type("Args", (), {"directory": str(legacy)})())  # идемпотентно
    try:
        async with session_factory()() as db:
            users = (await db.scalars(select(User))).all()
            assert all(is_password_hash(u.password) and verify_password("plain-pass", u.password) for u in users)
            history = (await db.execute(select(ClipHistory.user_id, ClipHistory.url, ClipHistory.platform))).all()
            assert sorted(history) == [(3, "https://vk.com/video-1_2", "vk"), (3, "https://www.youtube.com/watch?v=a", "yt")]
            standard = await db.get(Tariff, "standard")
            assert (standard.price, standard.token_in_day, standard.sale) == (2500, 7, False)
            assert (await db.get(Platform, "vk")).enabled is False
            assert (await db.get(Platform, "yt")).enabled is True
    finally:
        await dispose_engine()


async def test_create_admin_cli(settings, capsys):
    await cli.cmd_create_admin(type("Args", (), {"email": "Boss@Example.com", "password": "bosspass1"})())
    await cli.cmd_create_admin(type("Args", (), {"email": "boss@example.com", "password": "newpass12"})())
    try:
        async with session_factory()() as db:
            boss = (await db.scalars(select(User).where(User.email == "boss@example.com"))).all()
            assert len(boss) == 1 and boss[0].is_admin
            assert verify_password("newpass12", boss[0].password)
    finally:
        await dispose_engine()
    output = capsys.readouterr().out
    assert "Создан администратор" in output and "теперь администратор" in output
