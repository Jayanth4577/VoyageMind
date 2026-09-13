"""In-memory sliding-window rate limiter (spec §8.2).

Dependency-free and Redis-independent so it works even when Redis is down.
Per-client-IP buckets with a stricter limit for auth endpoints (brute-force
protection). Limits are configurable via settings; 429 responses include
Retry-After.
"""
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_buckets: dict[str, deque[float]] = defaultdict(deque)
_last_cleanup = 0.0

AUTH_PREFIXES = ("/auth/login", "/auth/register")


def reset_rate_limiter() -> None:
    """Test hook: clear all buckets."""
    _buckets.clear()


def _prune(key: str, now: float, window: float) -> None:
    bucket = _buckets[key]
    while bucket and bucket[0] <= now - window:
        bucket.popleft()
    # Opportunistic global cleanup so abandoned buckets don't grow unbounded
    global _last_cleanup
    if len(_buckets) > 10_000 and now - _last_cleanup > 60:
        for k in [k for k, v in _buckets.items() if not v]:
            del _buckets[k]
        _last_cleanup = now


def _check(key: str, limit: int, window: float) -> tuple[bool, int]:
    """Return (allowed, retry_after_seconds)."""
    now = time.monotonic()
    _prune(key, now, window)
    bucket = _buckets[key]
    if len(bucket) >= limit:
        retry_after = max(1, int(window - (now - bucket[0])) + 1)
        return False, retry_after
    bucket.append(now)
    return True, 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not settings.rate_limit_enabled:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        window = 60.0
        if request.url.path.startswith(AUTH_PREFIXES):
            limit = settings.auth_rate_limit_per_minute
            key = f"auth:{client_ip}"
        else:
            limit = settings.rate_limit_per_minute
            key = f"api:{client_ip}"

        allowed, retry_after = _check(key, limit, window)
        if not allowed:
            logger.warning("rate limit exceeded for %s on %s", client_ip, request.url.path)
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(retry_after)},
                content={"detail": "Too many requests — slow down and try again shortly"},
            )
        return await call_next(request)
