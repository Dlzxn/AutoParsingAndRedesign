from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(url: str, echo: bool = False) -> AsyncEngine:
    global _engine, _session_factory
    kwargs: dict = {"echo": echo}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"timeout": 30}
    else:
        kwargs.update(pool_size=10, max_overflow=20, pool_pre_ping=True, pool_recycle=1800)
    _engine = create_async_engine(url, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(_engine.sync_engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Database engine is not initialized")
    return _engine


def session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Database engine is not initialized")
    return _session_factory


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI-зависимость: одна сессия на запрос."""
    async with session_factory()() as session:
        yield session
