from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

editor = APIRouter()
templates = Jinja2Templates(directory="WebApp/FrontEnd/templates")

@editor.get("/editor")
async def editor_index(text: str, request: Request):
    print(text)
    return templates.TemplateResponse("editor.html", {"request": request, "text": text})