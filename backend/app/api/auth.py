import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.role import Role, UserRole
from app.core.security import verify_password, create_access_token, create_refresh_token, decode_token
from app.core.rbac import get_current_user
from app.core.exceptions import OIDCExchangeError, OIDCInvalidTokenError, OIDCProvisioningError
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    RefreshRequest,
    UserOut,
    OIDCExchangeRequest,
    SSOConfig,
)
from app.services.oidc import KeycloakOIDCService

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

    token_data = {"sub": str(user.id), "username": user.username}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(data.refresh_token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not a refresh token")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    token_data = {"sub": str(user.id), "username": user.username}
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

    token_data = {"sub": str(user.id), "username": user.username}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )
