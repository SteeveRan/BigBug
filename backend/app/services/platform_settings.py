"""
@file platform_settings.py
@description Typed accessor for the platform_settings key/value table
              (issue #114). get/set are plain DB helpers; maintenance mode
              adds a process-wide 30 s TTL cache so scheduler passes do not
              hit the DB every job, and a public one-liner for the status
              endpoint. set_setting invalidates the cache immediately.
@dependencies sqlalchemy
@relatedFiles ../models/platform_setting.py, ../api/maintenance.py, ../services/scheduler.py
"""

import logging
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform_setting import PlatformSetting

logger = logging.getLogger(__name__)

MAINTENANCE_KEY = "maintenance_mode"
_CACHE_TTL_SECONDS = 30.0

# Process-wide maintenance-mode cache: (monotonic_time, value).
_maintenance_cache: tuple[float, bool] | None = None


async def get_setting(db: AsyncSession, key: str, default=None):
    """Return the JSON value for *key*, or *default* if the row is missing."""
    result = await db.execute(select(PlatformSetting).where(PlatformSetting.key == key))
    row = result.scalar_one_or_none()
    return row.value if row else default


async def set_setting(db: AsyncSession, key: str, value) -> None:
    """Upsert *key* with a JSON *value* and invalidate the maintenance cache."""
    result = await db.execute(select(PlatformSetting).where(PlatformSetting.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        row = PlatformSetting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
    await db.commit()
    if key == MAINTENANCE_KEY:
        invalidate_maintenance_cache()


def invalidate_maintenance_cache() -> None:
    global _maintenance_cache
    _maintenance_cache = None


async def _read_maintenance_mode() -> bool:
    """DB read with own session — safe to call from the scheduler.

    Fail-open: if the DB is unreachable the flag is treated as False —
    maintenance mode is an optimization, and every enqueue writes to the
    same DB anyway, so an outage degrades normally.
    """
    from app.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            return bool(await get_setting(db, MAINTENANCE_KEY, False))
    except Exception:
        logger.warning("maintenance_mode read failed — assuming False (fail-open)")
        return False


async def is_maintenance_mode(*, force_refresh: bool = False) -> bool:
    """Cached (30 s TTL) maintenance-mode flag for scheduler pass gating."""
    global _maintenance_cache
    if not force_refresh and _maintenance_cache is not None:
        fetched_at, value = _maintenance_cache
        if (time.monotonic() - fetched_at) <= _CACHE_TTL_SECONDS:
            return value
    value = await _read_maintenance_mode()
    _maintenance_cache = (time.monotonic(), value)
    return value
