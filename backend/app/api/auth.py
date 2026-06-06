import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import (
    OIDCExchangeError,
    OIDCInvalidTokenError,
    OIDCProvisioningError,
)
from app.core.rbac import get_current_user
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
from app.schemas.rbac import UserPermissionsOut
from app.services.oidc import KeycloakOIDCService
from app.services.rbac_service import RBACService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
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
        )

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
async def sso_config():
    """
    Expose the public OIDC parameters needed to bootstrap keycloak-js.

    SSO is considered enabled only when a frontend client ID and a public URL
    are configured, so the frontend can hide the button in pure-local deployments.

    WHY keycloak_public_url: Backend uses internal Docker hostname for
    server-to-server communication, but browser needs publicly accessible URL.
    """
    return SSOConfig(
        enabled=bool(settings.keycloak_frontend_client_id and settings.keycloak_public_url),
        url=settings.keycloak_public_url,
        realm=settings.keycloak_realm,
        client_id=settings.keycloak_frontend_client_id,
    )


@router.post("/oidc/exchange", response_model=TokenResponse)
async def oidc_exchange(data: OIDCExchangeRequest, db: AsyncSession = Depends(get_db)):
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
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except OIDCInvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    except OIDCProvisioningError as exc:
        logger.error("oidc_provisioning_failed", extra={"error": str(exc)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

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
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )
