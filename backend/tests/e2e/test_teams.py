"""
@file test_teams.py
@description E2E tests for /api/teams (stage 30): CRUD, membership, permissions.
@dependencies backend/tests/e2e/conftest.py
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.e2e


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestTeamCrud:
    async def test_admin_crud_team(self, client: AsyncClient, admin_token: str, user_factory):
        owner = await user_factory("team-owner-user")
        create_resp = await client.post(
            "/api/teams",
            headers=auth(admin_token),
            json={"name": "e2e-team", "description": "desc", "owner_user_id": owner.id},
        )
        assert create_resp.status_code == 201
        team = create_resp.json()
        assert team["name"] == "e2e-team"
        assert team["owner"]["id"] == owner.id
        assert team["members_count"] == 1
        assert team["my_role"] is None  # admin is not a member

        get_resp = await client.get(f"/api/teams/{team['id']}", headers=auth(admin_token))
        assert get_resp.status_code == 200

        patch_resp = await client.patch(
            f"/api/teams/{team['id']}",
            headers=auth(admin_token),
            json={"description": "updated"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["description"] == "updated"

        delete_resp = await client.delete(f"/api/teams/{team['id']}", headers=auth(admin_token))
        assert delete_resp.status_code == 204

        gone_resp = await client.get(f"/api/teams/{team['id']}", headers=auth(admin_token))
        assert gone_resp.status_code == 404

    async def test_admin_list_all_teams(self, client: AsyncClient, admin_token: str, user_factory):
        owner = await user_factory("team-list-owner")
        await client.post(
            "/api/teams",
            headers=auth(admin_token),
            json={"name": "e2e-list-team", "owner_user_id": owner.id},
        )
        resp = await client.get("/api/teams", headers=auth(admin_token), params={"all": "true"})
        assert resp.status_code == 200
        names = {t["name"] for t in resp.json()}
        assert "e2e-list-team" in names

    async def test_viewer_cannot_create_team(self, client: AsyncClient, viewer_token: str):
        resp = await client.post(
            "/api/teams",
            headers=auth(viewer_token),
            json={"name": "viewer-team", "owner_user_id": 1},
        )
        assert resp.status_code == 403


class TestMembership:
    async def test_admin_add_member(self, client: AsyncClient, admin_token: str, user_factory):
        owner = await user_factory("mem-owner")
        member = await user_factory("mem-member")
        create_resp = await client.post(
            "/api/teams",
            headers=auth(admin_token),
            json={"name": "e2e-mem-team", "owner_user_id": owner.id},
        )
        team_id = create_resp.json()["id"]

        add_resp = await client.post(
            f"/api/teams/{team_id}/members",
            headers=auth(admin_token),
            json={"user_id": member.id},
        )
        assert add_resp.status_code == 201
        assert add_resp.json()["user_id"] == member.id

        dup_resp = await client.post(
            f"/api/teams/{team_id}/members",
            headers=auth(admin_token),
            json={"user_id": member.id},
        )
        assert dup_resp.status_code == 409

        members_resp = await client.get(f"/api/teams/{team_id}/members", headers=auth(admin_token))
        assert members_resp.status_code == 200
        assert {m["user_id"] for m in members_resp.json()} == {owner.id, member.id}

    async def test_remove_member_and_self_exit(
        self, client: AsyncClient, admin_token: str, user_factory
    ):
        owner = await user_factory("rm-owner")
        member = await user_factory("rm-member")
        create_resp = await client.post(
            "/api/teams",
            headers=auth(admin_token),
            json={"name": "e2e-rm-team", "owner_user_id": owner.id},
        )
        team_id = create_resp.json()["id"]
        await client.post(
            f"/api/teams/{team_id}/members",
            headers=auth(admin_token),
            json={"user_id": member.id},
        )

        remove_resp = await client.delete(
            f"/api/teams/{team_id}/members/{member.id}", headers=auth(admin_token)
        )
        assert remove_resp.status_code == 204

        # Removing the lead must fail with 400.
        lead_resp = await client.delete(
            f"/api/teams/{team_id}/members/{owner.id}", headers=auth(admin_token)
        )
        assert lead_resp.status_code == 400

    async def test_team_providers_endpoint(
        self, client: AsyncClient, admin_token: str, user_factory
    ):
        owner = await user_factory("prov-owner")
        create_resp = await client.post(
            "/api/teams",
            headers=auth(admin_token),
            json={"name": "e2e-prov-team", "owner_user_id": owner.id},
        )
        team_id = create_resp.json()["id"]

        resp = await client.get(f"/api/teams/{team_id}/providers", headers=auth(admin_token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
