"""
@file test_oidc.py
@description Unit tests for KeycloakOIDCService — exchange_code, validate_id_token,
             provision_or_update_user, and role synchronisation.
"""

import logging
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
    parse_realm_from_issuer,
)
from app.services.oidc_providers import CachedOIDCProvider

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


def _public_pem(private_pem: str) -> str:
    """Derive the public PEM from a private PEM."""
    key = serialization.load_pem_private_key(private_pem.encode("ascii"), password=None)
    return (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii")
    )


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
        "aud": "bigbug-frontend",
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

    Uses the ORM so that model-level defaults (e.g. is_custom=False) are
    always honoured, regardless of whether the table was created via Alembic
    migrations or Base.metadata.create_all.
    """
    roles: dict[str, Role] = {}
    for name in RoleName:
        result = await db_session.execute(select(Role).where(Role.name == name.value))
        role = result.scalar_one_or_none()
        if role is None:
            role = Role(name=name.value, description=name.value, is_custom=False)
            db_session.add(role)
            await db_session.flush()
        roles[name.value] = role
    await db_session.commit()
    return roles


# ─── issuer semantics (RFC 8414) ────────────────────────────────────────────


class TestIssuerSemantics:
    """Realm parsing and URL building from the full issuer URI."""

    def test_parse_realm_standard(self):
        assert parse_realm_from_issuer("https://kc.local/realms/myrealm") == "myrealm"

    def test_parse_realm_non_standard_name(self):
        assert parse_realm_from_issuer("http://kc:8080/realms/prod-42_x") == "prod-42_x"

    def test_parse_realm_issuer_with_trailing_slash(self):
        assert parse_realm_from_issuer("https://kc.local/realms/myrealm/") == "myrealm"

    def test_parse_realm_deep_path_takes_first_segment(self):
        # /realms/ deep in the path is NOT a realm issuer — first segment rules.
        assert parse_realm_from_issuer("https://kc.local/auth/realms/myrealm") is None

    def test_parse_realm_no_realm_segment(self):
        assert parse_realm_from_issuer("https://keycloak.local") is None

    def test_parse_realm_empty(self):
        assert parse_realm_from_issuer("") is None

    def test_parse_realm_empty_segment(self):
        assert parse_realm_from_issuer("https://kc.local/realms/") is None

    def test_issuer_with_origin_substitutes_public_url(self):
        issuer = KeycloakOIDCService._issuer(
            CachedOIDCProvider(
                issuer_url="https://kc.local/realms/prod",
                public_url="https://auth.example.com",
            )
        )
        assert issuer == "https://auth.example.com/realms/prod"

    def test_issuer_without_public_url(self):
        issuer = KeycloakOIDCService._issuer(
            CachedOIDCProvider(issuer_url="https://kc.local/realms/prod", public_url=None)
        )
        assert issuer == "https://kc.local/realms/prod"

    @pytest.mark.asyncio
    async def test_is_configured_false_for_legacy_issuer(self, db_session, caplog):
        config = CachedOIDCProvider(
            issuer_url="https://keycloak.local",  # legacy: no /realms/ segment
            frontend_client_id="bigbug-frontend",
            enabled=True,
            public_url=None,
        )
        service = KeycloakOIDCService(db_session, _oidc_config=config)
        with caplog.at_level(logging.WARNING):
            assert await service.is_configured() is False
        assert "oidc_issuer_missing_realm_segment" in caplog.text

    @pytest.mark.asyncio
    async def test_is_configured_true_for_full_issuer(self, db_session):
        config = CachedOIDCProvider(
            issuer_url="https://kc.local/realms/myrealm",
            frontend_client_id="bigbug-frontend",
            enabled=True,
            public_url=None,
        )
        service = KeycloakOIDCService(db_session, _oidc_config=config)
        assert await service.is_configured() is True

    @pytest.mark.asyncio
    async def test_exchange_code_uses_issuer_url_only(self, db_session, mock_http_client):
        """token_url is built from issuer_url alone (no realm suffix appended)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "at"}
        mock_http_client.post.return_value = mock_response

        config = CachedOIDCProvider(
            issuer_url="https://kc.local/realms/myrealm",
            frontend_client_id="bigbug-frontend",
            enabled=True,
            public_url=None,
        )
        service = KeycloakOIDCService(db_session, http_client=mock_http_client, _oidc_config=config)
        await service.exchange_code("code-1", "http://localhost/cb", "vrfy")

        url = mock_http_client.post.call_args.args[0]
        assert url == "https://kc.local/realms/myrealm/protocol/openid-connect/token"

    @pytest.mark.asyncio
    async def test_jwks_url_built_from_issuer(self, db_session, mock_http_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"keys": []}
        mock_response.raise_for_status = MagicMock()
        mock_http_client.get.return_value = mock_response

        config = CachedOIDCProvider(
            issuer_url="https://kc.local/realms/myrealm",
            frontend_client_id="bigbug-frontend",
            enabled=True,
            public_url=None,
        )
        service = KeycloakOIDCService(db_session, http_client=mock_http_client, _oidc_config=config)
        await service._get_jwks()

        url = mock_http_client.get.call_args.args[0]
        assert url == "https://kc.local/realms/myrealm/protocol/openid-connect/certs"


# ─── _JWKSCache ─────────────────────────────────────────────────────────────


class TestJWKSCache:
    def test_cache_miss_when_empty(self):
        cache = _JWKSCache(ttl_seconds=60)
        assert cache.get("https://kc.local/realms/a/certs") is None

    def test_cache_hit(self):
        cache = _JWKSCache(ttl_seconds=60)
        keys = {"keys": [{"kty": "RSA"}]}
        cache.set("https://kc.local/realms/a/certs", keys)
        assert cache.get("https://kc.local/realms/a/certs") is keys

    def test_cache_expired_after_ttl(self):
        cache = _JWKSCache(ttl_seconds=0)
        cache.set("https://kc.local/realms/a/certs", {"keys": [{"kty": "RSA"}]})
        time.sleep(0.001)
        assert cache.get("https://kc.local/realms/a/certs") is None

    def test_clear(self):
        cache = _JWKSCache(ttl_seconds=60)
        cache.set("https://kc.local/realms/a/certs", {"keys": [{"kty": "RSA"}]})
        cache.clear()
        assert cache.get("https://kc.local/realms/a/certs") is None

    def test_providers_isolated(self):
        """Two providers (realms) must never share cached keys (ADR-0037)."""
        cache = _JWKSCache(ttl_seconds=60)
        keys_a = {"keys": [{"kid": "a"}]}
        keys_b = {"keys": [{"kid": "b"}]}
        cache.set("https://kc.local/realms/a/protocol/openid-connect/certs", keys_a)
        cache.set("https://kc.local/realms/b/protocol/openid-connect/certs", keys_b)
        assert cache.get("https://kc.local/realms/a/protocol/openid-connect/certs") is keys_a
        assert cache.get("https://kc.local/realms/b/protocol/openid-connect/certs") is keys_b
        assert cache.get("https://kc.local/realms/c/protocol/openid-connect/certs") is None


# ─── exchange_code ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_exchange_code_success(db_session, mock_http_client, test_oidc_config):
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

    service = KeycloakOIDCService(
        db_session, http_client=mock_http_client, _oidc_config=test_oidc_config
    )
    result = await service.exchange_code("code-42", "http://localhost/cb", "vrfy")

    assert result == token_response
    mock_http_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_exchange_code_invalid(db_session, mock_http_client, test_oidc_config):
    """A non-200 response from Keycloak raises OIDCExchangeError."""
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = '{"error":"invalid_grant"}'
    mock_http_client.post.return_value = mock_response

    service = KeycloakOIDCService(
        db_session, http_client=mock_http_client, _oidc_config=test_oidc_config
    )
    with pytest.raises(OIDCExchangeError, match="rejected"):
        await service.exchange_code("bad-code", "http://localhost/cb", "vrfy")


@pytest.mark.asyncio
async def test_exchange_code_network_error(db_session, mock_http_client, test_oidc_config):
    """Network errors are wrapped in OIDCExchangeError."""
    mock_http_client.post.side_effect = httpx.ConnectError("no route to host")

    service = KeycloakOIDCService(
        db_session, http_client=mock_http_client, _oidc_config=test_oidc_config
    )
    with pytest.raises(OIDCExchangeError, match="identity provider"):
        await service.exchange_code("code-1", "http://localhost/cb", "vrfy")


# ─── validate_id_token ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_validate_id_token_success(
    db_session, rsa_keys, mock_http_client, monkeypatch, test_oidc_config
):
    """A properly signed ID token with valid claims passes validation."""
    private_pem, public_pem = rsa_keys
    id_token = _sign_id_token(private_pem)
    jwks = _build_jwks(public_pem)

    # Pre-load the cache so no HTTP call to Keycloak is needed.
    jwks_cache = _JWKSCache(ttl_seconds=600)
    jwks_cache.set(test_oidc_config.issuer_url + "/protocol/openid-connect/certs", jwks)

    service = KeycloakOIDCService(
        db_session,
        http_client=mock_http_client,
        jwks_cache=jwks_cache,
        _oidc_config=test_oidc_config,
    )
    claims = await service.validate_id_token(id_token)

    assert claims.subject == "kc-user-001"
    assert claims.username == "sso_user"
    assert claims.email == "sso_user@example.com"
    assert claims.full_name == "sso_user"  # fallback: no 'name' claim in token
    assert claims.roles == frozenset({"admin", "viewer"})


@pytest.mark.asyncio
async def test_validate_id_token_expired(db_session, rsa_keys, mock_http_client, test_oidc_config):
    """An expired ID token raises OIDCInvalidTokenError."""
    private_pem, public_pem = rsa_keys
    id_token = _sign_id_token(private_pem, expired=True)
    jwks = _build_jwks(public_pem)

    jwks_cache = _JWKSCache(ttl_seconds=600)
    jwks_cache.set(test_oidc_config.issuer_url + "/protocol/openid-connect/certs", jwks)

    service = KeycloakOIDCService(
        db_session,
        http_client=mock_http_client,
        jwks_cache=jwks_cache,
        _oidc_config=test_oidc_config,
    )
    with pytest.raises(OIDCInvalidTokenError, match="validation failed"):
        await service.validate_id_token(id_token)


@pytest.mark.asyncio
async def test_validate_id_token_bad_signature(
    db_session, rsa_keys, mock_http_client, test_oidc_config
):
    """Token signed with a different key must be rejected."""
    _, public_pem = rsa_keys
    wrong_priv, _ = _build_rsa_keypair()
    id_token = _sign_id_token(wrong_priv)
    jwks = _build_jwks(public_pem)

    jwks_cache = _JWKSCache(ttl_seconds=600)
    jwks_cache.set(test_oidc_config.issuer_url + "/protocol/openid-connect/certs", jwks)

    service = KeycloakOIDCService(
        db_session,
        http_client=mock_http_client,
        jwks_cache=jwks_cache,
        _oidc_config=test_oidc_config,
    )
    with pytest.raises(OIDCInvalidTokenError):
        await service.validate_id_token(id_token)


# ─── provision_or_update_user ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_provision_or_update_user_new(
    db_session, mock_http_client, seeded_roles, test_oidc_config
):
    """A new SSO user is created with the correct claims and roles."""
    claims = OIDCClaims(
        subject="kc-new-user",
        username="new_user",
        email="new_user@example.com",
        full_name="New User",
        roles=frozenset({"operator", "viewer"}),
    )
    service = KeycloakOIDCService(
        db_session, http_client=mock_http_client, _oidc_config=test_oidc_config
    )
    user = await service.provision_or_update_user(claims)

    assert user.id is not None
    assert user.username == "new_user"
    assert user.full_name == "New User"
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
    db_session, mock_http_client, seeded_roles, test_oidc_config
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
        full_name="Existing Updated",
        roles=frozenset({"admin"}),
    )
    service = KeycloakOIDCService(
        db_session, http_client=mock_http_client, _oidc_config=test_oidc_config
    )
    updated = await service.provision_or_update_user(claims)

    assert updated.id == user.id
    assert updated.email == "updated@example.com"
    assert updated.full_name == "Existing Updated"

    # Re-query with eager-load to avoid MissingGreenlet on lazy relationships
    from sqlalchemy.orm import selectinload

    result = await db_session.execute(
        select(User).options(selectinload(User.user_roles)).where(User.id == updated.id)
    )
    updated = result.scalar_one()
    assert {r.name for r in updated.roles} == {"admin"}


@pytest.mark.asyncio
async def test_provision_or_update_user_find_by_email(
    db_session, mock_http_client, seeded_roles, test_oidc_config
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
        full_name="Email User",
        roles=frozenset({"viewer"}),
    )
    service = KeycloakOIDCService(
        db_session, http_client=mock_http_client, _oidc_config=test_oidc_config
    )
    linked = await service.provision_or_update_user(claims)

    assert linked.id == user.id
    assert linked.keycloak_sub == "kc-new-sub-link"


# ─── sync_roles ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sync_roles_add_and_remove(
    db_session, mock_http_client, seeded_roles, test_oidc_config
):
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

    service = KeycloakOIDCService(
        db_session, http_client=mock_http_client, _oidc_config=test_oidc_config
    )
    # Desired: only operator (admin should be removed, operator added)
    await service._sync_roles(user, frozenset({"operator"}))
    await db_session.flush()

    # Re-query with eager-load to avoid MissingGreenlet on lazy relationships
    await db_session.refresh(user, ["user_roles"])
    role_names = {r.name for r in user.roles}
    assert role_names == {"operator"}


@pytest.mark.asyncio
async def test_sync_roles_unknown_ignored(
    db_session, mock_http_client, seeded_roles, test_oidc_config
):
    """Roles not present in the DB are silently ignored."""
    user = User(
        username="unknown_role_test",
        email="unknown@example.com",
        hashed_password=None,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    service = KeycloakOIDCService(
        db_session, http_client=mock_http_client, _oidc_config=test_oidc_config
    )
    await service._sync_roles(user, frozenset({"viewer", "super-admin"}))
    await db_session.flush()

    await db_session.refresh(user, ["user_roles"])
    role_names = {r.name for r in user.roles}
    assert role_names == {"viewer"}


@pytest.mark.asyncio
async def test_sync_roles_none(db_session, mock_http_client, seeded_roles, test_oidc_config):
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

    service = KeycloakOIDCService(
        db_session, http_client=mock_http_client, _oidc_config=test_oidc_config
    )
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
                "name": "John Doe",
                "realm_access": {"roles": ["admin", "operator"]},
            }
        )
        assert claims.subject == "abc"
        assert claims.username == "john"
        assert claims.email == "john@example.com"
        assert claims.full_name == "John Doe"
        assert claims.roles == frozenset({"admin", "operator"})

    def test_name_claim_maps_to_full_name(self):
        claims = KeycloakOIDCService._extract_claims(
            {
                "sub": "abc",
                "preferred_username": "jane",
                "email": "jane@example.com",
                "name": "Jane Smith",
                "realm_access": {"roles": []},
            }
        )
        assert claims.full_name == "Jane Smith"

    def test_full_name_falls_back_to_username(self):
        claims = KeycloakOIDCService._extract_claims(
            {
                "sub": "abc",
                "preferred_username": "jdoe",
                "email": "jdoe@example.com",
                "realm_access": {"roles": []},
            }
        )
        assert claims.full_name == "jdoe"

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


# ─── multi-provider (ADR-0037) ──────────────────────────────────────────────


class TestMultiProvider:
    """Per-provider config lookup and JWKS isolation between providers."""

    @pytest.mark.asyncio
    async def test_jwks_cached_per_provider_url(self, db_session, mock_http_client):
        """Two providers with different realms get separate JWKS entries."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"keys": [{"kid": "realm-a"}]}
        mock_response.raise_for_status = MagicMock()
        mock_http_client.get.return_value = mock_response

        cache = _JWKSCache(ttl_seconds=600)
        provider_a = CachedOIDCProvider(
            id=1,
            issuer_url="https://kc.local/realms/a",
            frontend_client_id="fe-a",
            enabled=True,
        )
        provider_b = CachedOIDCProvider(
            id=2,
            issuer_url="https://kc.local/realms/b",
            frontend_client_id="fe-b",
            enabled=True,
        )

        service_a = KeycloakOIDCService(
            db_session,
            http_client=mock_http_client,
            jwks_cache=cache,
            _oidc_config=provider_a,
        )
        service_b = KeycloakOIDCService(
            db_session,
            http_client=mock_http_client,
            jwks_cache=cache,
            _oidc_config=provider_b,
        )
        await service_a._get_jwks()
        await service_b._get_jwks()

        urls = [call.args[0] for call in mock_http_client.get.call_args_list]
        assert urls == [
            "https://kc.local/realms/a/protocol/openid-connect/certs",
            "https://kc.local/realms/b/protocol/openid-connect/certs",
        ]
        # Isolation: realm A's cached keys never served for realm B.
        assert cache.get("https://kc.local/realms/a/protocol/openid-connect/certs") == {
            "keys": [{"kid": "realm-a"}]
        }

    @pytest.mark.asyncio
    async def test_token_of_realm_a_rejected_under_provider_b(
        self, db_session, rsa_keys, mock_http_client
    ):
        """A token from realm A fails validation under provider B's config."""
        private_pem, public_pem = rsa_keys
        id_token = _sign_id_token(private_pem)  # iss = .../realms/bigbug

        cache = _JWKSCache(ttl_seconds=600)
        # Realm B's JWKS holds a different (real) signing key than realm A's —
        # signature verification must fail under provider B's config.
        wrong_priv, _ = _build_rsa_keypair()
        cache.set(
            "http://localhost:8180/realms/other/protocol/openid-connect/certs",
            _build_jwks(_public_pem(wrong_priv)),
        )

        provider_b = CachedOIDCProvider(
            id=2,
            issuer_url="http://localhost:8180/realms/other",
            frontend_client_id="bigbug-frontend",
            enabled=True,
        )
        service_b = KeycloakOIDCService(
            db_session,
            http_client=mock_http_client,
            jwks_cache=cache,
            _oidc_config=provider_b,
        )
        with pytest.raises(OIDCInvalidTokenError):
            await service_b.validate_id_token(id_token)

    @pytest.mark.asyncio
    async def test_disabled_provider_not_configured(self, db_session):
        provider = CachedOIDCProvider(
            id=3,
            issuer_url="https://kc.local/realms/a",
            frontend_client_id="fe",
            enabled=False,
        )
        service = KeycloakOIDCService(db_session, _oidc_config=provider)
        assert await service.is_configured() is False
