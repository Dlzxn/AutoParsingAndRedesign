from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import json

from WebApp.Middleware.AdminMiddleware import admin_middleware
from WebApp.BackEnd.db.CRUD import db
from WebApp.BackEnd.admin_panel.models.pydanticModel import UserUpdate, Promo
from WebApp.BackEnd.promo.db.promo_CRUD import db_promo

adm_api = APIRouter(prefix = "/api", tags = ["admin"],
                    dependencies=[Depends(admin_middleware)]
                    )

PRICING_FILE = "WebApp/BackEnd/subscription/tarifs_db/tarifs.json"
@adm_api.get("/users")
async def get_users(
        page: int = Query(1, ge=1),
        per_page: int = Query(10, ge=1, le=100),
        sort: str = Query("id"),
        order: str = Query("asc"),
        search: Optional[str] = None,
):
    print("[INFO]- get_users", page, per_page, sort, order, search)
    return await db.get_users(
        page=page,
        per_page=per_page,
        sort=sort,
        order=order,
        search=search
    )


@adm_api.post("/users")
async def create_new_user(user_data = UserUpdate):
    pass



# Обновляем роутер
@adm_api.put("/users/{user_id}")
async def update_user(
    user_id: int,
    user_data: UserUpdate,
):
    try:
        return await db.update_user(
            user_id,
            user_data.model_dump(exclude_unset=True)
        )
    except ValueError as e:
        print(f"[ERROR] {e}")
        raise HTTPException(status_code=400, detail=str(e))


@adm_api.get("/pricing")
async def get_pricing():
    try:
        with open(PRICING_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] {e}")
        raise HTTPException(500, detail="Ошибка чтения файла тарифов")


@adm_api.put("/pricing")
async def update_pricing(data: dict):
    try:
        # Валидация данных
        required_keys = {"free", "standard", "pro", "premium"}
        if data.keys() != required_keys:
            raise HTTPException(400, "Некорректная структура тарифов")

        for tariff in data.values():
            if not all(k in tariff for k in ["price", "token_in_day", "sale", "new_price"]):
                raise HTTPException(400, "Некорректные поля тарифа")

        # Сохранение в файл
        with open(PRICING_FILE, "w") as f:
            json.dump(data, f, indent=2)

        return {"status": "success"}

    except HTTPException as he:
        print(f"[ERROR] {he}")
        raise he
    except Exception as e:
        print(f"[ERROR] {e}")
        raise HTTPException(500, detail="Ошибка сохранения тарифов")

@adm_api.get("/promocodes")
async def all_promo():
    promo = await db_promo.get_all_promo()
    return promo

@adm_api.post("/promocodes")
async def update_promocodes(data: Promo):
    promo = await db_promo.create_promo(data)
    if promo:
        return True
    return False

@adm_api.get("/promocodes/{promo}")
async def get_promo_code(promo: int):
    promo = await db_promo.get_promo(promo)
    return promo
@adm_api.put("/promocodes/{promo}")
async def update_promo_code(promo: int, data: Promo):
    promo = await db_promo.update_promo(promo, data)

@adm_api.get("/platforms")
async def get_platforms():
    with open("WebApp/BackEnd/platform_status/platforms.json", "r") as f:
        return json.load(f)

@adm_api.put("/platforms/{platform}")
async def put_platform(platform: str, data: dict):
    try:
        with open("WebApp/BackEnd/platform_status/platforms.json", "r") as f:
            platfroms_status = json.load(f)
        platfroms_status[platform]["status"] = data["status"]
        with open("WebApp/BackEnd/platform_status/platforms.json", "w") as f:
            json.dump(platfroms_status, f, indent=2)
        return True
    except Exception as e:
        print(f"[ERROR] {e}")
        return False