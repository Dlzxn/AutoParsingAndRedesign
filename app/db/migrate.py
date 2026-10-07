"""Применение миграций Alembic из кода (при старте приложения и в тестах)."""
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import BASE_DIR


def _alembic_config() -> Config:
    cfg = Config(str(BASE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BASE_DIR / "migrations"))
    cfg.attributes["skip_logging_config"] = True
    return cfg


async def upgrade_to_head(engine: AsyncEngine) -> None:
    cfg = _alembic_config()

    def _run(sync_conn) -> None:  # noqa: ANN001
        cfg.attributes["connection"] = sync_conn
        command.upgrade(cfg, "head")

    async with engine.begin() as conn:
        await conn.run_sync(_run)
