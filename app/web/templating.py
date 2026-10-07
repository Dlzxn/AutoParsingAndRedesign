from datetime import datetime
from functools import lru_cache
from hashlib import md5

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.config import WEB_DIR

STATIC_DIR = WEB_DIR / "static"
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))


@lru_cache(maxsize=512)
def _file_version(path: str) -> str:
    try:
        return md5((STATIC_DIR / path).read_bytes(), usedforsecurity=False).hexdigest()[:10]
    except OSError:
        return "0"


def static_url(path: str) -> str:
    """URL статики с версией по содержимому файла — браузер не держит устаревший кэш после деплоя."""
    path = path.lstrip("/")
    return f"/static/{path}?v={_file_version(path)}"


templates.env.globals["static"] = static_url
templates.env.globals["now_year"] = datetime.now().year


def render(request: Request, name: str, status_code: int = 200, **context):
    context.setdefault("current_user", getattr(request.state, "user", None))
    return templates.TemplateResponse(request, name, context, status_code=status_code)
