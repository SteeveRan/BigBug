"""
@file test_providers.py
@description End-to-end API tests for the unified Providers V3 router
             (``/api/providers``). Covers TDD stage 13 (plan section 11.7):
             types metadata, CRUD, duplicate 409, validation 422, protected
             delete 409, ``owner=me`` filtering, usage and viewer write-denial.
@dependencies pytest, pytest-asyncio, httpx, backend/tests/e2e/conftest.py
@relatedFiles ../../app/api/providers.py, ../../app/services/providers/service.py
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.e2e


def auth(token: str) -> dict[str, str]:
    """Authorization header for a JWT token."""
    return {"Authorization": f"Bearer {token}"}


def private_payload(name: str) -> dict:
    """A valid private GitHub provider payload."""
    return {
        "domain": "git",
        "subtype": "github",
        "category": "private",
        "direction": "external",
        "name": name,
        "label": name,
    }


def public_payload(name: str) -> dict:
    """A valid public GitHub provider payload."""
    return {
        "domain": "git",
        "subtype": "github",
        "category": "public",
        "direction": "external",
        "name": name,
        "label": name,
    }


def system_payload(name: str) -> dict:
    """A valid system GitLab provider payload."""
    return {
        "domain": "git",
        "subtype": "gitlab",
        "category": "system",
        "direction": "internal",
        "name": name,
        "label": name,
        "base_url": "https://gitlab.internal.example.com",
    }


class TestProviderTypes:
    async def test_get_types_200(self, client: AsyncClient, admin_token: str):
        """GET /api/providers/types returns registry metadata for any user."""
        response = await client.get("/api/providers/types", headers=auth(admin_token))
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert {"subtype", "domain", "label", "capabilities", "config_schema"} <= set(data[0])


class TestProviderCrud:
    async def test_create_get_update_delete(self, client: AsyncClient, admin_token: str):
        """Full CRUD lifecycle returns 201/200/204."""
        create_resp = await client.post(
            "/api/providers", headers=auth(admin_token), json=private_payload("crud-provider")
        )
        assert create_resp.status_code == 201
        created = create_resp.json()
        assert created["name"] == "crud-provider"
        assert created["owner_user_id"] is not None  # private → current_user

        get_resp = await client.get(f"/api/providers/{created['id']}", headers=auth(admin_token))
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "crud-provider"

        patch_resp = await client.patch(
            f"/api/providers/{created['id']}",
            headers=auth(admin_token),
            json={"label": "crud-provider-renamed"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["label"] == "crud-provider-renamed"

        delete_resp = await client.delete(
            f"/api/providers/{created['id']}", headers=auth(admin_token)
        )
        assert delete_resp.status_code == 204

        gone_resp = await client.get(f"/api/providers/{created['id']}", headers=auth(admin_token))
        assert gone_resp.status_code == 404

    async def test_create_duplicate_name_409(self, client: AsyncClient, admin_token: str):
        """Creating a provider with an existing live name returns 409."""
        first = await client.post(
            "/api/providers", headers=auth(admin_token), json=private_payload("dup-provider")
        )
        assert first.status_code == 201

        second = await client.post(
            "/api/providers", headers=auth(admin_token), json=private_payload("dup-provider")
        )
        assert second.status_code == 409

    async def test_create_invalid_category_422(self, client: AsyncClient, admin_token: str):
        """A subtype/category combo rejected by the registry returns 422."""
        payload = private_payload("invalid-category")
        payload["category"] = "system"  # github does not allow system
        response = await client.post("/api/providers", headers=auth(admin_token), json=payload)
        assert response.status_code == 422

    async def test_delete_protected_409(self, client: AsyncClient, admin_token: str):
        """System providers are protected and cannot be deleted (409)."""
        create_resp = await client.post(
            "/api/providers", headers=auth(admin_token), json=system_payload("system-gitlab")
        )
        assert create_resp.status_code == 201
        assert create_resp.json()["is_protected"] is True

        delete_resp = await client.delete(
            f"/api/providers/{create_resp.json()['id']}", headers=auth(admin_token)
        )
        assert delete_resp.status_code == 409

    async def test_usage_200(self, client: AsyncClient, admin_token: str):
        """GET /api/providers/{id}/usage returns an (empty) usage list."""
        create_resp = await client.post(
            "/api/providers", headers=auth(admin_token), json=private_payload("usage-provider")
        )
        assert create_resp.status_code == 201

        response = await client.get(
            f"/api/providers/{create_resp.json()['id']}/usage", headers=auth(admin_token)
        )
        assert response.status_code == 200
        data = response.json()
        assert data["provider_id"] == create_resp.json()["id"]
        assert data["usage"] == []


class TestProviderVisibility:
    async def test_owner_me_filter(self, client: AsyncClient, admin_token: str):
        """``owner=me`` returns only providers owned by the caller."""
        private_resp = await client.post(
            "/api/providers", headers=auth(admin_token), json=private_payload("mine-provider")
        )
        assert private_resp.status_code == 201
        public_resp = await client.post(
            "/api/providers", headers=auth(admin_token), json=public_payload("shared-provider")
        )
        assert public_resp.status_code == 201

        response = await client.get(
            "/api/providers", headers=auth(admin_token), params={"owner": "me"}
        )
        assert response.status_code == 200
        names = {p["name"] for p in response.json()}
        assert "mine-provider" in names
        assert "shared-provider" not in names

    async def test_viewer_without_write_403(self, client: AsyncClient, viewer_token: str):
        """A viewer with ``providers:read`` but not ``providers:write`` gets 403."""
        response = await client.post(
            "/api/providers", headers=auth(viewer_token), json=private_payload("viewer-write")
        )
        assert response.status_code == 403

    async def test_viewer_can_read_200(self, client: AsyncClient, viewer_token: str):
        """A viewer can read the provider list."""
        response = await client.get("/api/providers", headers=auth(viewer_token))
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestProviderTeamVisibility:
    """Stage 31: e2e visibility matrix with 3 users and 2 teams."""

    async def test_team_isolation(
        self,
        client: AsyncClient,
        operator_token: str,
        viewer_token: str,
        operator_user,
        viewer_user,
        team_factory,
    ):
        # Operator is lead of both teams; viewer belongs only to team B.
        team_a = await team_factory("vis-team-a", operator_user.id)
        await team_factory("vis-team-b", operator_user.id, [viewer_user.id])

        # Operator creates a team-shared provider for team A.
        create_resp = await client.post(
            "/api/providers",
            headers=auth(operator_token),
            json={
                **private_payload("vis-team-provider"),
                "visibility": "team",
                "team_id": team_a.id,
            },
        )
        assert create_resp.status_code == 201
        provider_id = create_resp.json()["id"]

        # Operator (lead/member of team A) sees it.
        list_operator = await client.get("/api/providers", headers=auth(operator_token))
        assert any(p["id"] == provider_id for p in list_operator.json())

        # Viewer (member of team B, not team A) does not see it.
        list_viewer = await client.get("/api/providers", headers=auth(viewer_token))
        assert all(p["id"] != provider_id for p in list_viewer.json())

    async def test_share_unshare_e2e(
        self,
        client: AsyncClient,
        admin_token: str,
        user_factory,
        team_factory,
    ):
        owner = await user_factory("share-owner-e2e")
        member = await user_factory("share-member-e2e")
        team = await team_factory("share-team-e2e", owner.id, [member.id])

        create_resp = await client.post(
            "/api/providers", headers=auth(admin_token), json=private_payload("share-provider-e2e")
        )
        assert create_resp.status_code == 201
        provider_id = create_resp.json()["id"]

        share_resp = await client.post(
            f"/api/providers/{provider_id}/share",
            headers=auth(admin_token),
            json={"team_id": team.id},
        )
        assert share_resp.status_code == 200
        assert share_resp.json()["visibility"] == "team"
        assert share_resp.json()["team_id"] == team.id

        unshare_resp = await client.post(
            f"/api/providers/{provider_id}/unshare", headers=auth(admin_token)
        )
        assert unshare_resp.status_code == 200
        assert unshare_resp.json()["visibility"] == "owner"
        assert unshare_resp.json()["team_id"] is None

    async def test_post_patch_visibility_e2e(self, client: AsyncClient, admin_token: str):
        create_resp = await client.post(
            "/api/providers", headers=auth(admin_token), json=private_payload("patch-vis-provider")
        )
        assert create_resp.status_code == 201
        provider_id = create_resp.json()["id"]
        assert create_resp.json()["visibility"] == "owner"

        # PATCH visibility to public (private category allowed).
        patch_resp = await client.patch(
            f"/api/providers/{provider_id}",
            headers=auth(admin_token),
            json={"visibility": "public"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["visibility"] == "public"
