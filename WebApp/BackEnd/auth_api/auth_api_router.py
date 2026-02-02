from fastapi import APIRouter, Response, HTTPException
from random import randint
from WebApp.BackEnd.auth_api.models.login_model import Login
from WebApp.BackEnd.db.CRUD import db
auth = APIRouter(prefix="/api", tags=["auth"])

list_with_tokens:list = []

@auth.post("/login")
async def login(data: Login, re: Response):
    print(data)
    user = await db.verify_user(data.identity, data.password)
    print("User in login", user)
    if user is not None:
        print("User in login(created)", user)
        token = randint(1, 10000)
        list_with_tokens.append({"token": token, "user": user})
        re.set_cookie(key = "token", value = token, httponly = True)
        return {"status": "success"}
    else:
        print("User in login(not created)", user)
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

@auth.post("/registration")
async def registration(data: Login, re: Response):
    print(data)
    user = await db.create_user(data.identity, data.password)
    if user:
        token = randint(1, 10000)
        list_with_tokens.append({"token": token, "user": user})

        re.set_cookie(key="token", value = token, httponly=True)
        return {"status": "success"}
    else:
        return {"status": "failed"}

