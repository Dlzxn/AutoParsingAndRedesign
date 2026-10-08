"""Начальная схема.

Совместима с базой старой версии проекта: таблицы users и promo уже могут существовать
(создавались через create_all без Alembic). В этом случае они не пересоздаются,
а только дополняются недостающими колонками.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-07
"""
import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    tables = _tables()

    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("password", sa.String(255), nullable=False),
            sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("subscribe_status", sa.String(20), nullable=False, server_default="Free"),
            sa.Column("date_start", sa.DateTime(), nullable=True),
            sa.Column("date_end", sa.DateTime(), nullable=True),
            sa.Column("token_today", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        )
    else:
        with op.batch_alter_table("users") as batch:
            batch.alter_column("email", type_=sa.String(255), existing_nullable=False)
            batch.alter_column("password", type_=sa.String(255), existing_nullable=False)
            if "created_at" not in _columns("users"):
                batch.add_column(
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now())
                )
    if "ix_users_email" not in {i["name"] for i in sa.inspect(op.get_bind()).get_indexes("users")}:
        op.create_index("ix_users_email", "users", ["email"])

    if "promo" not in tables:
        op.create_table(
            "promo",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("status", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("type", sa.String(), nullable=False),
            sa.Column("date_ended", sa.DateTime(), nullable=True),
            sa.Column("count_activated", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("bonus_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("description", sa.String(), nullable=True),
        )

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_sessions_token_hash", "user_sessions", ["token_hash"], unique=True)
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"])

    op.create_table(
        "clip_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("platform", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "url", name="uq_clip_history_user_url"),
    )
    op.create_index("ix_clip_history_user_id", "clip_history", ["user_id"])

    op.create_table(
        "platforms",
        sa.Column("key", sa.String(20), primary_key=True),
        sa.Column("title", sa.String(50), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "tariffs",
        sa.Column("key", sa.String(20), primary_key=True),
        sa.Column("price", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("token_in_day", sa.Integer(), nullable=True),
        sa.Column("sale", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("new_price", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "media_sources",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("origin_url", sa.String(2048), nullable=True),
        sa.Column("original_name", sa.String(255), nullable=True),
        sa.Column("path", sa.String(1024), nullable=False),
        sa.Column("duration", sa.Float(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("has_audio", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_media_sources_user_id", "media_sources", ["user_id"])
    op.create_index("ix_media_sources_created_at", "media_sources", ["created_at"])

    op.create_table(
        "render_jobs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "source_id", sa.String(32), sa.ForeignKey("media_sources.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("output_path", sa.String(1024), nullable=True),
        sa.Column("output_size", sa.Integer(), nullable=True),
        sa.Column("output_duration", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_render_jobs_user_id", "render_jobs", ["user_id"])
    op.create_index("ix_render_jobs_status", "render_jobs", ["status"])
    op.create_index("ix_render_jobs_created_at", "render_jobs", ["created_at"])


def downgrade() -> None:
    for table in ("render_jobs", "media_sources", "tariffs", "platforms", "clip_history", "user_sessions"):
        op.drop_table(table)
    # users и promo не удаляются: в них данные пользователей старой версии.
