import logging
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import (
    OIDCExchangeError,
    OIDCInvalidTokenError,
    OIDCProvisioningError,
)
from app.core.rate_limit import rate_limit
from app.core.rbac import get_current_user, require_permission
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    OIDCExchangeRequest,
    RefreshRequest,
    TokenResponse,
    UserOut,
)
from app.schemas.oidc_provider import (
    OIDCProviderCreate,
    OIDCProviderOut,
    OIDCProviderUpdate,
    SSOConfig,
    SSOProvider,
)
from app.schemas.rbac import UserPermissionsOut
from app.services.audit import AuditService
from app.services.oidc import KeycloakOIDCService, parse_realm_from_issuer
from app.services.oidc_providers import OIDCProviderService
from app.services.rbac_service import RBACService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(rate_limit(settings.rate_limit_login)),
):
    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

    # Load permissions to include in JWT for RBAC caching
    rbac_service = RBACService(db)
    permissions = await rbac_service.get_user_permissions(user.id)

    token_data = {
        "sub": str(user.id),
        "username": user.username,
        "permissions": permissions,
    }

    # Audit log: login
    await AuditService.log_event(
        db,
        user_id=user.id,
        username=user.username,
        action="login",
        resource_type="auth",
        ip_address=request.client.host if request.client else None,
    )

    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(data.refresh_token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        ) from None

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not a refresh token")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Load fresh permissions to include in JWT for RBAC caching
    rbac_service = RBACService(db)
    permissions = await rbac_service.get_user_permissions(user.id)

    token_data = {
        "sub": str(user.id),
        "username": user.username,
        "permissions": permissions,
    }
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserOut(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        roles=[r.name for r in current_user.roles],
    )


@router.get("/me/permissions", response_model=UserPermissionsOut)
async def get_my_permissions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the current user's permissions."""
    service = RBACService(db)
    permissions = await service.get_user_permissions(current_user.id)

    # Determine primary role name (first role, or "none")
    role_name = current_user.roles[0].name if current_user.roles else "none"

    return UserPermissionsOut(
        user_id=current_user.id,
        role=role_name,
        permissions=permissions,
    )


@router.get("/sso/config", response_model=SSOConfig)
async def sso_config(db: AsyncSession = Depends(get_db)):
    """
    Expose the public OIDC parameters needed to bootstrap the SSO buttons
    (list contract, ADR-0037): one entry per enabled provider.

    ``realm`` and ``url`` are computed by the backend from the full issuer URI
    (RFC 8414) and ``public_url`` per ADR-0036. Providers whose issuer has no
    parsable ``/realms/`` segment are skipped (warning logged); the global
    master-switch turns the whole list off.
    """
    if not settings.sso_enabled:
        return SSOConfig(enabled=False, providers=[])

    service = OIDCProviderService(db)
    providers = await service.get_enabled_providers_cached()

    entries: list[SSOProvider] = []
    for p in providers:
        realm = parse_realm_from_issuer(p.issuer_url)
        if realm is None:
            logger.warning(
                "oidc_issuer_missing_realm_segment",
                extra={"provider_id": p.id, "issuer_url": p.issuer_url},
            )
            continue
        origin = p.public_url or p.issuer_url
        url = urlunsplit(urlsplit(origin)[:2] + ("", "", ""))
        entries.append(
            SSOProvider(
                id=p.id,
                name=p.name,
                url=url,
                realm=realm,
                client_id=p.frontend_client_id,
            )
        )
    return SSOConfig(enabled=bool(entries), providers=entries)


@router.post("/oidc/exchange", response_model=TokenResponse)
async def oidc_exchange(
    request: Request,
    data: OIDCExchangeRequest,
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(rate_limit(settings.rate_limit_oidc_exchange)),
):
    """
    Complete the SSO login: exchange the authorization code at the provider
    identified by ``provider_id``, validate the returned ID token,
    provision/update the local user, and issue the application's own JWTs (so
    the rest of the API stays auth-scheme-agnostic).

    The ``state`` parameter the frontend received back from Keycloak must carry
    the same ``provider_id`` — a mismatch is treated as a CSRF/broken-flow
    error and rejected with 401.
    """
    if data.state_provider_id != data.provider_id:
        logger.warning(
            "oidc_exchange_state_provider_mismatch",
            extra={"provider_id": data.provider_id, "state": data.state},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OIDC state does not match the selected provider",
        )

    service = KeycloakOIDCService(db, provider_id=data.provider_id)
    try:
        tokens = await service.exchange_code(
            code=data.code,
            redirect_uri=data.redirect_uri,
            code_verifier=data.code_verifier,
        )
        id_token = tokens.get("id_token")
        if not id_token:
            raise OIDCInvalidTokenError("Token response did not include an id_token")

        claims = await service.validate_id_token(id_token)
        user = await service.provision_or_update_user(claims)
    except OIDCExchangeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except OIDCInvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except OIDCProvisioningError as exc:
        logger.error("oidc_provisioning_failed", extra={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

    # Load permissions to include in JWT for RBAC caching
    rbac_service = RBACService(db)
    permissions = await rbac_service.get_user_permissions(user.id)

    token_data = {
        "sub": str(user.id),
        "username": user.username,
        "permissions": permissions,
    }

    # Audit log: SSO login
    await AuditService.log_event(
        db,
        user_id=user.id,
        username=user.username,
        action="login",
        resource_type="auth",
        ip_address=request.client.host if request.client else None,
    )

    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


# ── Admin OIDC providers (multi-provider, ADR-0037) ─────────────────


@router.get(
    "/admin/oidc-providers",
    response_model=list[OIDCProviderOut],
    dependencies=[Depends(require_permission("oidc:read"))],
)
async def list_oidc_providers(db: AsyncSession = Depends(get_db)):
    """
    Return all OIDC providers (admin only), ordered for the SSO button list.

    ``client_secret`` is masked — the real encrypted value is never
    returned via the API.
    """
    service = OIDCProviderService(db)
    return await service.list_providers()


@router.post(
    "/admin/oidc-providers",
    response_model=OIDCProviderOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("oidc:write"))],
)
async def create_oidc_provider(data: OIDCProviderCreate, db: AsyncSession = Depends(get_db)):
    """
    Register a new OIDC provider (admin only).

    ``client_secret`` is encrypted at rest via Fernet.  Creating a provider
    immediately invalidates the process-wide cache so the OIDC service
    picks up the new provider on the next request.
    """
    service = OIDCProviderService(db)
    return await service.create_provider(
        name=data.name,
        issuer_url=data.issuer_url,
        client_id=data.client_id,
        client_secret=data.client_secret,
        frontend_client_id=data.frontend_client_id,
        enabled=data.enabled,
        public_url=data.public_url,
        role_mapping=data.role_mapping,
        sort_order=data.sort_order,
    )


@router.patch(
    "/admin/oidc-providers/{provider_id}",
    response_model=OIDCProviderOut,
    dependencies=[Depends(require_permission("oidc:write"))],
)
async def update_oidc_provider(
    provider_id: int,
    data: OIDCProviderUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update one OIDC provider (admin only, PATCH semantics).

    ``client_secret`` is encrypted at rest via Fernet.  Updating any field
    immediately invalidates the process-wide cache so the OIDC service
    picks up the new values on the next request.
    """
    service = OIDCProviderService(db)
    row = await service.update_provider(
        provider_id,
        name=data.name,
        issuer_url=data.issuer_url,
        client_id=data.client_id,
        client_secret=data.client_secret,
        frontend_client_id=data.frontend_client_id,
        enabled=data.enabled,
        public_url=data.public_url,
        role_mapping=data.role_mapping,
        sort_order=data.sort_order,
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"OIDC provider {provider_id} not found",
        )
    return row


@router.delete(
    "/admin/oidc-providers/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("oidc:write"))],
)
async def delete_oidc_provider(provider_id: int, db: AsyncSession = Depends(get_db)):
    """Delete one OIDC provider (admin only)."""
    service = OIDCProviderService(db)
    if not await service.delete_provider(provider_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"OIDC provider {provider_id} not found",
        )
