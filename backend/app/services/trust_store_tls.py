"""
@file trust_store_tls.py
@description TLS trust injection for outbound provider connections (ADR-0037,
              issue #90). Centralizes the two materializations of a TrustStore:
              an in-memory :class:`ssl.SSLContext` for httpx ``verify=`` and a
              PEM bundle file (disk cache) for python-gitlab ``ssl_verify=`` and
              the git CLI (``GIT_SSL_CAINFO``). Semantics (ADR-0037 table):
              ``verify_ssl=False`` always wins and no context is built; a store
              replaces the trusted set entirely; no store keeps the existing
              env/system behavior (``app.core.http.ssl_verify()``).
@dependencies ssl, hashlib, app.config, app.core.http, app.models.trust_store
@relatedFiles services/providers/clients/_http.py, services/providers/service.py,
             services/gitlab_projects/_clients.py, services/source_providers/dispatcher.py
"""

from __future__ import annotations

import logging
import ssl
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.http import ssl_verify
from app.models.trust_store import TrustStore

logger = logging.getLogger(__name__)

# Everything httpx ``verify=`` and python-gitlab ``ssl_verify=`` accept.
TlsVerify = bool | str | ssl.SSLContext


async def provider_trust_pem(db: AsyncSession, trust_store_id: int | None) -> str | None:
    """Concatenated PEM of the store's certificates, or ``None``."""
    if trust_store_id is None:
        return None
    result = await db.execute(
        select(TrustStore)
        .options(selectinload(TrustStore.certificates))
        .where(TrustStore.id == trust_store_id)
    )
    store = result.unique().scalar_one_or_none()
    if store is None:
        logger.warning("Trust store %s not found for TLS injection", trust_store_id)
        return None
    return "\n".join(cert.pem for cert in store.certificates) or None


def ssl_context_for(verify_ssl: bool, pem: str | None) -> TlsVerify:
    """``verify=`` value for httpx clients per the ADR-0037 semantics table."""
    if not verify_ssl:
        return False
    if pem:
        return ssl.create_default_context(cadata=pem)
    return ssl_verify()


async def resolve_bundle_path(db: AsyncSession, trust_store_id: int | None) -> str | None:
    """PEM bundle file path for clients that need a path (python-gitlab, git CLI).

    The file is (re)written only when missing or stale, so an unchanged store
    costs one DB read. Atomic write (tmp + rename) — concurrent readers never
    see a half-written bundle.
    """
    pem = await provider_trust_pem(db, trust_store_id)
    if pem is None:
        return None
    directory = Path(settings.data_dir) / "trust_stores"
    path = directory / f"{trust_store_id}.pem"
    if not path.exists() or path.read_text() != pem:
        directory.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.tmp")
        tmp.write_text(pem)
        tmp.replace(path)
    return str(path)


async def provider_ssl_verify(db: AsyncSession, provider: object) -> TlsVerify:
    """``ssl_verify=`` for python-gitlab: False / bundle path / True."""
    if not getattr(provider, "verify_ssl", True):
        return False
    path = await resolve_bundle_path(db, getattr(provider, "trust_store_id", None))
    return path or True


async def provider_httpx_verify(db: AsyncSession, provider: object) -> TlsVerify:
    """``verify=`` (via ``make_client(ssl_context=...)``) for httpx clients."""
    verify_ssl: bool = getattr(provider, "verify_ssl", True)
    pem: str | None = None
    if verify_ssl:
        pem = await provider_trust_pem(db, getattr(provider, "trust_store_id", None))
    return ssl_context_for(verify_ssl, pem)
