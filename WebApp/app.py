from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import HTTPException
from starlette.exceptions import HTTPException as HTTPstarException
import os, sys, uvicorn, json

from WebApp.BackEnd.SearchRouter import search_router
from WebApp.BackEnd.DownloadVideoRouter import router
from WebApp.BackEnd.auth.auth_router import auth_router
from WebApp.BackEnd.auth_api.auth_api_router import auth
from WebApp.BackEnd.profile.profile_router import profile_router as profile
from WebApp.Middleware.BaseTokenMiddleware import TokenMiddleware
from WebApp.BackEnd.EditorRouter import editor
from WebApp.BackEnd.ViewRouter import view
from WebApp.BackEnd.Tests.TestRouter import test
from WebApp.BackEnd.db.create_tables import create_tables, drop_tables
from WebApp.BackEnd.user_data.user_api import data_router
from WebApp.BackEnd.admin_panel.admin import adm_router
from WebApp.BackEnd.admin_panel.admin_api import adm_api
from WebApp.BackEnd.promo.db.create_tables_promo import create_tables_promo, drop_tables_promo

#settings
TEST_STATUS: bool = True
AUTH_MIDDLEWARE: bool = True
DELETE_DATABASE: bool = False
ERROR_FIX: bool = True

"""Start app"""
app = FastAPI(docs_url=None,          # отключает Swagger UI (/docs)
    redoc_url=None,         # отключает ReDoc (/redoc)
    openapi_url=None        # отключает OpenAPI JSON (/openapi.json)
                )
def platform_status(name: str) -> bool:
    """Проверка доступности платформы"""
    with open("WebApp/BackEnd/platform_status/platforms.json", "r") as f:
        status = json.load(f)[name]["status"]
    if status == "on":
        return True
    return False

@app.on_event("startup")
async def startup():
    if DELETE_DATABASE:
        await drop_tables()
        await drop_tables_promo()
    await create_tables()
    await create_tables_promo()

"""Handlers"""
app.include_router(search_router)
app.include_router(router)
app.include_router(auth_router)
app.include_router(auth)
app.include_router(profile)
app.include_router(editor)
app.include_router(view)
app.include_router(data_router)
app.include_router(adm_router)
app.include_router(adm_api)

if TEST_STATUS:
    app.include_router(test)

if AUTH_MIDDLEWARE:
    app.add_middleware(TokenMiddleware)

templates = Jinja2Templates(directory="WebApp/FrontEnd/templates")

app.mount("/WebApp/FrontEnd", StaticFiles(directory="WebApp/FrontEnd"), name="static")
@app.get("/")
async def main(request: Request):
    return templates.TemplateResponse("mainString.html", {"request": request})

@app.get("/tariffs")
async def tariffs(request: Request):
    return templates.TemplateResponse("tariffs.html", {"request": request})
@app.get("/features")
async def features(request: Request):
    return templates.TemplateResponse("features.html", {"request": request})
@app.get("/reviews")
async def review(request: Request):
    return templates.TemplateResponse("review.html", {"request": request})
@app.get("/video")
async def main_video(request: Request):
    return templates.TemplateResponse("videos.html", {"request": request})
@app.get("/text")
async def main_text(request: Request):
    return templates.TemplateResponse("text.html", {"request": request})
"""
Module with Platforms:
-Vk Video
-YouTube Shorts
-Tumblr
-Coub
-Reddit
...
"""
@app.get("/vk")
async def main_vk(request: Request):
    if platform_status("vk"):
        return templates.TemplateResponse("VkSearch.html", {"request": request})
    return templates.TemplateResponse("tex_platform.html", {"request": request})
@app.get("/youtube")
async def main_yt(request: Request):
    if platform_status("yt"):
        return templates.TemplateResponse("YTSearch.html", {"request": request})
    return templates.TemplateResponse("tex_platform.html", {"request": request})
@app.get("/tumblr")
async def main_tb(request: Request):
    if platform_status("tumblr"):
        return templates.TemplateResponse("TumblrSearch.html", {"request": request})
    return templates.TemplateResponse("tex_platform.html", {"request": request})
@app.get("/coub")
async def main_cb(request: Request):
    if platform_status("coub"):
        return templates.TemplateResponse("CoubSearch.html", {"request": request})
    return templates.TemplateResponse("tex_platform.html", {"request": request})
@app.get("/reddit")
async def main_reddit(request: Request):
    if platform_status("reddit"):
        return templates.TemplateResponse("RedditSearch.html", {"request": request})
    return templates.TemplateResponse("tex_platform.html", {"request": request})
@app.get("/imgur")
async def main_reddit(request: Request):
    if platform_status("imgur"):
        return templates.TemplateResponse("ImgurSearch.html", {"request": request})
    return templates.TemplateResponse("tex_platform.html", {"request": request})

if ERROR_FIX:
    """
    Module For Exceptions:
    404 - Not Found
    And For All Exceptions
    """

    @app.exception_handler(HTTPstarException)
    async def all_exceptions(request: Request, exception: HTTPException):
        if exception.status_code == 404:
            return templates.TemplateResponse("NotFoundPage.html", {"request": request})
        else:
            return templates.TemplateResponse("InternetErrorPage.html", {"request": request})

