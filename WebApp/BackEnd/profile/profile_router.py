from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


profile_router = APIRouter(prefix="/profile", tags=["Profile"])

profile_router.mount("/WebApp/FrontEnd", StaticFiles(directory="WebApp/FrontEnd"), name="static")

templates = Jinja2Templates(directory="WebApp/FrontEnd/templates")

@profile_router.get("/")
async def get_profile(request: Request):
    return templates.TemplateResponse("profile.html", {"request": request})