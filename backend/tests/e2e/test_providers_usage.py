"""
@file test_providers_usage.py
@description E2E tests for provider usage/share/unshare (/api/providers) against
              a live backend. share/unshare require a private provider and an
              existing team (admin has providers:read_all, so team membership is
              not required). Data isolation via unique names. No sqlite, no mocks.
@dependencies backend/tests/e2e/conftest.py
"""

import pytest
from httpx import AsyncClient

from tests.e2e.conftest import assert_matches_openapi

pytestmark = pytest.mark.e2e


class TestProviderUsage:
    async def test_usage_on_public_provider(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        # Seeded public provider (github-anonymous, id=1) is stable across runs.
        response = await client.get("/api/providers/1/usage", headers=admin_headers)
        assert_matches_openapi(response, "/api/providers/{provider_id}/usage", "get", openapi_spec)
        assert response.status_code == 200
        assert response.json()["provider_id"] == 1
        assert isinstance(response.json()["usage"], list)


class TestProviderShare:
    async def test_share_and_unshare_private_provider(
        self, client: AsyncClient, admin_headers: dict, unique_name: str, openapi_spec: dict
    ):
        # Determine admin's user id for team ownership.
        me = await client.get("/api/auth/me", headers=admin_headers)
        assert me.status_code == 200
        admin_user_id = me.json()["id"]

        team = await client.post(
            "/api/teams",
            headers=admin_headers,
            json={"name": f"share-team-{unique_name}", "owner_user_id": admin_user_id},
        )
        assert team.status_code == 201
        team_id = team.json()["id"]

        provider = await client.post(
            "/api/providers",
            headers=admin_headers,
            json={
                "domain": "git",
                "subtype": "github",
                "category": "private",
                "direction": "external",
                "name": f"share-prov-{unique_name}",
                "label": f"share-prov-{unique_name}",
            },
        )
        assert provider.status_code == 201
        provider_id = provider.json()["id"]

        try:
            share = await client.post(
                f"/api/providers/{provider_id}/share",
                headers=admin_headers,
                json={"team_id": team_id},
            )
            assert_matches_openapi(
                share, "/api/providers/{provider_id}/share", "post", openapi_spec
            )
            assert share.status_code == 200
            assert share.json()["visibility"] == "team"
            assert share.json()["team_id"] == team_id

            unshare = await client.post(
                f"/api/providers/{provider_id}/unshare", headers=admin_headers
            )
            assert_matches_openapi(
                unshare, "/api/providers/{provider_id}/unshare", "post", openapi_spec
            )
            assert unshare.status_code == 200
            assert unshare.json()["visibility"] == "owner"
        finally:
            await client.delete(f"/api/providers/{provider_id}", headers=admin_headers)
            await client.delete(f"/api/teams/{team_id}", headers=admin_headers)
