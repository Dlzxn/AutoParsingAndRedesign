from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles



import uvicorn

app = FastAPI()

app.mount("/WebApp/FrontEnd", StaticFiles(directory="WebApp/FrontEnd"), name="static")
@app.get("/")
async def main():
    return FileResponse("WebApp/FrontEnd/templates/mainString.html")


def start_server():
    uvicorn.run(app, host="0.0.0.0", port=8000)