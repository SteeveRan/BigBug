"""
Rate limiting with fastapi-limiter + pyrate_limiter.

Uses in-memory rate limiting by default. In test mode or when
RATE_LIMIT_ENABLED=False, returns no-op dependencies so existing
tests are not affected.
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi_limiter.depends import RateLimiter
from pyrate_limiter import Duration, Limiter, Rate

from app.config import settings


async def _rate_limit_exceeded_callback(request: Request, response):
    """Custom 429 handler returning the standard BigBug error format.

    The ``retry_after`` hint is a fixed 60 seconds — a reasonable
    default for per-endpoint limits applied to login/OIDC exchange.
    """
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests", "retry_after": 60},
        headers={"Retry-After": "60"},
    )


def _parse_rate(rate_string: str) -> Rate:
    """Parse a rate string like ``"5/minute"`` into a pyrate_limiter Rate."""
    count, unit = rate_string.split("/")
    return Rate(int(count), getattr(Duration, unit.upper()))


async def _noop_dependency(request: Request):
    """No-op dependency when rate limiting is disabled."""
    return None


def rate_limit(rate_string: str):
    """FastAPI dependency factory for per-endpoint rate limiting.

    Usage in a router::

        @router.post("/login")
        async def login(
            request: Request,
            data: LoginRequest,
            db: AsyncSession = Depends(get_db),
            _rl: None = Depends(rate_limit(settings.rate_limit_login)),
        ):
            ...

    Returns a ``RateLimiter`` callable in production, or a no-op when
    ``rate_limit_enabled`` is False or ``environment`` is "test".
    """
    if settings.environment == "test" or not settings.rate_limit_enabled:
        return _noop_dependency

    rate = _parse_rate(rate_string)
    limiter = Limiter([rate])
    return RateLimiter(limiter=limiter, callback=_rate_limit_exceeded_callback)
