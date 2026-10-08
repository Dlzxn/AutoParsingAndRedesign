"""Простой ограничитель частоты запросов в памяти процесса (скользящее окно)."""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, status


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float = 60.0) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str) -> bool:
        """Регистрирует обращение. Возвращает False, если лимит превышен."""
        if self.limit <= 0:
            return True
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        if len(self._hits) > 10_000:  # защита от разрастания словаря
            self._cleanup(now)
        return True

    def check(self, key: str, message: str = "Слишком много запросов, попробуйте через минуту") -> None:
        if not self.hit(key):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, message)

    def reset(self) -> None:
        self._hits.clear()

    def _cleanup(self, now: float) -> None:
        for key in [k for k, v in self._hits.items() if not v or now - v[-1] > self.window]:
            del self._hits[key]
