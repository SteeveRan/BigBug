"""
@file oidc_providers.py
@description Service for managing the OIDC provider collection (ADR-0037).
              Provides CRUD, a 60 s TTL cache, and automatic client_secret
              encryption/decryption. Replaces the former singleton
              oidc_config service.
@dependencies app.core.secrets (encrypt_secret/decrypt_secret)
@relatedFiles ../models/oidc_provider.py, ../schemas/oidc_provider.py, ./oidc.py
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.secrets import decrypt_secret, encrypt_secret
from app.models.oidc_provider import OIDCProvider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cached provider snapshot (process-wide, TTL 60 s)
# ---------------------------------------------------------------------------


@dataclass
class CachedOIDCProvider:
    """Lightweight snapshot of one OIDC provider for the OIDC service."""

    id: int = 0
    name: str = ""
    issuer_url: str = ""
    client_id: str = ""
    client_secret: str | None = None
    frontend_client_id: str = ""
    enabled: bool = False
    public_url: str | None = None
    role_mapping: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# In-memory TTL cache for the provider collection
# ---------------------------------------------------------------------------


class _ProvidersCache:
    """
    Process-wide TTL cache for the OIDC provider list.

    Split into a separate class so the TTL policy is testable in isolation
    and the service stays focused on DB access.
    """

    def __init__(self, ttl_seconds: float = 60.0) -> None:
        self._ttl = ttl_seconds
        self._cached: list[CachedOIDCProvider] | None = None
        self._fetched_at: float = 0.0
        self._lock = asyncio.Lock()

    async def get(
        self, db: AsyncSession, *, force_refresh: bool = False
    ) -> list[CachedOIDCProvider]:
        """
        Return the cached provider list, refreshing from DB when stale or
        forced. Uses an asyncio.Lock so concurrent cache-miss requests
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

            providers = await _fetch_provider_rows(db)
            self._cached = providers
            self._fetched_at = time.monotonic()
            return providers

    def invalidate(self) -> None:
        """Clear the cache, forcing the next read to hit the database."""
        self._cached = None
        self._fetched_at = 0.0


# Process-wide cache instance.
_providers_cache = _ProvidersCache(ttl_seconds=60.0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_cached(row: OIDCProvider) -> CachedOIDCProvider:
    """Map a DB row to a decrypted cache snapshot."""
    return CachedOIDCProvider(
        id=row.id,
        name=row.name,
        issuer_url=row.issuer_url,
        client_id=row.client_id,
        client_secret=decrypt_secret(row.client_secret),
        frontend_client_id=row.frontend_client_id,
        enabled=row.enabled,
        public_url=row.public_url,
        role_mapping=row.role_mapping or {},
    )


async def _fetch_provider_rows(db: AsyncSession) -> list[CachedOIDCProvider]:
    """Fetch all provider rows, ordered for the SSO button list."""
    result = await db.execute(
        select(OIDCProvider).order_by(OIDCProvider.sort_order, OIDCProvider.id)
    )
    return [_row_to_cached(row) for row in result.scalars().all()]


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class OIDCProviderService:
    """
    CRUD and caching for the :class:`OIDCProvider` collection.

    Usage::

        service = OIDCProviderService(db)
        providers = await service.list_providers()
        row = await service.create_provider(name=..., issuer_url=...)
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── CRUD ──────────────────────────────────────────────────────────

    async def get_provider(self, provider_id: int) -> OIDCProvider | None:
        """Return one provider DB row or ``None``."""
        result = await self.db.execute(select(OIDCProvider).where(OIDCProvider.id == provider_id))
        return result.scalar_one_or_none()

    async def list_providers(self) -> list[OIDCProvider]:
        """Return all provider rows, ordered for the SSO button list."""
        result = await self.db.execute(
            select(OIDCProvider).order_by(OIDCProvider.sort_order, OIDCProvider.id)
        )
        return list(result.scalars().all())

    async def create_provider(
        self,
        *,
        name: str,
        issuer_url: str = "",
        client_id: str = "",
        client_secret: str | None = None,
        frontend_client_id: str = "",
        enabled: bool = False,
        public_url: str | None = None,
        role_mapping: dict[str, str] | None = None,
        sort_order: int = 0,
    ) -> OIDCProvider:
        row = OIDCProvider(
            name=name,
            issuer_url=issuer_url,
            client_id=client_id,
            client_secret=encrypt_secret(client_secret) if client_secret else None,
            frontend_client_id=frontend_client_id,
            enabled=enabled,
            public_url=public_url,
            role_mapping=role_mapping or {},
            sort_order=sort_order,
        )
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        invalidate_oidc_providers_cache()
        return row

    async def update_provider(
        self,
        provider_id: int,
        *,
        name: str | None = None,
        issuer_url: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        frontend_client_id: str | None = None,
        enabled: bool | None = None,
        public_url: str | None = None,
        role_mapping: dict[str, str] | None = None,
        sort_order: int | None = None,
    ) -> OIDCProvider | None:
        """PATCH semantics: ``None`` fields are left unchanged."""
        row = await self.get_provider(provider_id)
        if row is None:
            return None

        if name is not None:
            row.name = name
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
        if sort_order is not None:
            row.sort_order = sort_order

        await self.db.commit()
        await self.db.refresh(row)
        invalidate_oidc_providers_cache()
        return row

    async def delete_provider(self, provider_id: int) -> bool:
        """Delete one provider; returns ``False`` when it doesn't exist."""
        row = await self.get_provider(provider_id)
        if row is None:
            return False
        await self.db.delete(row)
        await self.db.commit()
        invalidate_oidc_providers_cache()
        return True

    # ── Cached accessors for the OIDC service / public endpoints ──────

    async def get_enabled_providers_cached(self) -> list[CachedOIDCProvider]:
        """Enabled providers from the process-wide TTL cache."""
        return [p for p in await self.get_all_providers_cached() if p.enabled]

    async def get_provider_cached(self, provider_id: int) -> CachedOIDCProvider | None:
        """One provider snapshot from the process-wide TTL cache."""
        for p in await self.get_all_providers_cached():
            if p.id == provider_id:
                return p
        return None

    async def get_all_providers_cached(self) -> list[CachedOIDCProvider]:
        """All provider snapshots from the process-wide TTL cache."""
        return await _providers_cache.get(self.db)


# ---------------------------------------------------------------------------
# Module-level helpers for cache invalidation
# ---------------------------------------------------------------------------


def invalidate_oidc_providers_cache() -> None:
    """
    Invalidate the process-wide OIDC providers cache.

    Called after an admin changes the collection so the OIDC service
    reflects changes immediately.
    """
    _providers_cache.invalidate()
