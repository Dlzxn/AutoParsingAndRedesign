from fastapi import APIRouter, Response
from random import randint
from WebApp.BackEnd.auth_api.models.login_model import Login
from WebApp.BackEnd.db.CRUD import db
auth = APIRouter(prefix="/api", tags=["auth"])

list_with_tokens:list = []

@auth.post("/login")
async def login(data: Login, re: Response):
    print(data)
    user = db.verify_user(data.identity, data.password)
    if user:
        token = randint(1, 10000)
        list_with_tokens.append({"token": token, "user": user})

        re.set_cookie(key = "token", value = token, httponly = True)
        return {"status": "success"}
    else:
        return {"status": "failed"}

@auth.post("/registration")
async def registration(data: Login, re: Response):
    print(data)
    user = db.create_user(data.identity, data.password)
    if user:
        token = randint(1, 10000)
        list_with_tokens.append({"token": token, "user": user})

        re.set_cookie(key="token", value = token, httponly=True)
        return {"status": "success"}
    else:
        return {"status": "failed"}

