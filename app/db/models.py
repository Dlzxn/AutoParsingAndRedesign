from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # Хеш пароля. У старых аккаунтов здесь может лежать пароль открытым текстом —
    # он заменяется на хеш при первом успешном входе (см. app.auth.service).
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    subscribe_status: Mapped[str] = mapped_column(String(20), nullable=False, default="Free")
    date_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    date_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    token_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=utcnow, server_default=func.now()
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class ClipHistory(Base):
    """Клипы, которые пользователь уже смотрел/скачивал — исключаются из повторной выдачи."""

    __tablename__ = "clip_history"
    __table_args__ = (UniqueConstraint("user_id", "url", name="uq_clip_history_user_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    platform: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class Platform(Base):
    __tablename__ = "platforms"

    key: Mapped[str] = mapped_column(String(20), primary_key=True)
    title: Mapped[str] = mapped_column(String(50), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Tariff(Base):
    __tablename__ = "tariffs"

    key: Mapped[str] = mapped_column(String(20), primary_key=True)
    price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    token_in_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    new_price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Promo(Base):
    __tablename__ = "promo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    date_ended: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    count_activated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bonus_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(String, nullable=True)


class MediaSource(Base):
    """Исходное видео для редактора (загруженное пользователем или скачанное по ссылке)."""

    __tablename__ = "media_sources"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    origin_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    original_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    duration: Mapped[float] = mapped_column(Float, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    has_audio: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)


class RenderJob(Base):
    __tablename__ = "render_jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("media_sources.id", ondelete="CASCADE"), nullable=False)
    params: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued", index=True)
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    output_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
