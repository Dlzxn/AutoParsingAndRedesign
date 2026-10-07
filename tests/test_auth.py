from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.security import hash_password, hash_token, is_password_hash, verify_password
from app.db.models import User, UserSession
from tests.conftest import _new_client, register


def test_password_hashing():
    hashed = hash_password("секрет-123")
    assert is_password_hash(hashed) and len(hashed) <= 100  # влезает в колонку старой схемы
    assert verify_password("секрет-123", hashed)
    assert not verify_password("секрет-124", hashed)
    assert hash_password("x") != hash_password("x")  # соль


def test_legacy_plaintext_and_garbage():
    assert verify_password("plain", "plain")
    assert not verify_password("plain", "other")
    assert not verify_password("x", "scrypt$broken")
    assert not verify_password("x", "")


async def test_register_login_logout(client):
    await register(client, "New@Example.com ")
    me = (await client.get("/api/user/user_data")).json()
    assert me == {"authenticated": True, "name": "new@example.com", "subscriptionPlan": "Free",
                  "is_admin": False, "date_end": None}

    cookie = client.cookies.get("session")
    assert cookie and len(cookie) >= 40

    response = await client.get("/logout")
    assert response.status_code == 303
    client.cookies.clear()
    assert (await client.get("/api/user/user_data")).json() == {"authenticated": False}

    response = await client.post("/api/login", json={"identity": "NEW@example.com", "password": "secret123"})
    assert response.status_code == 200
    assert (await client.get("/api/user/user_data")).json()["authenticated"] is True


async def test_session_cookie_flags(client):
    response = await client.post("/api/registration", json={"identity": "a@b.cd", "password": "secret123"})
    header = response.headers["set-cookie"].lower()
    assert "httponly" in header and "samesite=lax" in header


async def test_logout_invalidates_server_session(client, db):
    await register(client)
    token = client.cookies.get("session")
    await client.get("/logout")
    assert await db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token))) is None


@pytest.mark.parametrize(
    ("identity", "password", "detail"),
    [
        ("not-an-email", "secret123", "email или телефон"),
        ("123", "secret123", "email или телефон"),
        ("a@b.cd", "123", "минимум 6"),
    ],
)
async def test_registration_validation(client, identity, password, detail):
    response = await client.post("/api/registration", json={"identity": identity, "password": password})
    assert response.status_code == 400
    assert detail in response.json()["detail"]


async def test_phone_registration(client):
    await register(client, "79991234567")
    assert (await client.get("/api/user/user_data")).json()["name"] == "79991234567"


async def test_duplicate_registration(client):
    await register(client)
    client.cookies.clear()
    response = await client.post("/api/registration", json={"identity": "USER@example.com", "password": "secret123"})
    assert response.status_code == 400
    assert "уже существует" in response.json()["detail"]


async def test_wrong_password(client):
    await register(client)
    client.cookies.clear()
    response = await client.post("/api/login", json={"identity": "user@example.com", "password": "wrong-pass"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Неверный логин или пароль"


async def test_legacy_plaintext_user_upgraded_on_login(client, db):
    db.add(User(email="old@example.com", password="oldpassword"))
    await db.commit()
    response = await client.post("/api/login", json={"identity": "old@example.com", "password": "oldpassword"})
    assert response.status_code == 200
    await db.close()
    stored = await db.scalar(select(User.password).where(User.email == "old@example.com"))
    assert is_password_hash(stored)


async def test_legacy_duplicate_emails(client, db):
    """В старой БД email не был уникальным — вход должен найти нужную запись."""
    db.add_all([User(email="dup@example.com", password="first-pass"), User(email="dup@example.com", password="second-pass")])
    await db.commit()
    assert (await client.post("/api/login", json={"identity": "dup@example.com", "password": "second-pass"})).status_code == 200


async def test_expired_session(client, db):
    await register(client)
    session = await db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(client.cookies["session"])))
    session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db.commit()
    assert (await client.get("/api/user/user_data")).json() == {"authenticated": False}


async def test_forged_and_oversized_tokens(client):
    client.cookies.set("session", "forged-token")
    assert (await client.get("/api/user/user_data")).json() == {"authenticated": False}
    client.cookies.set("session", "x" * 5000)
    assert (await client.get("/api/user/user_data")).json() == {"authenticated": False}


async def test_login_rate_limit(client):
    codes = [
        (await client.post("/api/login", json={"identity": "x@y.zz", "password": "bad-pass"})).status_code
        for _ in range(11)
    ]
    assert codes[:10] == [401] * 10 and codes[10] == 429


async def test_login_page_redirect_target_is_safe(app):
    async with await _new_client(app) as c:
        page = await c.get("/login", params={"next": "//evil.com"})
        assert 'data-next="/"' in page.text
        page = await c.get("/login", params={"next": "/editor"})
        assert 'data-next="/editor"' in page.text
        await register(c)
        response = await c.get("/login", params={"next": "https://evil.com"})
        assert response.status_code == 303 and response.headers["location"] == "/"
