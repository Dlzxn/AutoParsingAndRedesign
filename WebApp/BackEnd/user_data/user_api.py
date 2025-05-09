from fastapi import APIRouter, Request
from WebApp.BackEnd.auth_api.auth_api_router import list_with_tokens
from WebApp.BackEnd.db.CRUD import db

data_router = APIRouter(prefix = "/api/user")

@data_router.get("/user_data")
async def get_user_data(request: Request):
    token = request.cookies.get("token")
    print("TOKEN", token)
    if token is not None:
        try:
            user = None
            for x in list_with_tokens:
                print(x)
                if str(x["token"]) == str(token):
                    print(x)
                    user = x["user"]
                    print("USER", user)
            if user is None:
                print("[ERROR] User not found")
                return None
            data = await db.is_subscribe(user.id)
            print("[DATA]", {"name": f"id {data[1]}", "subscriptionPlan": data[0]})
            return {"name": data[1], "subscriptionPlan": data[0]}
        except Exception as e:
            print("[ERROR]", e)
            return None
    else:
        print("Token is None")
        return None


