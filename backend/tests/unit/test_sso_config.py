"""
@file test_sso_config.py
@description Integration tests for GET /api/auth/sso/config (list contract,
              ADR-0037) and the admin provider CRUD: realm/url computed per
              ADR-0036, legacy issuer rows skipped, master-switch off → empty
              list, disabled provider hidden from the list.
@relatedFiles app/api/auth.py, app/services/oidc_providers.py
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.oidc_provider import OIDCProvider
from app.services.oidc_providers import invalidate_oidc_providers_cache


async def _seed_provider(db_session: AsyncSession, **overrides) -> OIDCProvider:
    defaults: dict = {
        "name": "Keycloak",
        "issuer_url": "https://kc.local/realms/prod",
        "client_id": "bigbug-backend",
        "client_secret": None,
        "frontend_client_id": "bigbug-frontend",
        "enabled": True,
        "public_url": None,
        "role_mapping": {},
        "sort_order": 0,
    }
    defaults.update(overrides)
    row = OIDCProvider(**defaults)
    db_session.add(row)
    await db_session.commit()
    invalidate_oidc_providers_cache()
    return row


@pytest.fixture(autouse=True)
def _clean_cache():
    invalidate_oidc_providers_cache()
    yield
    invalidate_oidc_providers_cache()


@pytest.mark.asyncio
async def test_sso_config_computes_realm_and_url(client: AsyncClient, db_session: AsyncSession):
    await _seed_provider(db_session, public_url="https://auth.example.com")
    response = await client.get("/api/auth/sso/config")
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert data["providers"] == [
        {
            "id": data["providers"][0]["id"],
            "name": "Keycloak",
            "realm": "prod",
            "url": "https://auth.example.com",
            "client_id": "bigbug-frontend",
        }
    ]


@pytest.mark.asyncio
async def test_sso_config_url_falls_back_to_issuer_origin(
    client: AsyncClient, db_session: AsyncSession
):
    await _seed_provider(db_session, public_url=None)
    response = await client.get("/api/auth/sso/config")
    assert response.json()["providers"][0]["url"] == "https://kc.local"


@pytest.mark.asyncio
async def test_sso_config_two_providers_different_realms(
    client: AsyncClient, db_session: AsyncSession
):
    """Both providers are listed with their own url/realm (ADR-0037)."""
    await _seed_provider(db_session, name="A", issuer_url="https://kc.local/realms/a")
    await _seed_provider(
        db_session,
        name="B",
        issuer_url="https://other.local/realms/b",
        frontend_client_id="fe-b",
        public_url="https://auth.local",
        sort_order=1,
    )
    response = await client.get("/api/auth/sso/config")
    providers = response.json()["providers"]
    assert [(p["name"], p["realm"], p["url"]) for p in providers] == [
        ("A", "a", "https://kc.local"),
        ("B", "b", "https://auth.local"),
    ]


@pytest.mark.asyncio
async def test_sso_config_legacy_issuer_skipped(
    client: AsyncClient, db_session: AsyncSession, caplog
):
    """A legacy row without /realms/ segment is skipped, others still listed."""
    await _seed_provider(db_session, issuer_url="https://keycloak.local", public_url=None)
    with caplog.at_level("WARNING"):
        response = await client.get("/api/auth/sso/config")
    assert response.status_code == 200
    data = response.json()
    assert data["providers"] == []
    assert data["enabled"] is False
    assert "oidc_issuer_missing_realm_segment" in caplog.text


@pytest.mark.asyncio
async def test_sso_config_disabled_provider_hidden(client: AsyncClient, db_session: AsyncSession):
    await _seed_provider(db_session, enabled=False)
    response = await client.get("/api/auth/sso/config")
    data = response.json()
    assert data["enabled"] is False
    assert data["providers"] == []


@pytest.mark.asyncio
async def test_sso_config_master_switch_off(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
):
    """Master-switch off → enabled=false and an empty list, even with rows."""
    await _seed_provider(db_session)
    from app.config import settings

    monkeypatch.setattr(settings, "sso_enabled", False)
    response = await client.get("/api/auth/sso/config")
    data = response.json()
    assert data["enabled"] is False
    assert data["providers"] == []


# ─── Admin CRUD ─────────────────────────────────────────────────────────────


HDR = {"Authorization": "Bearer x"}


@pytest.mark.asyncio
async def test_admin_crud_roundtrip(
    client: AsyncClient, db_session: AsyncSession, admin_token: str
):
    headers = {"Authorization": f"Bearer {admin_token}"}

    # POST
    resp = await client.post(
        "/api/auth/admin/oidc-providers",
        headers=headers,
        json={"name": "Corp", "issuer_url": "https://kc.example.com/realms/myrealm"},
    )
    assert resp.status_code == 201
    body = resp.json()
    pid = body["id"]
    assert body["client_secret"] == "********"
    assert body["enabled"] is False

    # sso/config shows the provider once enabled
    await client.patch(
        f"/api/auth/admin/oidc-providers/{pid}",
        headers=headers,
        json={"enabled": True},
    )
    sso = (await client.get("/api/auth/sso/config")).json()
    assert [p["id"] for p in sso["providers"]] == [pid]

    # Disable → hidden
    await client.patch(
        f"/api/auth/admin/oidc-providers/{pid}", headers=headers, json={"enabled": False}
    )
    sso = (await client.get("/api/auth/sso/config")).json()
    assert sso["providers"] == []

    # PATCH 404
    resp = await client.patch(
        "/api/auth/admin/oidc-providers/99999", headers=headers, json={"enabled": True}
    )
    assert resp.status_code == 404

    # DELETE
    resp = await client.delete(f"/api/auth/admin/oidc-providers/{pid}", headers=headers)
    assert resp.status_code == 204
    resp = await client.delete(f"/api/auth/admin/oidc-providers/{pid}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_create_rejects_issuer_without_realm(client: AsyncClient, admin_token: str):
    response = await client.post(
        "/api/auth/admin/oidc-providers",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Bad", "issuer_url": "https://kc.example.com"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_admin_update_accepts_full_issuer(
    client: AsyncClient, db_session: AsyncSession, admin_token: str
):
    row = await _seed_provider(db_session)
    response = await client.patch(
        f"/api/auth/admin/oidc-providers/{row.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"issuer_url": "https://kc.example.com/realms/myrealm"},
    )
    assert response.status_code == 200
    assert response.json()["issuer_url"] == "https://kc.example.com/realms/myrealm"


# ─── Exchange provider resolution ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_exchange_unknown_provider_id(client: AsyncClient):
    """Unknown provider_id → 4xx (502 from unknown-provider resolution), not a wrong lookup."""
    response = await client.post(
        "/api/auth/oidc/exchange",
        json={
            "code": "c",
            "redirect_uri": "http://localhost/cb",
            "code_verifier": "v",
            "provider_id": 424242,
            "state": "424242",
        },
    )
    assert response.status_code == 502


@pytest.mark.asyncio
async def test_exchange_state_provider_mismatch(client: AsyncClient, db_session: AsyncSession):
    """state carrying another provider's id → 401 (CSRF/broken flow)."""
    await _seed_provider(db_session)
    response = await client.post(
        "/api/auth/oidc/exchange",
        json={
            "code": "c",
            "redirect_uri": "http://localhost/cb",
            "code_verifier": "v",
            "provider_id": 1,
            "state": "999",
        },
    )
    assert response.status_code == 401
