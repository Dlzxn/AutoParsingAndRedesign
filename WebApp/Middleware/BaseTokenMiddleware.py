from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import FileResponse, RedirectResponse


class TokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        token = request.cookies.get("token")
        print("TOKEN", token)
        print(request.url.path)
        if (".js" in request.url.path or ".css" in request.url.path or "/login" == request.url.path or "/api"
                in request.url.path):
            return await call_next(request)
        if not token is None or request.url.path == "/registration":
            response = await call_next(request)
            return response
        else:
            return RedirectResponse("/registration")

