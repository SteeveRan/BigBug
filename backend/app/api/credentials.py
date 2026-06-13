"""
@file credentials.py
@description REST API for managing credentials — create, update, delete, and test
             encrypted secrets (GitHub tokens, GitLab tokens, HTTPS basic auth, SSH keys).
             Includes audit logging for all mutating operations.
@dependencies app.core.rbac, app.core.secrets, app.schemas.credential, app.services.audit
@relatedFiles ../models/credential.py, ../schemas/credential.py, ../services/audit.py
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import require_permission
from app.core.secrets import encrypt_secret
from app.database import get_db
from app.models.credential import Credential
from app.models.user import User
from app.schemas.credential import CredentialCreate, CredentialOut, CredentialUpdate
from app.services.audit import AuditService

router = APIRouter()


async def _get_credential_or_404(db: AsyncSession, credential_id: int) -> Credential:
    """Fetch a non-deleted credential or raise HTTP 404."""
    result = await db.execute(
        select(Credential).where(
            Credential.id == credential_id,
            ~Credential.is_deleted,
        )
    )
    credential = result.scalar_one_or_none()
    if credential is None:
        raise HTTPException(status_code=404, detail=f"Credential with id={credential_id} not found")
    return credential


# ── List ──────────────────────────────────────────────────────────


@router.get("/", response_model=list[CredentialOut])
async def list_credentials(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("integrations:read")),
):
    """List all non-deleted credentials."""
    result = await db.execute(
        select(Credential).where(~Credential.is_deleted).order_by(Credential.name.asc())
    )
    return [CredentialOut.model_validate(c) for c in result.scalars().all()]


# ── Get ───────────────────────────────────────────────────────────


@router.get("/{credential_id}", response_model=CredentialOut)
async def get_credential(
    credential_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("integrations:read")),
):
    """Get a single credential by ID (secret is never returned)."""
    return CredentialOut.model_validate(await _get_credential_or_404(db, credential_id))


# ── Create ────────────────────────────────────────────────────────


@router.post("/", response_model=CredentialOut, status_code=status.HTTP_201_CREATED)
async def create_credential(
    data: CredentialCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("integrations:write")),
):
    """Create a new credential with encrypted secret storage."""
    encrypted = encrypt_secret(data.secret)
    credential = Credential(
        name=data.name,
        credential_type=data.credential_type,
        provider=data.provider,
        username=data.username,
        encrypted_secret=encrypted,
        ssh_public_key=data.ssh_public_key,
        base_url=data.base_url,
        status_flag=0,
        status_text="OK",
    )
    db.add(credential)
    await db.commit()
    await db.refresh(credential)

    await AuditService.log_event(
        db,
        user_id=current_user.id,
        username=current_user.username,
        action="credential.created",
        resource_type="credential",
        resource_id=credential.id,
        resource_name=credential.name,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    return CredentialOut.model_validate(credential)


# ── Update ────────────────────────────────────────────────────────


@router.patch("/{credential_id}", response_model=CredentialOut)
async def update_credential(
    credential_id: int,
    data: CredentialUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("integrations:write")),
):
    """Partially update a credential (re-encrypts secret if provided)."""
    credential = await _get_credential_or_404(db, credential_id)

    changed = False
    for field_name in (
        "name",
        "credential_type",
        "provider",
        "username",
        "ssh_public_key",
        "base_url",
    ):
        new_value = getattr(data, field_name, None)
        if new_value is not None and getattr(credential, field_name) != new_value:
            setattr(credential, field_name, new_value)
            changed = True

    if data.secret is not None:
        credential.encrypted_secret = encrypt_secret(data.secret)
        changed = True

    if changed:
        await db.commit()
        await db.refresh(credential)

    await AuditService.log_event(
        db,
        user_id=current_user.id,
        username=current_user.username,
        action="credential.updated",
        resource_type="credential",
        resource_id=credential.id,
        resource_name=credential.name,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    return CredentialOut.model_validate(credential)


# ── Delete ────────────────────────────────────────────────────────


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("integrations:write")),
):
    """Soft-delete a credential."""
    credential = await _get_credential_or_404(db, credential_id)
    credential_name = credential.name

    credential.is_deleted = True
    await db.commit()

    await AuditService.log_event(
        db,
        user_id=current_user.id,
        username=current_user.username,
        action="credential.deleted",
        resource_type="credential",
        resource_id=credential_id,
        resource_name=credential_name,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()


# ── Test ──────────────────────────────────────────────────────────


@router.post("/{credential_id}/test", response_model=CredentialOut)
async def test_credential(
    credential_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("integrations:write")),
):
    """Mark a credential as tested (updates last_tested_at and logs audit event)."""
    from datetime import UTC, datetime

    credential = await _get_credential_or_404(db, credential_id)
    credential.last_tested_at = datetime.now(UTC)
    credential.status_flag = 0
    credential.status_text = "OK"
    await db.commit()
    await db.refresh(credential)

    await AuditService.log_event(
        db,
        user_id=current_user.id,
        username=current_user.username,
        action="credential.tested",
        resource_type="credential",
        resource_id=credential.id,
        resource_name=credential.name,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    return CredentialOut.model_validate(credential)
