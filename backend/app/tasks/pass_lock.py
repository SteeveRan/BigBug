"""Job-pass lock: prevents overlapping runs of the same scheduled pass.

Usage in a scheduler job:

    async with job_pass_lock("sync_all") as acquired:
        if not acquired:
            return  # another pass holds the lock
        ...run the pass...

TTL must exceed the max expected pass duration; Redis expires the key
on worker death, so no manual cleanup is needed.
"""

import contextlib
import logging
from collections.abc import AsyncIterator

from redis.asyncio import Redis

from app.config import settings

logger = logging.getLogger(__name__)

_lock_clients: dict[str, Redis] = {}


def _get_client(url: str) -> Redis:
    if url not in _lock_clients:
        _lock_clients[url] = Redis.from_url(url)
    return _lock_clients[url]


def job_pass_lock(
    name: str,
    ttl_seconds: int = 3600,
    *,
    client: Redis | None = None,
):
    """Context manager yielding True if the lock was acquired, False if skipped."""

    @contextlib.asynccontextmanager
    async def _ctx() -> AsyncIterator[bool]:
        redis = client or _get_client(settings.redis_url)
        key = f"bigbug:job_pass_lock:{name}"
        acquired = bool(await redis.set(key, "1", nx=True, px=ttl_seconds * 1000))
        if not acquired:
            logger.info("job pass %s skipped: lock held", name)
        try:
            yield acquired
        finally:
            if acquired:
                await redis.delete(key)

    return _ctx()
