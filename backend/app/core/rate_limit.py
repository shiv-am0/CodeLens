import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request

from app.core.config import settings


class InMemoryRateLimiter:
    """Small single-instance limiter; use a shared store when scaling horizontally."""

    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            requests = self._requests[key]
            while requests and requests[0] <= cutoff:
                requests.popleft()
            if len(requests) >= self.limit:
                retry_after = max(1, int(self.window_seconds - (now - requests[0])))
                raise HTTPException(
                    status_code=429,
                    detail={
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests. Please try again later.",
                    },
                    headers={"Retry-After": str(retry_after)},
                )
            requests.append(now)


analysis_limiter = InMemoryRateLimiter(settings.analysis_requests_per_hour, 3600)
chat_limiter = InMemoryRateLimiter(settings.chat_requests_per_minute, 60)
admin_login_limiter = InMemoryRateLimiter(5, 15 * 60)


def client_identifier(request: Request) -> str:
    # Render supplies the original client first in X-Forwarded-For.
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def limit_analysis_requests(request: Request) -> None:
    analysis_limiter.check(client_identifier(request))


def limit_chat_requests(request: Request) -> None:
    chat_limiter.check(client_identifier(request))
