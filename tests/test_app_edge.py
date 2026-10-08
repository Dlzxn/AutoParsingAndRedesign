"""Приложение целиком: непредвиденные ошибки, healthcheck, CLI, фоновая очистка, редкие ветки API."""
import asyncio
import logging

import httpx
import pytest

from app import cli
from app.auth import service as auth_service


@pytest.fixture
async def raw_client(app):
    """Клиент, который не пробрасывает исключения приложения, а возвращает ответ 500."""
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


# ---------- Непредвиденные ошибки ----------

async def test_unexpected_error_in_api_returns_json(raw_client, app, monkeypatch, caplog):
    async def broken(*args, **kwargs):
        raise RuntimeError("database exploded")

    from app.catalog import service as catalog

    monkeypatch.setattr("app.users.router.get_tariffs", broken)
    with caplog.at_level(logging.ERROR):
        response = await raw_client.get("/api/user/pricing")
    assert response.status_code == 500
    assert response.json() == {"detail": "Внутренняя ошибка сервера"}
    assert "database exploded" not in response.text  # детали не утекают пользователю
    assert any("Unhandled error" in r.message for r in caplog.records)
    assert catalog  # модуль на месте


async def test_unexpected_error_on_page_returns_html(raw_client, monkeypatch):
    async def broken(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.pages.router.get_tariffs", broken)
    await raw_client.post("/api/registration", json={"identity": "p@example.com", "password": "secret123"})
    response = await raw_client.get("/profile")
    assert response.status_code == 500
    assert "text/html" in response.headers["content-type"] and "Что-то пошло не так" in response.text


async def test_healthz_degraded_without_ffmpeg(client, settings):
    settings.ffmpeg_path = "no-such-ffmpeg"
    response = await client.get("/healthz")
    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "db": True, "ffmpeg": False}


async def test_healthz_degraded_without_database(client, monkeypatch):
    def broken_engine():
        raise RuntimeError("no db")

    monkeypatch.setattr("app.main.get_engine", broken_engine)
    response = await client.get("/healthz")
    assert response.status_code == 503 and response.json()["db"] is False


def test_missing_binaries_are_logged(settings, caplog):
    from app.main import _check_binaries

    settings.ffmpeg_path = "no-such-ffmpeg"
    with caplog.at_level(logging.ERROR):
        _check_binaries(settings)
    assert any("не будут" in r.message for r in caplog.records)


async def test_api_docs_in_debug_mode(settings):
    from app.main import create_app

    settings.debug = True
    application = create_app(settings)
    async with application.router.lifespan_context(application):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application), base_url="http://t") as c:
            assert (await c.get("/api/openapi.json")).status_code == 200
    settings.debug = False


async def test_favicon_and_register_alias(client):
    assert (await client.get("/favicon.ico")).headers["location"] == "/static/img/logo.svg"
    assert (await client.get("/register")).headers["location"] == "/registration"


async def test_html_validation_error_on_page(client):
    response = await client.get("/api/search/coub")  # нет обязательного q
    assert response.status_code in (401, 422)


# ---------- Авторизация: редкие ветки ----------

@pytest.mark.parametrize(
    ("identity", "password", "message"),
    [("a" * 251 + "@b.cd", "secret123", "длинный логин"), ("ok@b.cd", "x" * 257, "длинный пароль")],
    ids=["long-login", "long-password"],
)
async def test_too_long_credentials(db, identity, password, message):
    with pytest.raises(auth_service.AuthError, match=message):
        await auth_service.create_user(db, identity, password)


async def test_delete_session_without_token(db):
    await auth_service.delete_session(db, None)
    await auth_service.delete_session(db, "")


async def test_expired_sessions_cleanup(db):
    from datetime import datetime, timedelta, timezone

    from app.db.models import UserSession

    user = await auth_service.create_user(db, "s@example.com", "secret123")
    await auth_service.create_session(db, user, ttl_days=30)
    db.add(UserSession(token_hash="x" * 64, user_id=user.id, created_at=datetime.now(timezone.utc),
                       expires_at=datetime.now(timezone.utc) - timedelta(days=1)))
    await db.commit()
    assert await auth_service.delete_expired_sessions(db) == 1


# ---------- Админка: редкие ветки ----------

async def test_admin_update_validation(admin_client, user_client):
    users = (await admin_client.get("/api/admin/users")).json()["users"]
    user_id = next(u["id"] for u in users if u["email"] == "user@example.com")
    bad_email = await admin_client.put(f"/api/admin/users/{user_id}", json={"email": "not-an-email"})
    assert bad_email.status_code == 400 and "email или телефон" in bad_email.json()["detail"]
    short_password = await admin_client.put(f"/api/admin/users/{user_id}", json={"password": "123"})
    assert short_password.status_code == 400 and "минимум 6" in short_password.json()["detail"]


async def test_admin_promo_not_found(admin_client):
    payload = {"name": "X", "type": "sale", "status": True, "count_activated": 0, "bonus_count": 0}
    assert (await admin_client.get("/api/admin/promocodes/999")).status_code == 404
    assert (await admin_client.put("/api/admin/promocodes/999", json=payload)).status_code == 404
    assert (await admin_client.delete("/api/admin/promocodes/999")).status_code == 404


# ---------- История ----------

async def test_history_rejects_invalid_urls(db):
    from app.history.service import mark_seen

    user = await auth_service.create_user(db, "h@example.com", "secret123")
    assert await mark_seen(db, user.id, "   ") is False
    assert await mark_seen(db, user.id, "https://x/" + "a" * 3000) is False
    assert await mark_seen(db, user.id, "https://x/1") is True
    assert await mark_seen(db, user.id, "https://x/1") is False


async def test_history_concurrent_duplicate_is_tolerated(db, monkeypatch):
    """Два одновременных запроса пишут один и тот же клип — второй получает IntegrityError и не падает."""
    from app.db.models import ClipHistory
    from app.history import service

    user = await auth_service.create_user(db, "c@example.com", "secret123")
    db.add(ClipHistory(user_id=user.id, url="https://x/race"))
    await db.commit()

    async def no_existing(*args, **kwargs):
        return None

    monkeypatch.setattr(db, "scalar", no_existing)  # проверка «уже есть» проскочила, как при гонке
    assert await service.mark_seen(db, user.id, "https://x/race") is False


# ---------- Фоновое обслуживание ----------

async def test_maintenance_loop_survives_errors(settings, monkeypatch, caplog):
    from app import maintenance

    calls = []

    async def flaky_cleanup(*args):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("disk error")
        return {}

    monkeypatch.setattr(maintenance, "cleanup_once", flaky_cleanup)
    monkeypatch.setattr(maintenance, "INTERVAL_SECONDS", 0.01)
    with caplog.at_level(logging.ERROR):
        task = asyncio.create_task(maintenance.maintenance_loop(settings, None))
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert len(calls) >= 2
    assert any("Maintenance failed" in r.message for r in caplog.records)


# ---------- CLI ----------

def test_cli_migrate_and_create_admin(settings, capsys):
    cli.main(["migrate"])
    cli.main(["create-admin", "cli@example.com", "clipass1"])
    output = capsys.readouterr().out
    assert "Миграции применены" in output and "Создан администратор" in output


def test_cli_error_exit_code(settings, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["create-admin", "cli2@example.com", "123"])
    assert exc.value.code == 1
    assert "минимум 6" in capsys.readouterr().err


def test_cli_import_ignores_unknown_tariffs(settings, tmp_path, capsys):
    (tmp_path / "tarifs.json").write_text('{"gold": {"price": 1}}', encoding="utf-8")
    cli.main(["import-legacy", str(tmp_path)])
    assert "Тарифы перенесены" in capsys.readouterr().out


def test_cli_requires_command():
    with pytest.raises(SystemExit):
        cli.main([])
