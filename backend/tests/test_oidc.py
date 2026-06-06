"""
@file test_oidc.py
@description Unit tests for KeycloakOIDCService — exchange_code, validate_id_token,
             provision_or_update_user, and role synchronisation.
"""

import time
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwk as jose_jwk
from jose import jwt as jose_jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import OIDCExchangeError, OIDCInvalidTokenError
from app.core.rbac import RoleName
from app.models.role import Role, UserRole
from app.models.user import User
from app.services.oidc import (
    KeycloakOIDCService,
    OIDCClaims,
    _JWKSCache,
)

# ─── helpers ────────────────────────────────────────────────────────────────


def _build_rsa_keypair() -> tuple[str, str]:
    """Return (private_pem, public_pem) for an ephemeral RS256 key."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    public_pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii")
    )
    return private_pem, public_pem


def _build_jwks(public_pem: str) -> dict:
    """Convert a PEM public key into a JWKS dict with one key."""
    key = jose_jwk.construct(public_pem, "RS256")
    jwk_dict = key.to_dict()
    jwk_dict["kid"] = "test-key-001"
    return {"keys": [jwk_dict]}


def _sign_id_token(
    private_pem: str,
    claims: dict | None = None,
    *,
    expired: bool = False,
) -> str:
    """Create a (valid or expired) RS256-signed ID token."""
    now = int(time.time())
    payload: dict = {
        "iss": "http://localhost:8180/realms/bigbug",
        "aud": "bigbug-backend",
        "sub": "kc-user-001",
        "preferred_username": "sso_user",
        "email": "sso_user@example.com",
        "realm_access": {"roles": ["admin", "viewer"]},
        "iat": now,
        "exp": now - 3600 if expired else now + 3600,
        **(claims or {}),
    }
    headers = {"kid": "test-key-001"}
    return jose_jwt.encode(payload, private_pem, algorithm="RS256", headers=headers)


def _make_mock_httpx_client(**kwargs) -> MagicMock:
    """Create a mock httpx.AsyncClient whose methods return AsyncMock."""
    mock = MagicMock(spec=httpx.AsyncClient)
    for method in ("get", "post", "head", "request"):
        setattr(mock, method, AsyncMock(**kwargs))
    return mock


# ─── fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def rsa_keys() -> tuple[str, str]:
    return _build_rsa_keypair()


@pytest.fixture
def mock_http_client() -> MagicMock:
    return _make_mock_httpx_client()


@pytest_asyncio.fixture
async def seeded_roles(db_session: AsyncSession):
    """Ensure admin, operator, viewer roles exist in the test DB.

    Uses a simple upsert strategy to coexist with conftest fixtures that may
    have already created the same roles in a shared session.
    """
    from sqlalchemy import text as sa_text

    roles = {}
    for name in RoleName:
        # Use INSERT OR IGNORE so the fixture is safe when called together
        # with admin_user / operator_user (which also seed roles).
        stmt = sa_text(
            "INSERT OR IGNORE INTO roles (name, description, created_at) "
            "VALUES (:name, :desc, datetime('now'))"
        )
        await db_session.execute(stmt, {"name": name.value, "desc": name.value})
        await db_session.flush()
        # Now fetch the role (whether newly inserted or already existed).
        result = await db_session.execute(select(Role).where(Role.name == name.value))
        roles[name.value] = result.scalar_one()
    await db_session.commit()
    return roles


# ─── _JWKSCache ─────────────────────────────────────────────────────────────


class TestJWKSCache:
    def test_cache_miss_when_empty(self):
        cache = _JWKSCache(ttl_seconds=60)
        assert cache.get() is None

    def test_cache_hit(self):
        cache = _JWKSCache(ttl_seconds=60)
        keys = {"keys": [{"kty": "RSA"}]}
        cache.set(keys)
        assert cache.get() is keys

    def test_cache_expired_after_ttl(self):
        cache = _JWKSCache(ttl_seconds=0)
        cache.set({"keys": [{"kty": "RSA"}]})
        time.sleep(0.001)
        assert cache.get() is None

    def test_clear(self):
        cache = _JWKSCache(ttl_seconds=60)
        cache.set({"keys": [{"kty": "RSA"}]})
        cache.clear()
        assert cache.get() is None


# ─── exchange_code ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_exchange_code_success(db_session, mock_http_client):
    """Successful authorization-code exchange returns token set."""
    token_response = {
        "access_token": "at-abc",
        "id_token": "id-xyz",
        "refresh_token": "rt-123",
        "expires_in": 300,
        "token_type": "Bearer",
    }
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = token_response
    mock_http_client.post.return_value = mock_response

    service = KeycloakOIDCService(db_session, http_client=mock_http_client)
    result = await service.exchange_code("code-42", "http://localhost/cb", "vrfy")

    assert result == token_response
    mock_http_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_exchange_code_invalid(db_session, mock_http_client):
    """A non-200 response from Keycloak raises OIDCExchangeError."""
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = '{"error":"invalid_grant"}'
    mock_http_client.post.return_value = mock_response

    service = KeycloakOIDCService(db_session, http_client=mock_http_client)
    with pytest.raises(OIDCExchangeError, match="rejected"):
        await service.exchange_code("bad-code", "http://localhost/cb", "vrfy")


@pytest.mark.asyncio
async def test_exchange_code_network_error(db_session, mock_http_client):
    """Network errors are wrapped in OIDCExchangeError."""
    mock_http_client.post.side_effect = httpx.ConnectError("no route to host")

    service = KeycloakOIDCService(db_session, http_client=mock_http_client)
    with pytest.raises(OIDCExchangeError, match="identity provider"):
        await service.exchange_code("code-1", "http://localhost/cb", "vrfy")


# ─── validate_id_token ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_validate_id_token_success(
    db_session, rsa_keys, mock_http_client, monkeypatch
):
    """A properly signed ID token with valid claims passes validation."""
    private_pem, public_pem = rsa_keys
    id_token = _sign_id_token(private_pem)
    jwks = _build_jwks(public_pem)

    # Pre-load the cache so no HTTP call to Keycloak is needed.
    jwks_cache = _JWKSCache(ttl_seconds=600)
    jwks_cache.set(jwks)

    service = KeycloakOIDCService(
        db_session, http_client=mock_http_client, jwks_cache=jwks_cache
    )
    claims = await service.validate_id_token(id_token)

    assert claims.subject == "kc-user-001"
    assert claims.username == "sso_user"
    assert claims.email == "sso_user@example.com"
    assert claims.roles == frozenset({"admin", "viewer"})


@pytest.mark.asyncio
async def test_validate_id_token_expired(db_session, rsa_keys, mock_http_client):
    """An expired ID token raises OIDCInvalidTokenError."""
    private_pem, public_pem = rsa_keys
    id_token = _sign_id_token(private_pem, expired=True)
    jwks = _build_jwks(public_pem)

    jwks_cache = _JWKSCache(ttl_seconds=600)
    jwks_cache.set(jwks)

    service = KeycloakOIDCService(
        db_session, http_client=mock_http_client, jwks_cache=jwks_cache
    )
    with pytest.raises(OIDCInvalidTokenError, match="validation failed"):
        await service.validate_id_token(id_token)


@pytest.mark.asyncio
async def test_validate_id_token_bad_signature(db_session, rsa_keys, mock_http_client):
    """Token signed with a different key must be rejected."""
    _, public_pem = rsa_keys
    wrong_priv, _ = _build_rsa_keypair()
    id_token = _sign_id_token(wrong_priv)
    jwks = _build_jwks(public_pem)

    jwks_cache = _JWKSCache(ttl_seconds=600)
    jwks_cache.set(jwks)

    service = KeycloakOIDCService(
        db_session, http_client=mock_http_client, jwks_cache=jwks_cache
    )
    with pytest.raises(OIDCInvalidTokenError):
        await service.validate_id_token(id_token)


# ─── provision_or_update_user ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_provision_or_update_user_new(db_session, mock_http_client, seeded_roles):
    """A new SSO user is created with the correct claims and roles."""
    claims = OIDCClaims(
        subject="kc-new-user",
        username="new_user",
        email="new_user@example.com",
        roles=frozenset({"operator", "viewer"}),
    )
    service = KeycloakOIDCService(db_session, http_client=mock_http_client)
    user = await service.provision_or_update_user(claims)

    assert user.id is not None
    assert user.username == "new_user"
    assert user.keycloak_sub == "kc-new-user"
    assert user.hashed_password is None  # SSO-only
    assert user.is_active is True

    # Re-query with eager-load to avoid MissingGreenlet on lazy relationships
    from sqlalchemy.orm import selectinload

    result = await db_session.execute(
        select(User).options(selectinload(User.user_roles)).where(User.id == user.id)
    )
    user = result.scalar_one()
    role_names = {r.name for r in user.roles}
    assert role_names == {"operator", "viewer"}


@pytest.mark.asyncio
async def test_provision_or_update_user_existing(
    db_session, mock_http_client, seeded_roles
):
    """An existing SSO user is updated instead of duplicated."""
    # Pre-create the user
    user = User(
        username="existing",
        email="existing@example.com",
        keycloak_sub="kc-existing",
        hashed_password=None,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    # Assign initial role
    db_session.add(UserRole(user_id=user.id, role_id=seeded_roles["viewer"].id))
    await db_session.commit()

    claims = OIDCClaims(
        subject="kc-existing",
        username="existing_updated",
        email="updated@example.com",
        roles=frozenset({"admin"}),
    )
    service = KeycloakOIDCService(db_session, http_client=mock_http_client)
    updated = await service.provision_or_update_user(claims)

    assert updated.id == user.id
    assert updated.email == "updated@example.com"

    # Re-query with eager-load to avoid MissingGreenlet on lazy relationships
    from sqlalchemy.orm import selectinload

    result = await db_session.execute(
        select(User).options(selectinload(User.user_roles)).where(User.id == updated.id)
    )
    updated = result.scalar_one()
    assert {r.name for r in updated.roles} == {"admin"}


@pytest.mark.asyncio
async def test_provision_or_update_user_find_by_email(
    db_session, mock_http_client, seeded_roles
):
    """If no Keycloak sub matches, the user is found by email."""
    user = User(
        username="email_user",
        email="link-me@example.com",
        hashed_password=None,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    claims = OIDCClaims(
        subject="kc-new-sub-link",
        username="email_user",
        email="link-me@example.com",
        roles=frozenset({"viewer"}),
    )
    service = KeycloakOIDCService(db_session, http_client=mock_http_client)
    linked = await service.provision_or_update_user(claims)

    assert linked.id == user.id
    assert linked.keycloak_sub == "kc-new-sub-link"


# ─── sync_roles ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sync_roles_add_and_remove(db_session, mock_http_client, seeded_roles):
    """_sync_roles adds new roles and removes revoked ones."""
    user = User(
        username="roles_test",
        email="roles@example.com",
        hashed_password=None,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    # Pre-assign admin role
    db_session.add(UserRole(user_id=user.id, role_id=seeded_roles["admin"].id))
    await db_session.commit()

    service = KeycloakOIDCService(db_session, http_client=mock_http_client)
    # Desired: only operator (admin should be removed, operator added)
    await service._sync_roles(user, frozenset({"operator"}))
    await db_session.flush()

    # Re-query with eager-load to avoid MissingGreenlet on lazy relationships
    await db_session.refresh(user, ["user_roles"])
    role_names = {r.name for r in user.roles}
    assert role_names == {"operator"}


@pytest.mark.asyncio
async def test_sync_roles_unknown_ignored(db_session, mock_http_client, seeded_roles):
    """Roles not present in the DB are silently ignored."""
    user = User(
        username="unknown_role_test",
        email="unknown@example.com",
        hashed_password=None,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    service = KeycloakOIDCService(db_session, http_client=mock_http_client)
    await service._sync_roles(user, frozenset({"viewer", "super-admin"}))
    await db_session.flush()

    await db_session.refresh(user, ["user_roles"])
    role_names = {r.name for r in user.roles}
    assert role_names == {"viewer"}


@pytest.mark.asyncio
async def test_sync_roles_none(db_session, mock_http_client, seeded_roles):
    """An empty desired_roles set clears all role assignments."""
    user = User(
        username="clear_roles",
        email="clear@example.com",
        hashed_password=None,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=seeded_roles["viewer"].id))
    await db_session.commit()

    service = KeycloakOIDCService(db_session, http_client=mock_http_client)
    await service._sync_roles(user, frozenset())
    await db_session.flush()

    await db_session.refresh(user, ["user_roles"])
    assert len(user.roles) == 0


# ─── _extract_claims ────────────────────────────────────────────────────────


class TestExtractClaims:
    def test_normal_payload(self):
        claims = KeycloakOIDCService._extract_claims(
            {
                "sub": "abc",
                "preferred_username": "john",
                "email": "john@example.com",
                "realm_access": {"roles": ["admin", "operator"]},
            }
        )
        assert claims.subject == "abc"
        assert claims.username == "john"
        assert claims.email == "john@example.com"
        assert claims.roles == frozenset({"admin", "operator"})

    def test_no_preferred_username_falls_back_to_email(self):
        claims = KeycloakOIDCService._extract_claims(
            {
                "sub": "abc",
                "email": "john@example.com",
                "realm_access": {"roles": []},
            }
        )
        assert claims.username == "john"

    def test_unknown_roles_filtered(self):
        claims = KeycloakOIDCService._extract_claims(
            {
                "sub": "abc",
                "preferred_username": "jane",
                "email": "jane@example.com",
                "realm_access": {"roles": ["admin", "custom-app-role"]},
            }
        )
        assert claims.roles == frozenset({"admin"})
