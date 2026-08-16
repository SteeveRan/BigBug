"""
@file test_teams.py
@description E2E tests for the Teams API (/api/teams) against a live backend:
              CRUD, membership add/duplicate/remove/lead-guard, viewer RBAC 403
              and team-provider listing. Users are provisioned through the real
              admin API and torn down afterwards. Teams are always deleted
              BEFORE their owner users to satisfy the ``teams_owner_user_id``
              foreign key. No sqlite, no mocks.
@dependencies backend/tests/e2e/conftest.py
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.e2e.conftest import assert_matches_openapi

pytestmark = pytest.mark.e2e


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def user_factory(client: AsyncClient, admin_headers: dict):
    """Create ephemeral users via the admin API; clean them all up afterwards."""
    created: list[int] = []

    async def factory(username: str) -> dict:
        resp = await client.post(
            "/api/admin/users",
            headers=admin_headers,
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password": "e2e-team-user-password",
                "roles": ["viewer"],
            },
        )
        assert resp.status_code == 201, f"Failed to create user {username}: {resp.text}"
        created.append(resp.json()["id"])
        return resp.json()

    yield factory

    for user_id in created:
        await client.delete(f"/api/admin/users/{user_id}", headers=admin_headers)


@pytest_asyncio.fixture
async def team_factory(client: AsyncClient, admin_headers: dict):
    """Create teams via the API and delete them (in reverse order) afterwards.

    Requested AFTER ``user_factory`` in each test signature, so pytest tears
    this fixture down BEFORE ``user_factory`` — teams are deleted first, which
    avoids the ``teams_owner_user_id`` FK violation on owner-user deletion.
    """
    created: list[int] = []

    async def factory(name: str, owner_user_id: int) -> dict:
        resp = await client.post(
            "/api/teams",
            headers=admin_headers,
            json={"name": name, "owner_user_id": owner_user_id},
        )
        assert resp.status_code == 201, f"Failed to create team {name}: {resp.text}"
        created.append(resp.json()["id"])
        return resp.json()

    yield factory

    for team_id in reversed(created):
        await client.delete(f"/api/teams/{team_id}", headers=admin_headers)


class TestTeamCrud:
    async def test_admin_crud_team(
        self,
        client: AsyncClient,
        admin_headers: dict,
        user_factory,
        unique_name: str,
        openapi_spec: dict,
    ):
        owner = await user_factory(f"owner-{unique_name}")
        create = await client.post(
            "/api/teams",
            headers=admin_headers,
            json={
                "name": f"team-{unique_name}",
                "description": "desc",
                "owner_user_id": owner["id"],
            },
        )
        assert_matches_openapi(create, "/api/teams", "post", openapi_spec)
        assert create.status_code == 201
        team = create.json()
        assert team["name"] == f"team-{unique_name}"
        assert team["owner"]["id"] == owner["id"]
        assert team["members_count"] == 1

        get = await client.get(f"/api/teams/{team['id']}", headers=admin_headers)
        assert_matches_openapi(get, "/api/teams/{team_id}", "get", openapi_spec)
        assert get.status_code == 200

        patch = await client.patch(
            f"/api/teams/{team['id']}", headers=admin_headers, json={"description": "updated"}
        )
        assert_matches_openapi(patch, "/api/teams/{team_id}", "patch", openapi_spec)
        assert patch.status_code == 200
        assert patch.json()["description"] == "updated"

        delete = await client.delete(f"/api/teams/{team['id']}", headers=admin_headers)
        assert_matches_openapi(delete, "/api/teams/{team_id}", "delete", openapi_spec)
        assert delete.status_code == 204

        gone = await client.get(f"/api/teams/{team['id']}", headers=admin_headers)
        assert gone.status_code == 404

    async def test_admin_list_all_teams(
        self,
        client: AsyncClient,
        admin_headers: dict,
        user_factory,
        team_factory,
        unique_name: str,
        openapi_spec: dict,
    ):
        owner = await user_factory(f"listowner-{unique_name}")
        await team_factory(f"list-{unique_name}", owner["id"])
        resp = await client.get("/api/teams", headers=admin_headers, params={"all": "true"})
        assert_matches_openapi(resp, "/api/teams", "get", openapi_spec)
        assert resp.status_code == 200
        names = {t["name"] for t in resp.json()}
        assert f"list-{unique_name}" in names

    async def test_viewer_cannot_create_team(self, client: AsyncClient, viewer_headers: dict):
        resp = await client.post(
            "/api/teams",
            headers=viewer_headers,
            json={"name": "viewer-team", "owner_user_id": 1},
        )
        assert resp.status_code == 403


class TestMembership:
    async def test_admin_add_member(
        self,
        client: AsyncClient,
        admin_headers: dict,
        user_factory,
        team_factory,
        unique_name: str,
        openapi_spec: dict,
    ):
        owner = await user_factory(f"memowner-{unique_name}")
        member = await user_factory(f"memmember-{unique_name}")
        team = await team_factory(f"mem-{unique_name}", owner["id"])
        team_id = team["id"]

        add = await client.post(
            f"/api/teams/{team_id}/members",
            headers=admin_headers,
            json={"user_id": member["id"]},
        )
        assert_matches_openapi(add, "/api/teams/{team_id}/members", "post", openapi_spec)
        assert add.status_code == 201
        assert add.json()["user_id"] == member["id"]

        dup = await client.post(
            f"/api/teams/{team_id}/members",
            headers=admin_headers,
            json={"user_id": member["id"]},
        )
        assert dup.status_code == 409

        members = await client.get(f"/api/teams/{team_id}/members", headers=admin_headers)
        assert_matches_openapi(members, "/api/teams/{team_id}/members", "get", openapi_spec)
        assert members.status_code == 200
        assert {m["user_id"] for m in members.json()} == {owner["id"], member["id"]}

    async def test_remove_member_and_lead_guard(
        self,
        client: AsyncClient,
        admin_headers: dict,
        user_factory,
        team_factory,
        unique_name: str,
    ):
        owner = await user_factory(f"rmowner-{unique_name}")
        member = await user_factory(f"rmmember-{unique_name}")
        team = await team_factory(f"rm-{unique_name}", owner["id"])
        team_id = team["id"]
        await client.post(
            f"/api/teams/{team_id}/members",
            headers=admin_headers,
            json={"user_id": member["id"]},
        )

        remove = await client.delete(
            f"/api/teams/{team_id}/members/{member['id']}", headers=admin_headers
        )
        assert remove.status_code == 204

        # Removing the lead must fail with 400.
        lead = await client.delete(
            f"/api/teams/{team_id}/members/{owner['id']}", headers=admin_headers
        )
        assert lead.status_code == 400

    async def test_team_providers_endpoint(
        self,
        client: AsyncClient,
        admin_headers: dict,
        user_factory,
        team_factory,
        unique_name: str,
        openapi_spec: dict,
    ):
        owner = await user_factory(f"provowner-{unique_name}")
        team = await team_factory(f"prov-{unique_name}", owner["id"])
        team_id = team["id"]

        resp = await client.get(f"/api/teams/{team_id}/providers", headers=admin_headers)
        assert_matches_openapi(resp, "/api/teams/{team_id}/providers", "get", openapi_spec)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
