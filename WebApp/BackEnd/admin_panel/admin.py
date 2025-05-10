from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from WebApp.Middleware.AdminMiddleware import admin_middleware

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
