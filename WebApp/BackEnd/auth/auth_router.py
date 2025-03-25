from fastapi import APIRouter
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


auth_router = APIRouter()

auth_router.mount("/WebApp/FrontEnd", StaticFiles(directory="WebApp/FrontEnd"), name="static")


@auth_router.get("/login")
async def login():
    return FileResponse("WebApp/FrontEnd/templates/login.html")


@auth_router.get("/registration")
async def registration():
    return FileResponse("WebApp/FrontEnd/templates/registration.html")