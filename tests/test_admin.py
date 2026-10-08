import pytest
from sqlalchemy import select

from app.core.security import is_password_hash
from app.db.models import User

ADMIN_PAGES = ["/admin", "/admin/users", "/admin/pricing", "/admin/promocode", "/admin/platforms", "/admin/stats"]


@pytest.mark.parametrize("path", ADMIN_PAGES)
async def test_admin_pages(admin_client, user_client, client, path):
    assert (await admin_client.get(path)).status_code == 200
    assert (await user_client.get(path)).status_code == 404  # обычный пользователь не узнает о существовании
    assert (await client.get(path)).status_code == 303


@pytest.mark.parametrize("path", ["/api/admin/users", "/api/admin/pricing", "/api/admin/promocodes",
                                  "/api/admin/platforms", "/api/admin/stats"])
async def test_admin_api_forbidden(user_client, client, path):
    assert (await user_client.get(path)).status_code == 403
    assert (await client.get(path)).status_code == 401


async def test_users_list_has_no_passwords(admin_client, user_client):
    data = (await admin_client.get("/api/admin/users")).json()
    assert data["total"] == 2
    assert all("password" not in u for u in data["users"])


async def test_users_search_sort_pagination(admin_client, app):
    from app.auth.service import create_user
    from app.db.base import session_factory

    async with session_factory()() as db:
        for i in range(12):
            await create_user(db, f"user{i:02d}@example.com", "secret123")
    page1 = (await admin_client.get("/api/admin/users", params={"per_page": 5})).json()
    assert page1["total"] == 13 and page1["total_pages"] == 3 and len(page1["users"]) == 5
    found = (await admin_client.get("/api/admin/users", params={"search": "user1"})).json()
    assert {u["email"] for u in found["users"]} == {"user10@example.com", "user11@example.com"}
    desc = (await admin_client.get("/api/admin/users", params={"sort": "email", "order": "desc"})).json()
    assert desc["users"][0]["email"] == "user11@example.com"
    bad_sort = await admin_client.get("/api/admin/users", params={"sort": "password"})
    assert bad_sort.status_code == 200  # неизвестное поле сортировки игнорируется


async def test_create_update_delete_user(admin_client, db):
    response = await admin_client.post("/api/admin/users", json={
        "email": "made@example.com", "password": "secret123", "subscribe_status": "Pro", "date_end": "2027-01-31",
        "token_today": 7, "is_admin": False})
    assert response.status_code == 201, response.text
    user = response.json()
    assert user["subscribe_status"] == "Pro" and user["date_end"].startswith("2027-01-31")

    response = await admin_client.put(f"/api/admin/users/{user['id']}", json={
        "email": "renamed@example.com", "subscribe_status": "Premium", "date_end": None, "token_today": 3,
        "password": "newsecret"})
    assert response.status_code == 200, response.text
    assert response.json()["email"] == "renamed@example.com"
    assert response.json()["date_end"] is None
    stored = await db.scalar(select(User).where(User.id == user["id"]))
    assert is_password_hash(stored.password)

    assert (await admin_client.post("/api/login", json={"identity": "renamed@example.com", "password": "newsecret"})).status_code == 200


async def test_user_validation(admin_client, user_client):
    users = (await admin_client.get("/api/admin/users")).json()["users"]
    regular = next(u for u in users if u["email"] == "user@example.com")
    response = await admin_client.put(f"/api/admin/users/{regular['id']}", json={"subscribe_status": "VIP"})
    assert response.status_code == 422
    response = await admin_client.put(f"/api/admin/users/{regular['id']}", json={"email": "admin@example.com"})
    assert response.status_code == 400 and "занят" in response.json()["detail"]
    response = await admin_client.post("/api/admin/users", json={"email": "user@example.com", "password": "secret123"})
    assert response.status_code == 400
    assert (await admin_client.put("/api/admin/users/99999", json={"token_today": 1})).status_code == 404


async def test_admin_cannot_lock_themselves_out(admin_client):
    me = next(u for u in (await admin_client.get("/api/admin/users")).json()["users"] if u["is_admin"])
    assert (await admin_client.put(f"/api/admin/users/{me['id']}", json={"is_admin": False})).status_code == 400
    assert (await admin_client.delete(f"/api/admin/users/{me['id']}")).status_code == 400


async def test_delete_user_removes_sessions(admin_client, user_client):
    users = (await admin_client.get("/api/admin/users")).json()["users"]
    regular = next(u for u in users if u["email"] == "user@example.com")
    assert (await admin_client.delete(f"/api/admin/users/{regular['id']}")).status_code == 204
    assert (await user_client.get("/api/user/user_data")).json() == {"authenticated": False}
    assert (await admin_client.delete(f"/api/admin/users/{regular['id']}")).status_code == 404


async def test_tariffs(admin_client, client):
    data = (await admin_client.get("/api/admin/pricing")).json()
    data["pro"].update(price=999, sale=False, token_in_day=None)
    response = await admin_client.put("/api/admin/pricing", json=data)
    assert response.status_code == 200
    public = (await client.get("/api/user/pricing")).json()
    assert public["pro"] == {"price": 999, "token_in_day": None, "sale": False, "new_price": 150}

    assert (await admin_client.put("/api/admin/pricing", json={"gold": {"price": 1}})).status_code == 400
    assert (await admin_client.put("/api/admin/pricing", json={"pro": {"price": -5}})).status_code == 422


async def test_promocodes_crud(admin_client):
    payload = {"name": "SUMMER", "type": "sale", "status": True, "date_ended": "2027-06-01T12:00",
               "count_activated": 10, "bonus_count": 5, "description": ""}
    created = (await admin_client.post("/api/admin/promocodes", json=payload)).json()
    assert created["id"] and created["description"] is None

    payload.update(name="WINTER", date_ended="")
    updated = await admin_client.put(f"/api/admin/promocodes/{created['id']}", json=payload)
    assert updated.status_code == 200 and updated.json()["name"] == "WINTER" and updated.json()["date_ended"] is None

    assert [p["name"] for p in (await admin_client.get("/api/admin/promocodes")).json()] == ["WINTER"]
    assert (await admin_client.delete(f"/api/admin/promocodes/{created['id']}")).status_code == 204
    assert (await admin_client.get(f"/api/admin/promocodes/{created['id']}")).status_code == 404
    assert (await admin_client.post("/api/admin/promocodes", json={**payload, "name": ""})).status_code == 422


async def test_platform_toggle(admin_client, user_client, db):
    platforms = (await admin_client.get("/api/admin/platforms")).json()
    assert {p["key"] for p in platforms} == {"vk", "yt", "coub", "reddit", "imgur", "tumblr"}
    response = await admin_client.put("/api/admin/platforms/imgur", json={"enabled": False})
    assert response.json() == {"key": "imgur", "title": "Imgur", "enabled": False}
    assert "Технические работы" in (await user_client.get("/imgur")).text
    assert (await admin_client.put("/api/admin/platforms/myspace", json={"enabled": False})).status_code == 404


async def test_stats(admin_client, user_client):
    await user_client.post("/api/history", json={"url": "https://coub.com/x", "platform": "coub"})
    stats = (await admin_client.get("/api/admin/stats")).json()
    assert stats["users_total"] == 2 and stats["admins"] == 1
    assert stats["users_by_plan"] == {"Free": 2}
    assert stats["clips_by_platform"] == {"coub": 1}
    assert stats["render_queue"] == 0


async def test_csv_export(admin_client, user_client):
    response = await admin_client.get("/admin/export")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    text = response.text.lstrip("﻿")
    assert text.splitlines()[0].startswith("id;email;is_admin")
    assert "user@example.com" in text
    assert "scrypt$" not in text and "secret123" not in text  # пароли не выгружаются


async def test_xss_in_email_is_escaped_in_admin_page(admin_client, db):
    db.add(User(email='<img src=x onerror=alert(1)>@x.ru', password="x"))
    await db.commit()
    html = (await admin_client.get("/admin/users")).text
    assert "onerror=alert(1)" not in html  # данные подгружаются через API и экранируются в JS
