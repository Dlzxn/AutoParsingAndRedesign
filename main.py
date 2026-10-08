"""Совместимость со старым способом запуска (uvicorn main:app). Предпочтительно: uvicorn app.asgi:app"""
from app.asgi import app  # noqa: F401
