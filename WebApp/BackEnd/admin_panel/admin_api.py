from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import json

from WebApp.Middleware.AdminMiddleware import admin_middleware
from WebApp.BackEnd.db.CRUD import db
from WebApp.BackEnd.admin_panel.models.pydanticModel import UserUpdate

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