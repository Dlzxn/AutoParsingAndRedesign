from fastapi import APIRouter

from WebApp.BackEnd.auth_api.models.login_model import Login

auth = APIRouter(prefix="/api", tags=["auth"])

@auth.post("/login")
async def login(data: Login):
    print(data)
    return {"status": "success"}

@auth.post("/registration")
async def registration(data: Login):
    print(data)
    return {"status": "success"}

