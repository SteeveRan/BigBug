"""
@file oidc_config.py
@description Service for managing the OIDC configuration singleton row.
             Provides CRUD, caching (60 s TTL), and automatic client_secret
             encryption/decryption.
@dependencies app.core.secrets (encrypt_secret/decrypt_secret),
               app.config.settings (fallback for env vars when DB row missing)
@relatedFiles ../models/oidc_config.py, ../schemas/oidc_config.py, ./oidc.py
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.secrets import decrypt_secret, encrypt_secret
from app.models.oidc_config import OIDCConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cached config snapshot (process-wide, TTL 60 s)
# ---------------------------------------------------------------------------


@dataclass
class _CachedOIDCConfig:
    """Lightweight snapshot of the active OIDC config for the OIDC service."""

    issuer_url: str = ""
    client_id: str = ""
    client_secret: str | None = None
    frontend_client_id: str = ""
    enabled: bool = False
    public_url: str | None = None
    role_mapping: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# In-memory TTL cache for the active config
# ---------------------------------------------------------------------------


class _ConfigCache:
    """
    Process-wide TTL cache for the OIDC config row.

    Split into a separate class so the TTL policy is testable in isolation
    and the service stays focused on DB access.
    """

    def __init__(self, ttl_seconds: float = 60.0) -> None:
        self._ttl = ttl_seconds
        self._cached: _CachedOIDCConfig | None = None
        self._fetched_at: float = 0.0
        self._lock = asyncio.Lock()

    async def get(self, db: AsyncSession, *, force_refresh: bool = False) -> _CachedOIDCConfig:
        """
        Return the cached config, refreshing from DB when stale or forced.

        Uses an asyncio.Lock so that multiple concurrent cache-miss requests
        coalesce into a single DB query instead of thundering.
        """
        if not force_refresh:
            cached = self._cached
            if cached is not None and (time.monotonic() - self._fetched_at) <= self._ttl:
                return cached

        async with self._lock:
            # Double-check under lock — another coroutine may have refreshed
            # while we waited.
            if not force_refresh:
                cached = self._cached
                if cached is not None and (time.monotonic() - self._fetched_at) <= self._ttl:
                    return cached

            config = await _fetch_config_row(db)
            self._cached = config
            self._fetched_at = time.monotonic()
            return config

    def invalidate(self) -> None:
        """Clear the cache, forcing the next read to hit the database."""
        self._cached = None
        self._fetched_at = 0.0


# Process-wide cache instance.
_config_cache = _ConfigCache(ttl_seconds=60.0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config_row_to_cached(row: OIDCConfig) -> _CachedOIDCConfig:
    """Map a DB row to a decrypted cache snapshot."""
    return _CachedOIDCConfig(
        issuer_url=row.issuer_url,
        client_id=row.client_id,
        client_secret=decrypt_secret(row.client_secret),
        frontend_client_id=row.frontend_client_id,
        enabled=row.enabled,
        public_url=row.public_url,
        role_mapping=row.role_mapping or {},
    )


async def _fetch_config_row(db: AsyncSession) -> _CachedOIDCConfig:
    """Fetch the singleton OIDC config row from the DB.

    If no row exists (SSO not configured by an admin), returns a
    disabled default so the application remains operational without
    accidentally exposing an unconfigured SSO flow.
    """
    result = await db.execute(select(OIDCConfig).limit(1))
    row = result.scalar_one_or_none()
    if row is not None:
        return _config_row_to_cached(row)

    # No DB row → SSO stays disabled until explicitly configured by an admin.
    logger.info("oidc_config_no_db_row_sso_disabled")
    return _CachedOIDCConfig(
        issuer_url="",
        client_id="",
        client_secret=None,
        frontend_client_id="",
        enabled=False,
        public_url=None,
        role_mapping={},
    )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class OIDCConfigService:
    """
    CRUD and caching for the singleton :class:`OIDCConfig` row.

    Usage::

        service = OIDCConfigService(db)
        config = await service.get_config()
        await service.update_config(data)
        cached = await service.get_active_config_cached()
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── CRUD ──────────────────────────────────────────────────────────

    async def get_config(self) -> OIDCConfig | None:
        """Return the full DB row or ``None`` when SSO hasn't been configured yet.

        The caller (admin API) is responsible for presenting a meaningful
        default when no row exists.  This method deliberately does **not**
        auto-create a row — the admin must explicitly configure SSO via
        :meth:`update_config`.
        """
        result = await self.db.execute(select(OIDCConfig).limit(1))
        return result.scalar_one_or_none()

    async def update_config(
        self,
        issuer_url: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        frontend_client_id: str | None = None,
        enabled: bool | None = None,
        public_url: str | None = None,
        role_mapping: dict[str, str] | None = None,
    ) -> OIDCConfig:
        """Update the singleton OIDC config row, creating one if needed."""
        row = await self.get_config()
        if row is None:
            # First-time configuration — create the singleton row.
            row = OIDCConfig(
                issuer_url="",
                client_id="",
                client_secret=None,
                frontend_client_id="",
                enabled=False,
                public_url=None,
                role_mapping={},
            )
            self.db.add(row)
            await self.db.flush()

        if issuer_url is not None:
            row.issuer_url = issuer_url
        if client_id is not None:
            row.client_id = client_id
        if client_secret is not None:
            row.client_secret = encrypt_secret(client_secret) if client_secret else None
        if frontend_client_id is not None:
            row.frontend_client_id = frontend_client_id
        if enabled is not None:
            row.enabled = enabled
        if public_url is not None:
            row.public_url = public_url
        if role_mapping is not None:
            row.role_mapping = role_mapping

        await self.db.commit()
        await self.db.refresh(row)

        # Invalidate the shared cache so the OIDC service picks up changes
        # on the very next request.
        invalidate_oidc_cache()

        return row

    # ── Cached accessor for OIDC service ──────────────────────────────

    async def get_active_config_cached(self) -> _CachedOIDCConfig:
        """
        Return a lightweight snapshot of the active config.

        Reads from the process-wide TTL cache; hits the DB at most once
        every 60 seconds.
        """
        return await _config_cache.get(self.db)


# ---------------------------------------------------------------------------
# Module-level helpers for cache invalidation
# ---------------------------------------------------------------------------


def invalidate_oidc_cache() -> None:
    """
    Invalidate the process-wide OIDC config cache.

    Called after an admin updates the config so the OIDC service reflects
    changes immediately.
    """
    _config_cache.invalidate()


def get_oidc_config_sync() -> _CachedOIDCConfig | None:
    """
    **Synchronous** accessor intended for module-level initialisation
    (e.g. the `_jwks_cache` placeholder) where we cannot `await`.

    Returns ``None`` when the cache is cold; callers must fall back to
    ``settings.*`` in that case.
    """
    return _config_cache._cached
