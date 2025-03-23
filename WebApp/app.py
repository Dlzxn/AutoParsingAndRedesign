from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os, sys

from WebApp.BackEnd.SearchRouter import search_router
from WebApp.BackEnd.DownloadVideoRouter import router



import uvicorn

app = FastAPI()
app.include_router(search_router)
app.include_router(router)

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




def start_server():
    uvicorn.run(app, host="0.0.0.0", port=8000)