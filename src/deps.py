import time
import uuid
from typing import Callable

from fastapi import Depends, Header, HTTPException, Request, status
from limits import RateLimitItemPerMinute
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowElasticExpiryRateLimiter

from .settings import Settings, get_settings


class APIKeyChecker:
    def __init__(self, settings: Settings):
        self.enabled = bool(settings.API_KEY)
        self.expected = settings.API_KEY

    async def __call__(self, x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
        if not self.enabled:
            return
        if not x_api_key or x_api_key != self.expected:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={
                "code": "unauthorized",
                "message": "Missing or invalid API key",
            })


def get_api_key_checker(settings: Settings = Depends(get_settings)) -> APIKeyChecker:
    return APIKeyChecker(settings)


class RateLimiter:
    def __init__(self, settings: Settings):
        self.storage = MemoryStorage()
        self.strategy = FixedWindowElasticExpiryRateLimiter(self.storage)
        self.per_minute = settings.RATE_LIMIT_PER_MIN
        self.burst = settings.RATE_LIMIT_BURST

    async def __call__(self, request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        key = f"ip:{client_ip}"
        item = RateLimitItemPerMinute(self.per_minute)
        allowed = self.strategy.test(item, key)
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail={
                "code": "rate_limited",
                "message": "Too many requests",
            })
        # consume one token; FixedWindowElasticExpiryRateLimiter can track bursts naturally
        self.strategy.hit(item, key)


def get_rate_limiter(settings: Settings = Depends(get_settings)) -> RateLimiter:
    return RateLimiter(settings)


def request_id_generator(request: Request) -> str:
    rid = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    return rid
