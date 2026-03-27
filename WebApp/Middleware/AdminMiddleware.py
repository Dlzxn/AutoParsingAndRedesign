from fastapi import FastAPI, Depends, HTTPException, Request

from WebApp.BackEnd.db.CRUD import db
from WebApp.BackEnd.auth_api.auth_api_router import list_with_tokens

async def admin_middleware(request: Request):
    """Проверка является ли пользователь админом"""
    try:
        token = request.cookies.get("token")
        for user in list_with_tokens:
            if str(user["token"]) == str(token):
                user_data = user["user"]

        data: bool = await db.is_admin(user_data.id)

        if data:
            print("[INFO] admin")
            return True
        else:
            print("[ERROR] HTTPException 403")
            raise HTTPException(403, "Frobidden")
    except Exception as e:
        print(f"[ERROR] {e}")
        raise HTTPException(403, "Frobidden")