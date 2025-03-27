from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os, sys,uvicorn

from WebApp.BackEnd.SearchRouter import search_router
from WebApp.BackEnd.DownloadVideoRouter import router
from WebApp.BackEnd.auth.auth_router import auth_router
from WebApp.BackEnd.auth_api import auth_api_router
from WebApp.BackEnd.auth_api.auth_api_router import auth
from WebApp.Middleware.BaseTokenMiddleware import TokenMiddleware

app = FastAPI()
app.include_router(search_router)
app.include_router(router)
app.include_router(auth_router)
app.include_router(auth)

#app.add_middleware(TokenMiddleware)

app.mount("/WebApp/FrontEnd", StaticFiles(directory="WebApp/FrontEnd"), name="static")
@app.get("/")
async def main():
    return FileResponse("WebApp/FrontEnd/templates/mainString.html")


@app.get("/files")
async def files():
    current_dir = os.getcwd()

    # Проверяем платформу и открываем папку соответствующим способом
    if sys.platform == "win32":
        os.startfile(f"{current_dir}/Data")  # Windows
    elif sys.platform == "darwin":
        os.system(f'open "{current_dir}/Data"')  # macOS
    else:
        os.system(f'xdg-open "{current_dir}/Data"')  # Linux
    return {
    "status": "success",
    "message": "Папка успешно открыта."
}