from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os, sys,uvicorn

from WebApp.BackEnd.SearchRouter import search_router
from WebApp.BackEnd.DownloadVideoRouter import router
from WebApp.BackEnd.auth.auth_router import auth_router
from WebApp.BackEnd.auth_api import auth_api_router
from WebApp.BackEnd.auth_api.auth_api_router import auth
from WebApp.BackEnd.profile.profile_router import profile_router as profile
from WebApp.Middleware.BaseTokenMiddleware import TokenMiddleware

app = FastAPI()
app.include_router(search_router)
app.include_router(router)
app.include_router(auth_router)
app.include_router(auth)
app.include_router(profile)

app.add_middleware(TokenMiddleware)

templates = Jinja2Templates(directory="WebApp/FrontEnd/templates")

app.mount("/WebApp/FrontEnd", StaticFiles(directory="WebApp/FrontEnd"), name="static")
@app.get("/")
async def main(request: Request):
    return templates.TemplateResponse("mainString.html", {"request": request})
@app.get("/vk")
async def main(request: Request):
    return templates.TemplateResponse("VkSearch.html", {"request": request})
@app.get("/youtube")
async def main(request: Request):
    return templates.TemplateResponse("YTSearch.html", {"request": request})