"""
@file providers.py
@description REST API for the unified Providers V3 entity (``resource_providers``).
             Runs in parallel with the legacy ``/api/integrations`` and
             ``/api/mirroring`` providers endpoints during the migration.
             Maps :class:`app.core.exceptions.DomainError` raised by
             :class:`app.services.providers.service.ProviderService` to HTTP
             status codes, keeping transport concerns out of the service layer.
@dependencies app.core.rbac, app.schemas.provider, app.services.providers.service
@relatedFiles ../models/resource_provider.py, ../schemas/provider.py,
             ../services/providers/service.py
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.core.rbac import get_current_user, require_permission, require_scope_permission
from app.database import get_db
from app.models.resource_provider import (
    ProviderCapability,
    ProviderCategory,
    ProviderDirection,
    ProviderDomain,
    ProviderSubtype,
    ResourceProvider,
)
from app.models.user import User
from app.schemas.provider import (
    ProviderActionIn,
    ProviderActionOut,
    ProviderCreate,
    ProviderOut,
    ProviderShareIn,
    ProviderTestResult,
    ProviderTypeOut,
    ProviderUpdate,
)
from app.services.providers.registry import all_types
from app.services.providers.service import ProviderService

router = APIRouter()


# ──── Helpers ──────────────────────────────────────────────────────────────


def _translate(exc: DomainError) -> HTTPException:
    """Map a domain-layer error to the HTTP response it declares."""
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


async def _user_permissions(user: User, db: AsyncSession) -> set[str]:
    """Resolve the caller's permission names (JWT cache first, DB fallback)."""
    cached = getattr(user, "_cached_permissions", [])
    if cached:
        return set(cached)
    from app.services.rbac_service import RBACService

    return set(await RBACService(db).get_user_permissions(user.id))


def _require_permission(perms: set[str], permission: str) -> None:
    if permission not in perms:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: '{permission}' required",
        )


def _is_system_visible(provider: ResourceProvider | None, perms: set[str]) -> bool:
    """System providers are hidden from non-privileged users (12.2.1)."""
    if provider is not None and provider.category != ProviderCategory.system:
        return True
    return "providers_system:write" in perms or "providers:read_all" in perms


# ──── Types metadata ───────────────────────────────────────────────────────


@router.get("/types", response_model=list[ProviderTypeOut])
async def get_provider_types(
    _: User = Depends(get_current_user),
):
    """Registry metadata for all subtypes (form generation on the frontend)."""
    return [ProviderTypeOut(**item) for item in all_types()]


# ──── List ─────────────────────────────────────────────────────────────────


@router.get("", response_model=list[ProviderOut])
async def list_providers(
    domain: ProviderDomain | None = None,
    subtype: ProviderSubtype | None = None,
    category: ProviderCategory | None = None,
    direction: ProviderDirection | None = None,
    owner: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("providers:read")),
):
    """List providers with filters. Private providers are scoped to their owner
    (or everyone when ``providers:read_all`` is held); system rows are visible
    only to ``providers_system:write`` or an explicit ``category=system`` query
    with ``providers:read_all``."""
    service = ProviderService(db)
    providers = await service.list_providers(current_user)
    perms = await _user_permissions(current_user, db)

    show_system = "providers_system:write" in perms or (
        category == ProviderCategory.system and "providers:read_all" in perms
    )

    result: list[ResourceProvider] = []
    for provider in providers:
        if provider.category == ProviderCategory.system and not show_system:
            continue
        if domain is not None and provider.domain != domain:
            continue
        if subtype is not None and provider.subtype != subtype:
            continue
        if category is not None and provider.category != category:
            continue
        if direction is not None and provider.direction != direction:
            continue
        if owner == "me" and provider.owner_user_id != current_user.id:
            continue
        result.append(provider)

    return [ProviderOut.model_validate(p) for p in result]


# ──── Detail ───────────────────────────────────────────────────────────────


@router.get("/{provider_id}", response_model=ProviderOut)
async def get_provider(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("providers:read")),
):
    service = ProviderService(db)
    try:
        provider = await service.get_provider(provider_id, current_user)
    except DomainError as exc:
        raise _translate(exc) from exc

    perms = await _user_permissions(current_user, db)
    if not _is_system_visible(provider, perms):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found",
        )

    return ProviderOut.model_validate(provider)


# ──── Create ───────────────────────────────────────────────────────────────


@router.post("", response_model=ProviderOut, status_code=status.HTTP_201_CREATED)
async def create_provider(
    data: ProviderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    perms = await _user_permissions(current_user, db)
    required = (
        "providers_system:write" if data.category == ProviderCategory.system else "providers:write"
    )
    _require_permission(perms, required)

    service = ProviderService(db)
    try:
        provider = await service.create_provider(
            domain=data.domain,
            subtype=data.subtype,
            category=data.category,
            direction=data.direction,
            name=data.name,
            label=data.label,
            user=current_user,
            description=data.description,
            base_url=data.base_url,
            config=data.config,
            credential_id=data.credential_id,
            visibility=data.visibility,
            team_id=data.team_id,
        )
    except DomainError as exc:
        raise _translate(exc) from exc

    return ProviderOut.model_validate(provider)


# ──── Update ───────────────────────────────────────────────────────────────


@router.patch("/{provider_id}", response_model=ProviderOut)
async def update_provider(
    provider_id: int,
    data: ProviderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ProviderService(db)
    try:
        existing = await service.get_provider(provider_id, current_user)
    except DomainError as exc:
        raise _translate(exc) from exc

    perms = await _user_permissions(current_user, db)
    required = (
        "providers_system:write"
        if existing.category == ProviderCategory.system
        else "providers:write"
    )
    _require_permission(perms, required)

    try:
        provider = await service.update_provider(
            provider_id,
            current_user,
            category=data.category,
            direction=data.direction,
            label=data.label,
            description=data.description,
            base_url=data.base_url,
            config=data.config,
            credential_id=data.credential_id,
            is_active=data.is_active,
            is_default=data.is_default,
            verify_ssl=data.verify_ssl,
            priority=data.priority,
            visibility=data.visibility,
            team_id=data.team_id,
        )
    except DomainError as exc:
        raise _translate(exc) from exc

    return ProviderOut.model_validate(provider)


# ──── Share / Unshare ──────────────────────────────────────────────────────


@router.post("/{provider_id}/share", response_model=ProviderOut)
async def share_provider(
    provider_id: int,
    data: ProviderShareIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Share a private provider with a team (12.3)."""
    service = ProviderService(db)
    try:
        provider = await service.share_provider(provider_id, data.team_id, current_user)
    except DomainError as exc:
        raise _translate(exc) from exc

    return ProviderOut.model_validate(provider)


@router.post("/{provider_id}/unshare", response_model=ProviderOut)
async def unshare_provider(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revert a provider to owner visibility (12.3)."""
    service = ProviderService(db)
    try:
        provider = await service.unshare_provider(provider_id, current_user)
    except DomainError as exc:
        raise _translate(exc) from exc

    return ProviderOut.model_validate(provider)


# ──── Delete ───────────────────────────────────────────────────────────────


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ProviderService(db)
    try:
        existing = await service.get_provider(provider_id, current_user)
    except DomainError as exc:
        raise _translate(exc) from exc

    perms = await _user_permissions(current_user, db)
    required = (
        "providers_system:write"
        if existing.category == ProviderCategory.system
        else "providers:delete"
    )
    _require_permission(perms, required)

    try:
        await service.delete_provider(provider_id, current_user)
    except DomainError as exc:
        raise _translate(exc) from exc


# ──── Connection test ──────────────────────────────────────────────────────


@router.post("/{provider_id}/test", response_model=ProviderTestResult)
async def test_provider(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_scope_permission("providers:write", "provider", "provider_id")),
):
    service = ProviderService(db)
    try:
        result = await service.test_connection(provider_id, current_user)
    except DomainError as exc:
        raise _translate(exc) from exc

    return ProviderTestResult(**result)


# ──── Domain actions ───────────────────────────────────────────────────────


@router.post("/{provider_id}/actions/{action}", response_model=ProviderActionOut)
async def run_provider_action(
    provider_id: int,
    action: ProviderCapability,
    data: ProviderActionIn | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_scope_permission("providers:use", "provider", "provider_id")),
):
    service = ProviderService(db)
    try:
        result = await service.dispatch_action(
            provider_id,
            action,
            current_user,
            params=(data.params if data is not None else None),
        )
    except DomainError as exc:
        raise _translate(exc) from exc

    return ProviderActionOut(action=result["action"], items=result["items"])


# ──── Usage ────────────────────────────────────────────────────────────────


@router.get("/{provider_id}/usage")
async def get_provider_usage(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("providers:read")),
):
    service = ProviderService(db)
    try:
        await service.get_provider(provider_id, current_user)
    except DomainError as exc:
        raise _translate(exc) from exc

    usage = await service.get_usage(provider_id)
    return {"provider_id": provider_id, "usage": usage}
