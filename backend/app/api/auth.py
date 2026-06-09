import logging
from datetime import UTC, datetime

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
from app.core.rbac import get_current_user, require_admin
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
    SSOConfig,
    TokenResponse,
    UserOut,
)
from app.schemas.oidc_config import OIDCConfigOut, OIDCConfigPublic, OIDCConfigUpdate
from app.schemas.rbac import UserPermissionsOut
from app.services.audit import AuditService
from app.services.oidc import KeycloakOIDCService
from app.services.oidc_config import OIDCConfigService
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
    Expose the public OIDC parameters needed to bootstrap keycloak-js.

    Reads from the database-backed OIDC config with automatic fallback to
    environment variables when the DB row doesn't exist yet.

    SSO is considered enabled only when a frontend client ID and a public URL
    are configured, so the frontend can hide the button in pure-local deployments.
    """
    service = OIDCConfigService(db)
    config = await service.get_active_config_cached()

    return SSOConfig(
        enabled=config.enabled,
        url=config.public_url or "",
        realm="bigbug",  # realm is hard-coded; not configurable via DB
        client_id=config.frontend_client_id,
    )


@router.post("/oidc/exchange", response_model=TokenResponse)
async def oidc_exchange(
    request: Request,
    data: OIDCExchangeRequest,
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(rate_limit(settings.rate_limit_oidc_exchange)),
):
    """
    Complete the SSO login: exchange the authorization code at Keycloak,
    validate the returned ID token, provision/update the local user, and issue
    the application's own JWTs (so the rest of the API stays auth-scheme-agnostic).
    """
    service = KeycloakOIDCService(db)
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


# ── Admin OIDC configuration ────────────────────────────────────────


@router.get(
    "/admin/oidc-config",
    response_model=OIDCConfigOut,
    dependencies=[Depends(require_admin())],
)
async def get_oidc_config(db: AsyncSession = Depends(get_db)):
    """
    Return the full OIDC configuration (admin only).

    Returns a disabled default when SSO hasn't been configured yet.
    ``client_secret`` is masked — the real encrypted value is never
    returned via the API.
    """
    service = OIDCConfigService(db)
    config = await service.get_config()
    if config is None:
        # No DB row yet — return a placeholder so the admin UI can render.
        now = datetime.now(tz=UTC)
        return OIDCConfigOut(
            id=0,
            issuer_url="",
            client_id="",
            client_secret="********",
            frontend_client_id="",
            enabled=False,
            public_url=None,
            role_mapping={},
            created_at=now,
            updated_at=now,
        )
    return config


@router.patch(
    "/admin/oidc-config",
    response_model=OIDCConfigOut,
    dependencies=[Depends(require_admin())],
)
async def update_oidc_config(
    data: OIDCConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update the OIDC configuration (admin only).

    ``client_secret`` is encrypted at rest via Fernet.  Updating any field
    immediately invalidates the process-wide cache so the OIDC service
    picks up the new values on the next request.
    """
    service = OIDCConfigService(db)
    config = await service.update_config(
        issuer_url=data.issuer_url,
        client_id=data.client_id,
        client_secret=data.client_secret,
        frontend_client_id=data.frontend_client_id,
        enabled=data.enabled,
        public_url=data.public_url,
        role_mapping=data.role_mapping,
    )
    return config


@router.get(
    "/admin/oidc-config/public",
    response_model=OIDCConfigPublic,
    dependencies=[Depends(require_admin())],
)
async def get_oidc_config_public(db: AsyncSession = Depends(get_db)):
    """Return the OIDC config subset for admin UI previews (no secret)."""
    service = OIDCConfigService(db)
    config = await service.get_config()
    if config is None:
        return OIDCConfigPublic(
            enabled=False,
            issuer_url="",
            frontend_client_id="",
            public_url=None,
        )
    return config
