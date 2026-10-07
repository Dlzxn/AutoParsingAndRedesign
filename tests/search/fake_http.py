"""Подмена aiohttp.ClientSession для тестов провайдеров: маршруты по префиксу URL, запись вызовов."""
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Call:
    method: str
    url: str
    kwargs: dict

    @property
    def params(self) -> dict:
        return self.kwargs.get("params") or {}

    @property
    def headers(self) -> dict:
        return self.kwargs.get("headers") or {}


@dataclass
class Route:
    method: str
    prefix: str
    status: int = 200
    payload: Any = None
    body: str | None = None
    exception: BaseException | None = None
    repeat: bool = False
    used: bool = field(default=False)


class FakeResponse:
    def __init__(self, status: int, text: str) -> None:
        self.status = status
        self._text = text

    async def text(self) -> str:
        return self._text

    async def json(self, content_type: str | None = None) -> Any:
        return json.loads(self._text)


class _RequestContext:
    def __init__(self, route: Route) -> None:
        self.route = route

    async def __aenter__(self) -> FakeResponse:
        if self.route.exception is not None:
            raise self.route.exception
        text = self.route.body if self.route.body is not None else json.dumps(self.route.payload)
        return FakeResponse(self.route.status, text)

    async def __aexit__(self, *exc) -> None:
        return None


class FakeSession:
    def __init__(self) -> None:
        self.routes: list[Route] = []
        self.calls: list[Call] = []

    def add(self, method: str, prefix: str, **kwargs) -> "FakeSession":
        self.routes.append(Route(method.upper(), prefix, **kwargs))
        return self

    def get(self, prefix: str, **kwargs) -> "FakeSession":
        return self.add("GET", prefix, **kwargs)

    def post(self, prefix: str, **kwargs) -> "FakeSession":
        return self.add("POST", prefix, **kwargs)

    def request(self, method: str, url: str, **kwargs) -> _RequestContext:
        self.calls.append(Call(method.upper(), url, kwargs))
        for route in self.routes:
            if route.method == method.upper() and url.startswith(route.prefix) and (route.repeat or not route.used):
                route.used = True
                return _RequestContext(route)
        raise AssertionError(f"Unexpected request: {method} {url}")

    def calls_to(self, prefix: str) -> list[Call]:
        return [c for c in self.calls if c.url.startswith(prefix)]
