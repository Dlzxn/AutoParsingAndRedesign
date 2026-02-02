from fastapi import APIRouter, Response, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from WebApp.BackEnd.auth_api.auth_api_router import list_with_tokens
auth_router = APIRouter()

auth_router.mount("/WebApp/FrontEnd", StaticFiles(directory="WebApp/FrontEnd"), name="static")


@auth_router.get("/login")
async def login():
    return FileResponse("WebApp/FrontEnd/templates/login.html")


@auth_router.get("/registration")
async def registration():
    return FileResponse("WebApp/FrontEnd/templates/registration.html")

@auth_router.get("/logout")
async def logout(request: Request, response: Response):
    user_token = request.cookies.get("token")
    for data in list_with_tokens:
        if str(data["token"]) == user_token:
            list_with_tokens.remove(data)
            print("[INFO] User logged out, token removed")
    response = RedirectResponse(url="/")
    response.delete_cookie("token")
    return response

