"""
@file trust_store.py
@description :class:`TrustStoreService` — CRUD for named CA bundles (ADR-0037).
              PEM is validated with ``cryptography.x509``; the SHA-256
              fingerprint is computed at save time. Deleting a store that is
              referenced by providers raises DomainError 409 with the list of
              referring providers. Raises :class:`DomainError` (not
              HTTPException) to stay transport-agnostic.
@dependencies sqlalchemy, cryptography, app.models.trust_store
@relatedFiles ../api/trust_stores.py, ../schemas/trust_store.py, ./providers/service.py
"""

from __future__ import annotations

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import DomainError
from app.models.resource_provider import ResourceProvider
from app.models.trust_store import TrustStore, TrustStoreCertificate


def _parse_pem_blocks(pem_text: str) -> list[str]:
    """Split a PEM text into individual certificate blocks and validate them.

    A chain paste (several BEGIN CERTIFICATE blocks in one text) becomes
    separate certificates. Anything that is not a parseable certificate raises
    DomainError 422.
    """
    lines = [line.strip() for line in pem_text.strip().splitlines()]
    blocks: list[str] = []
    current: list[str] = []
    inside = False
    for line in lines:
        if line == "-----BEGIN CERTIFICATE-----":
            if inside:
                raise DomainError("Invalid PEM: nested certificate blocks", 422)
            inside = True
            current = [line]
        elif inside:
            current.append(line)
            if line == "-----END CERTIFICATE-----":
                blocks.append("\n".join(current))
                current = []
                inside = False
    if inside or not blocks:
        raise DomainError("Invalid PEM: no certificate found", 422)

    for block in blocks:
        try:
            x509.load_pem_x509_certificate(block.encode())
        except ValueError as exc:
            raise DomainError(f"Invalid PEM certificate: {exc}", 422) from exc
    return blocks


def _fingerprint(pem_block: str) -> str:
    """SHA-256 of the DER body as lowercase hex (64 chars)."""
    cert = x509.load_pem_x509_certificate(pem_block.encode())
    digest = cert.fingerprint(hashes.SHA256())
    return digest.hex()


class TrustStoreService:
    """Business logic for ``trust_stores`` (ADR-0037)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Helpers ─────────────────────────────────────────────────────────

    async def _get_or_404(self, store_id: int) -> TrustStore:
        result = await self.db.execute(
            select(TrustStore)
            .options(selectinload(TrustStore.certificates))
            .where(TrustStore.id == store_id)
        )
        store = result.scalar_one_or_none()
        if store is None:
            raise DomainError(f"Trust store {store_id} not found", 404)
        return store

    # ── CRUD ────────────────────────────────────────────────────────────

    async def list_stores(self) -> list[TrustStore]:
        result = await self.db.execute(
            select(TrustStore)
            .options(selectinload(TrustStore.certificates))
            .order_by(TrustStore.name)
        )
        return list(result.scalars().all())

    async def get_store(self, store_id: int) -> TrustStore:
        return await self._get_or_404(store_id)

    async def create_store(self, *, name: str, description: str | None = None) -> TrustStore:
        await self._ensure_name_free(name)
        store = TrustStore(name=name, description=description)
        self.db.add(store)
        await self.db.commit()
        return await self._get_or_404(store.id)

    async def update_store(
        self,
        store_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> TrustStore:
        store = await self._get_or_404(store_id)
        if name is not None and name != store.name:
            await self._ensure_name_free(name)
            store.name = name
        if description is not None:
            store.description = description
        await self.db.commit()
        return await self._get_or_404(store.id)

    async def delete_store(self, store_id: int) -> None:
        """Hard delete, gated by usage: RESTRICT FK — a store referenced by a
        provider must not silently disappear (ADR-0037)."""
        store = await self._get_or_404(store_id)
        providers = await self.get_usage(store_id)
        if providers:
            raise DomainError(
                f"Trust store is in use by providers: {', '.join(providers)}", 409
            )
        await self.db.delete(store)
        await self.db.commit()

    async def _ensure_name_free(self, name: str) -> None:
        existing = await self.db.execute(
            select(TrustStore).where(
                TrustStore.name == name,
                TrustStore.is_deleted.is_(False),
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise DomainError(f"Trust store name '{name}' already exists", 409)

    # ── Certificates ────────────────────────────────────────────────────

    async def add_certificates(
        self, store_id: int, items: list[tuple[str, str]]
    ) -> list[TrustStoreCertificate]:
        """Add certificates ``[(name, pem), ...]``. Each ``pem`` may be a chain
        (several blocks) — every block becomes its own row. Duplicate names
        inside one request are rejected before any insert."""
        store = await self._get_or_404(store_id)

        parsed: list[tuple[str, str, str]] = []  # (name, pem_block, fingerprint)
        seen_names: set[str] = set()
        for name, pem in items:
            blocks = _parse_pem_blocks(pem)
            names = [name] if len(blocks) == 1 else [f"{name}-{i + 1}" for i in range(len(blocks))]
            for cert_name, block in zip(names, blocks, strict=True):
                if cert_name in seen_names or any(c.name == cert_name for c in store.certificates):
                    raise DomainError(f"Certificate name '{cert_name}' already exists", 409)
                seen_names.add(cert_name)
                parsed.append((cert_name, block, _fingerprint(block)))

        for cert_name, block, fp in parsed:
            cert = TrustStoreCertificate(
                trust_store_id=store.id,
                name=cert_name,
                pem=block,
                fingerprint=fp,
            )
            self.db.add(cert)
        await self.db.commit()
        # Sessions with expire_on_commit=False (tests) keep the stale empty
        # collection in the identity map — reload it explicitly.
        await self.db.refresh(store, ["certificates"])
        return store.certificates

    async def delete_certificate(self, store_id: int, certificate_id: int) -> None:
        """Remove one certificate (e.g. a rotated intermediate CA)."""
        store = await self._get_or_404(store_id)
        for cert in store.certificates:
            if cert.id == certificate_id:
                await self.db.delete(cert)
                await self.db.commit()
                await self.db.refresh(store, ["certificates"])
                return
        raise DomainError(f"Certificate {certificate_id} not found", 404)

    # ── Usage ───────────────────────────────────────────────────────────

    async def get_usage(self, store_id: int) -> list[str]:
        """Names of live providers referencing the store (409 payload, ADR-0037)."""
        result = await self.db.execute(
            select(ResourceProvider.name).where(
                ResourceProvider.trust_store_id == store_id,
                ResourceProvider.is_deleted.is_(False),
            )
        )
        return [row.name for row in result.all()]
