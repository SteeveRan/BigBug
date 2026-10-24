"""
@file trust_stores.py
@description REST API for Trust Stores (ADR-0037). Permissions:
              ``trust_stores:read`` for reads, ``trust_stores:write`` for
              mutations (admin-only per RBAC matrix). DomainError raised by the
              service is mapped to HTTP via the app-level handler.
@dependencies app.core.rbac, app.schemas.trust_store, app.services.trust_store
@relatedFiles ../services/trust_store.py, ../schemas/trust_store.py
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.trust_store import (
    TrustStoreCertificateOut,
    TrustStoreCertificatesIn,
    TrustStoreCreate,
    TrustStoreOut,
    TrustStoreUpdate,
    TrustStoreUsageOut,
)
from app.services.trust_store import TrustStoreService

router = APIRouter()


# ──── Stores CRUD ──────────────────────────────────────────────────────────


@router.get("", response_model=list[TrustStoreOut])
async def list_trust_stores(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("trust_stores:read")),
):
    return await TrustStoreService(db).list_stores()


@router.get("/{store_id}", response_model=TrustStoreOut)
async def get_trust_store(
    store_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("trust_stores:read")),
):
    return await TrustStoreService(db).get_store(store_id)


@router.post("", response_model=TrustStoreOut, status_code=status.HTTP_201_CREATED)
async def create_trust_store(
    data: TrustStoreCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("trust_stores:write")),
):
    return await TrustStoreService(db).create_store(name=data.name, description=data.description)


@router.patch("/{store_id}", response_model=TrustStoreOut)
async def update_trust_store(
    store_id: int,
    data: TrustStoreUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("trust_stores:write")),
):
    return await TrustStoreService(db).update_store(
        store_id, name=data.name, description=data.description
    )


@router.delete("/{store_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trust_store(
    store_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("trust_stores:write")),
):
    await TrustStoreService(db).delete_store(store_id)


# ──── Certificates ─────────────────────────────────────────────────────────


@router.post(
    "/{store_id}/certificates",
    response_model=list[TrustStoreCertificateOut],
    status_code=status.HTTP_201_CREATED,
)
async def add_certificates(
    store_id: int,
    data: TrustStoreCertificatesIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("trust_stores:write")),
):
    """Add one certificate ({name, pem}) or a chain (multi-block PEM is split
    into separate rows)."""
    service = TrustStoreService(db)
    await service.add_certificates(store_id, [(i.name, i.pem) for i in data.items()])
    store = await service.get_store(store_id)
    return list(store.certificates)


@router.delete(
    "/{store_id}/certificates/{certificate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_certificate(
    store_id: int,
    certificate_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("trust_stores:write")),
):
    """Remove one certificate (e.g. a rotated intermediate CA)."""
    await TrustStoreService(db).delete_certificate(store_id, certificate_id)


# ──── Usage ────────────────────────────────────────────────────────────────


@router.get("/{store_id}/usage", response_model=TrustStoreUsageOut)
async def get_trust_store_usage(
    store_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("trust_stores:read")),
):
    providers = await TrustStoreService(db).get_usage(store_id)
    return TrustStoreUsageOut(trust_store_id=store_id, providers=providers)
