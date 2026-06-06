"""
@file oidc.py
@description Keycloak OIDC service implementing the Authorization Code + PKCE
             flow used by the frontend SSO button. Responsibilities:
               * exchange an authorization code for tokens at Keycloak
               * fetch and cache the realm JWKS (with a TTL)
               * validate the ID token signature, issuer, audience and expiry
               * extract normalized claims from a validated token
               * provision-or-update the matching local user (hybrid auth) and
                 sync roles from realm_access.roles -> admin/operator/viewer

@dependencies httpx (async HTTP), python-jose[cryptography] (JWT/JWKS),
              SQLAlchemy async session
@relatedFiles app/api/auth.py (HTTP layer), app/core/rbac.py (RoleName),
              app/core/exceptions.py (OIDC* exceptions)

The class is deliberately framework-agnostic: it raises domain exceptions
(OIDC*) instead of HTTPException so it can be unit-tested without FastAPI and
reused outside the request lifecycle.
"""

from __future__ import annotations

import logging
import time
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass

import httpx
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import (
    OIDCExchangeError,
    OIDCInvalidTokenError,
    OIDCProvisioningError,
)
from app.core.rbac import RoleName
from app.models.role import Role, UserRole
from app.models.user import User

logger = logging.getLogger(__name__)

# Roles we understand locally. Any Keycloak realm role outside this set is
# ignored when syncing — the local RBAC model only knows these three.
_KNOWN_ROLES: frozenset[str] = frozenset(r.value for r in RoleName)


@dataclass(frozen=True)
class OIDCClaims:
    """Normalized subset of ID-token claims the application cares about."""

    subject: str
    username: str
    email: str
    roles: frozenset[str]


class _JWKSCache:
    """
    Tiny in-memory TTL cache for a realm's JSON Web Key Set.

    Split into its own class so the caching policy (and key rotation window) is
    testable in isolation and the service stays focused on the OIDC flow.
    """

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._keys: dict | None = None
        self._fetched_at: float = 0.0

    def get(self) -> dict | None:
        # WHY: treat the cache as a miss once the TTL elapses so rotated signing
        # keys are picked up without a process restart.
        if self._keys is None:
            return None
        if (time.monotonic() - self._fetched_at) > self._ttl:
            return None
        return self._keys

    def set(self, keys: dict) -> None:
        self._keys = keys
        self._fetched_at = time.monotonic()

    def clear(self) -> None:
        self._keys = None
        self._fetched_at = 0.0


class KeycloakOIDCService:
    """
    Orchestrates the server-side half of the SSO login.

    A single instance is cheap to build per request; the JWKS cache is shared at
    module level via :data:`_jwks_cache` so token validations across requests
    reuse the fetched keys.
    """

    def __init__(
        self,
        db: AsyncSession,
        *,
        http_client: httpx.AsyncClient | None = None,
        jwks_cache: _JWKSCache | None = None,
    ) -> None:
        self._db = db
        # Allow injecting a client/cache in tests; default to module singletons.
        self._http_client = http_client
        self._jwks_cache = jwks_cache or _jwks_cache

    # --- public API -----------------------------------------------------------

    async def exchange_code(
        self, code: str, redirect_uri: str, code_verifier: str
    ) -> dict:
        """
        Exchange an authorization code for a token set at Keycloak's token
        endpoint using PKCE.

        Raises:
            OIDCExchangeError: on network failure or a non-2xx token response.
        """
        # IMPORTANT: The authorization code was issued to the frontend
        # (public) client, so the exchange must use the same client_id and
        # NEVER include a client_secret — public clients rely on PKCE alone.
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
            "client_id": settings.keycloak_frontend_client_id,
        }

        try:
            async with self._client() as client:
                response = await client.post(settings.keycloak_token_url, data=data)
        except httpx.HTTPError as exc:
            logger.warning(
                "oidc_token_exchange_network_error", extra={"error": str(exc)}
            )
            raise OIDCExchangeError("Could not reach the identity provider") from exc

        if response.status_code != httpx.codes.OK:
            # Keycloak returns error/error_description in the body; log it but do
            # not leak provider internals to the caller.
            logger.warning(
                "oidc_token_exchange_rejected",
                extra={
                    "status_code": response.status_code,
                    "body": response.text[:500],
                },
            )
            raise OIDCExchangeError("Authorization code exchange was rejected")

        return response.json()

    async def validate_id_token(self, id_token: str) -> OIDCClaims:
        """
        Validate ``id_token`` against the realm JWKS and return its claims.

        Raises:
            OIDCInvalidTokenError: on any signature/issuer/audience/expiry error.
        """
        jwks = await self._get_jwks()
        try:
            # Decode WITHOUT issuer/audience first to inspect the token and
            # produce a helpful log message that pinpoints the exact mismatch.
            unverified = jwt.get_unverified_claims(id_token)
            expected_iss = self._issuer()
            token_iss = unverified.get("iss", "")
            token_aud = unverified.get("aud", "")
            logger.debug(
                "oidc_id_token_pre_validate",
                extra={
                    "token_iss": token_iss,
                    "expected_iss": expected_iss,
                    "token_aud": token_aud,
                    "expected_aud": settings.keycloak_frontend_client_id,
                },
            )
        except JWTError:
            pass  # Can't even decode the header; let jwt.decode report it.

        try:
            payload = jwt.decode(
                id_token,
                jwks,
                # Keycloak signs tokens with RS256 by default.
                algorithms=["RS256"],
                audience=settings.keycloak_frontend_client_id,
                issuer=self._issuer(),
                # WHY: at_hash links the ID token to an access token we don't
                # validate here, so skip that specific check to avoid spurious
                # failures while keeping signature/exp/aud/iss enforcement.
                options={"verify_at_hash": False},
            )
        except JWTError as exc:
            logger.warning(
                "oidc_id_token_invalid",
                extra={
                    "error": str(exc),
                    "token_iss": token_iss,
                    "expected_iss": expected_iss,
                    "token_aud": token_aud,
                    "expected_aud": settings.keycloak_frontend_client_id,
                },
            )
            raise OIDCInvalidTokenError("ID token validation failed") from exc

        return self._extract_claims(payload)

    async def provision_or_update_user(self, claims: OIDCClaims) -> User:
        """
        Find or create the local user for ``claims`` and sync roles.

        Hybrid auth: SSO users live in the same ``users`` table as local users
        but are keyed by ``keycloak_sub`` and have a null password.

        Raises:
            OIDCProvisioningError: if the resulting user has no usable identity.
        """
        if not claims.subject:
            raise OIDCProvisioningError("Token is missing the subject (sub) claim")

        user = await self._find_user(claims)
        if user is None:
            user = await self._create_user(claims)
            logger.info("oidc_user_created", extra={"username": user.username})
        else:
            self._update_user(user, claims)

        await self._sync_roles(user, claims.roles)
        await self._db.flush()
        # Refresh role relationship so callers see the freshly synced roles.
        await self._db.refresh(user)
        return user

    # --- internals ------------------------------------------------------------

    def _client(self) -> AbstractAsyncContextManager[httpx.AsyncClient]:
        # Reuse an injected client (tests) or build a short-lived one with a
        # bounded timeout so a slow IDP can't pin a worker indefinitely.
        if self._http_client is not None:
            return _NonClosingClient(self._http_client)
        return httpx.AsyncClient(timeout=settings.keycloak_http_timeout_seconds)

    async def _get_jwks(self) -> dict:
        cached = self._jwks_cache.get()
        if cached is not None:
            return cached
        try:
            async with self._client() as client:
                response = await client.get(settings.keycloak_jwks_url)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("oidc_jwks_fetch_failed", extra={"error": str(exc)})
            raise OIDCInvalidTokenError("Could not load signing keys") from exc
        keys = response.json()
        self._jwks_cache.set(keys)
        return keys

    @staticmethod
    def _issuer() -> str:
        # IMPORTANT: Keycloak with KC_HOSTNAME_STRICT=false determines the iss
        # claim from the Host header of the initiating request. The browser
        # connects via the public URL, so the token carries the public issuer.
        # We must validate against the same issuer.
        return f"{settings.keycloak_public_url}/realms/{settings.keycloak_realm}"

    @staticmethod
    def _extract_claims(payload: dict) -> OIDCClaims:
        subject = payload.get("sub", "")
        # preferred_username is Keycloak's canonical login name; fall back to
        # email local-part so we always have a non-empty username.
        email = payload.get("email", "") or ""
        username = payload.get("preferred_username") or (
            email.split("@")[0] if email else subject
        )
        realm_roles = payload.get("realm_access", {}).get("roles", []) or []
        roles = frozenset(r for r in realm_roles if r in _KNOWN_ROLES)
        return OIDCClaims(subject=subject, username=username, email=email, roles=roles)

    async def _find_user(self, claims: OIDCClaims) -> User | None:
        # Match on the immutable Keycloak subject first; fall back to email so a
        # pre-existing local account is linked to SSO instead of duplicated.
        result = await self._db.execute(
            select(User).where(User.keycloak_sub == claims.subject)
        )
        user = result.scalar_one_or_none()
        if user is not None:
            return user
        if claims.email:
            result = await self._db.execute(
                select(User).where(User.email == claims.email)
            )
            return result.scalar_one_or_none()
        return None

    async def _create_user(self, claims: OIDCClaims) -> User:
        user = User(
            username=claims.username,
            email=claims.email or f"{claims.subject}@sso.local",
            hashed_password=None,  # SSO-only account
            keycloak_sub=claims.subject,
            is_active=True,
        )
        self._db.add(user)
        await self._db.flush()  # assign PK before role rows reference it
        return user

    def _update_user(self, user: User, claims: OIDCClaims) -> None:
        # Keep the local record aligned with the IDP as the source of truth for
        # SSO-managed attributes, while preserving any existing password.
        # NOTE: ``# type: ignore`` follows the project convention for SQLAlchemy
        # Declarative columns, whose descriptors confuse static type checkers on
        # instance assignment but resolve to plain values at runtime.
        if user.keycloak_sub is None:  # type: ignore[comparison-overlap]
            user.keycloak_sub = claims.subject  # type: ignore[assignment]
        if claims.email:
            user.email = claims.email  # type: ignore[assignment]
        if claims.username:
            user.username = claims.username  # type: ignore[assignment]

    async def _sync_roles(self, user: User, desired_roles: frozenset[str]) -> None:
        """Make the user's role assignments match ``desired_roles`` exactly."""
        if desired_roles:
            result = await self._db.execute(
                select(Role).where(Role.name.in_(desired_roles))
            )
            role_by_name = {role.name: role for role in result.scalars().all()}
        else:
            # No recognised IDP roles -> user ends up with no assignments.
            role_by_name = {}

        # Map any roles that exist in Keycloak but were never seeded locally:
        # we simply skip them (the init script seeds admin/operator/viewer).
        current = await self._db.execute(
            select(UserRole).where(UserRole.user_id == user.id)
        )
        current_assignments = {ur.role_id: ur for ur in current.scalars().all()}
        desired_role_ids = {role.id for role in role_by_name.values()}

        # Remove assignments no longer granted by the IDP.
        for role_id, assignment in current_assignments.items():
            if role_id not in desired_role_ids:
                await self._db.delete(assignment)

        # Add newly granted assignments.
        for role_id in desired_role_ids - current_assignments.keys():
            self._db.add(UserRole(user_id=user.id, role_id=role_id))


class _NonClosingClient:
    """
    Async-context wrapper that yields an injected client without closing it.

    Lets :meth:`KeycloakOIDCService._client` use ``async with`` uniformly for
    both owned (short-lived) and injected (test) clients.
    """

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def __aenter__(self) -> httpx.AsyncClient:
        return self._client

    async def __aexit__(self, *_exc) -> None:
        return None


# Process-wide JWKS cache shared across requests; TTL from settings.
_jwks_cache = _JWKSCache(ttl_seconds=settings.keycloak_jwks_cache_ttl_seconds)
