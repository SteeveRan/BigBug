"""
@file test_sso_config.py
@description Integration tests for GET /api/auth/sso/config with the full-issuer
             semantics (RFC 8414): realm/url are computed by the backend from
             issuer_url + public_url; legacy issuer values yield enabled=false.
@relatedFiles app/api/auth.py, app/services/oidc.py
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.oidc_config import OIDCConfig
from app.services.oidc_config import invalidate_oidc_cache


async def _seed_config(db_session: AsyncSession, **overrides) -> None:
    defaults: dict = {
        "issuer_url": "https://kc.local/realms/prod",
        "client_id": "bigbug-backend",
        "client_secret": None,
        "frontend_client_id": "bigbug-frontend",
        "enabled": True,
        "public_url": None,
        "role_mapping": {},
    }
    defaults.update(overrides)
    db_session.add(OIDCConfig(**defaults))
    await db_session.commit()
    invalidate_oidc_cache()


@pytest.fixture(autouse=True)
def _clean_cache():
    invalidate_oidc_cache()
    yield
    invalidate_oidc_cache()


@pytest.mark.asyncio
async def test_sso_config_computes_realm_and_url(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_config(db_session, public_url="https://auth.example.com")
    response = await client.get("/api/auth/sso/config")
    assert response.status_code == 200
    data = response.json()
    assert data["realm"] == "prod"
    assert data["url"] == "https://auth.example.com"
    assert data["client_id"] == "bigbug-frontend"
    assert data["enabled"] is True


@pytest.mark.asyncio
async def test_sso_config_url_falls_back_to_issuer_origin(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_config(db_session, public_url=None)
    response = await client.get("/api/auth/sso/config")
    assert response.status_code == 200
    assert response.json()["url"] == "https://kc.local"


@pytest.mark.asyncio
async def test_sso_config_legacy_issuer_disabled(
    client: AsyncClient, db_session: AsyncSession, caplog
):
    """A legacy row without /realms/ segment → enabled=false, no crash."""
    await _seed_config(db_session, issuer_url="https://keycloak.local", public_url=None)
    with caplog.at_level("WARNING"):
        response = await client.get("/api/auth/sso/config")
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is False
    assert "oidc_issuer_missing_realm_segment" in caplog.text


@pytest.mark.asyncio
async def test_patch_oidc_config_rejects_issuer_without_realm(
    client: AsyncClient, admin_token: str
):
    response = await client.patch(
        "/api/auth/admin/oidc-config",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"issuer_url": "https://kc.example.com"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_oidc_config_accepts_full_issuer(
    client: AsyncClient, db_session: AsyncSession, admin_token: str
):
    response = await client.patch(
        "/api/auth/admin/oidc-config",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"issuer_url": "https://kc.example.com/realms/myrealm"},
    )
    assert response.status_code == 200
    assert response.json()["issuer_url"] == "https://kc.example.com/realms/myrealm"
