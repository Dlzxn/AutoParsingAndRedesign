from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
import json

from WebApp.BackEnd.auth_api.auth_api_router import list_with_tokens

editor = APIRouter()
templates = Jinja2Templates(directory="WebApp/FrontEnd/templates")

@editor.get("/editor")
async def editor_index(text: str, video_url: str, request: Request):
    print(text)
    token = request.cookies.get("token")
    with open("Data/clips_history.json", "r") as file:
        print("OPEN FILE AS JSON")
        clips = json.load(file)
        user = " "

    with open("Data/clips_history.json", "w") as file:
        for x in list_with_tokens:
            print(x["token"], token)
            if str(x["token"]) == str(token):
                user = x["user"]
                print(f"User: {user.password} {user.id}, {user.email}")
        clips_user = []
        try:
            clips_user = clips[str(user.id)]
            clips_user.append(video_url)
        except KeyError:
            print(KeyError)
            clips_user = [video_url]
        finally:
            clips[user.id] = clips_user
            json.dump(clips, file)
            print("Json Dumped")
    return templates.TemplateResponse("editor.html", {"request": request, "text": text})