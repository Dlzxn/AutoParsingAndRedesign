from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from WebApp.Middleware.AdminMiddleware import admin_middleware
from WebApp.BackEnd.admin_panel.export.to_csv import export_to_csv

adm_router = APIRouter(prefix = "/admin", tags = ["admin"], dependencies=[Depends(admin_middleware)])
templates = Jinja2Templates(directory="WebApp/FrontEnd/templates")
adm_router.mount("/WebApp/FrontEnd", StaticFiles(directory="WebApp/FrontEnd"), name="static")

@adm_router.get("/")
async def adm_main_page(request: Request):
    return templates.TemplateResponse("admin_panel.html", {"request": request})
@adm_router.get("/users")
async def adm_main_page(request: Request):
    return templates.TemplateResponse("users_list_adm.html", {"request": request})
@adm_router.get("/pricing")
async def adm_main_page(request: Request):
    return templates.TemplateResponse("tarif_adm.html", {"request": request})
@adm_router.get("/export")
async def to_csv(request: Request):
    await export_to_csv()
    return FileResponse("data.csv")
@adm_router.get("/promocode")
async def adm_promo(request: Request):
    return templates.TemplateResponse("adm_promo.html", {"request": request})
@adm_router.get("/platforms")
async def adm_promo(request: Request):
    return templates.TemplateResponse("platforms.html", {"request": request})
