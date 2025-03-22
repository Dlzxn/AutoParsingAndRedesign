from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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


def start_server():
    uvicorn.run(app, host="0.0.0.0", port=8000)