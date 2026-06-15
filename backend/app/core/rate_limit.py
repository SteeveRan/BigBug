"""
Rate limiting with pyrate_limiter (custom FastAPI integration).

Replaces fastapi-limiter to avoid the ``_IncludedRouter.path`` bug
(fastapi-limiter accesses ``route.path`` which fails on nested routers
in FastAPI >= 0.115).

Uses in-memory rate limiting by default. In test mode or when
RATE_LIMIT_ENABLED=False, returns no-op dependencies so existing
tests are not affected.
"""

from __future__ import annotations

from fastapi import Request
from pyrate_limiter import Duration, Limiter, Rate

from app.config import settings


def _parse_rate(rate_string: str) -> Rate:
    """Parse a rate string like ``"5/minute"`` into a pyrate_limiter Rate."""
    count, unit = rate_string.split("/")
    return Rate(int(count), getattr(Duration, unit.upper()))


async def _noop_dependency(request: Request) -> None:
    """No-op dependency when rate limiting is disabled."""
    return None


# ---------------------------------------------------------------------------
# Custom RateLimiter replacing fastapi-limiter
# ---------------------------------------------------------------------------


class _RateLimiter:
    """Callable FastAPI dependency that rate-limits per-endpoint.

    Uses ``pyrate_limiter.Limiter.try_acquire()`` for rate checking with
    per-client identity keys, avoiding the ``route.path`` /
    ``_IncludedRouter`` bug in the upstream ``fastapi-limiter`` library.

    Client identity is determined by ``X-Forwarded-For`` header (if present)
    or the TCP ``client.host``. Requests without an identifying key are
    *not* rate-limited (pass-through).
    """

    def __init__(self, limiter: Limiter) -> None:
        self._limiter: Limiter = limiter

    @staticmethod
    def _identity(request: Request) -> str:
        """Extract client identity from request headers / host."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        client = request.client
        if client is not None:
            return client.host
        return ""

    def _key(self, request: Request) -> str:
        """Build the rate-limiting key: identity + path."""
        ident = self._identity(request)
        path = request.url.path
        return f"{ident}:{path}"

    async def __call__(self, request: Request) -> None:
        """FastAPI dependency callable — raises 429 if limit exceeded.

        Unlike fastapi-limiter, uses ``request.url.path`` directly instead
        of ``request.scope["route"].path``, avoiding the ``_IncludedRouter``
        AttributeError.
        """
        ident = self._identity(request)
        if not ident:
            return

        key = self._key(request)

        if not self._limiter.try_acquire(key):
            from fastapi import HTTPException

            raise HTTPException(
                status_code=429,
                detail={"detail": "Too many requests", "retry_after": 60},
                headers={"Retry-After": "60"},
            )


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------


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

    Returns a ``_RateLimiter`` callable in production, or a no-op when
    ``rate_limit_enabled`` is False or ``environment`` is "test".
    """
    if settings.environment == "test" or not settings.rate_limit_enabled:
        return _noop_dependency

    rate = _parse_rate(rate_string)
    limiter = Limiter(rate)
    return _RateLimiter(limiter=limiter)
