from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from WebApp.BackEnd.auth_api.auth_api_router import list_with_tokens


class TokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        token = request.cookies.get("token")
        print("TOKEN", token)
        print(request.url.path)
        if (".js" in request.url.path or ".css" in request.url.path or "/login" == request.url.path or "/api"
                in request.url.path or request.url.path[-1] == "/"):
            print(". call_next")
            return await call_next(request)
        if request.url.path == "/registration":
            response = await call_next(request)
            print("/reg call_next")
            return response
        print("len now", len(list_with_tokens))
        for elem in list_with_tokens:
            print(elem["token"], len(list_with_tokens))
            if str(elem["token"]) == str(token):
                print("in list_with_tokens")
                return await call_next(request)
        else:
            print("not in list_with_tokens")
            return RedirectResponse("/registration")

