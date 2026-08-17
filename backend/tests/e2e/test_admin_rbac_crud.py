"""
@file test_admin_rbac_crud.py
@description E2E tests for admin RBAC CRUD against a live backend:
              roles (create/get/patch/delete/list-users), role scopes for all
              four resource types (source-groups, credentials, sync-groups,
              providers), and admin users (patch/delete). Roles are custom
              (is_custom=True) so they may be modified and deleted; users are
              soft-isolated via unique names and torn down. No sqlite, no mocks.
@dependencies backend/tests/e2e/conftest.py
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.e2e.conftest import assert_matches_openapi

pytestmark = pytest.mark.e2e


async def _create_role(client: AsyncClient, admin_headers: dict, name: str) -> dict:
    resp = await client.post(
        "/api/admin/roles",
        headers=admin_headers,
        json={
            "name": name,
            "description": "e2e custom role",
            "permission_names": ["mirrors:read"],
        },
    )
    assert resp.status_code == 201, f"Failed to create role {name}: {resp.text}"
    return resp.json()


class TestAdminUsers:
    async def test_patch_and_delete_user(
        self, client: AsyncClient, admin_headers: dict, unique_name: str, openapi_spec: dict
    ):
        username = f"u-{unique_name}"
        create = await client.post(
            "/api/admin/users",
            headers=admin_headers,
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password": "e2e-password",
                "roles": ["viewer"],
            },
        )
        assert_matches_openapi(create, "/api/admin/users", "post", openapi_spec)
        assert create.status_code == 201
        user_id = create.json()["id"]

        patch = await client.patch(
            f"/api/admin/users/{user_id}",
            headers=admin_headers,
            json={"email": f"{username}-renamed@example.com", "is_active": False},
        )
        assert_matches_openapi(patch, "/api/admin/users/{user_id}", "patch", openapi_spec)
        assert patch.status_code == 200
        assert patch.json()["email"] == f"{username}-renamed@example.com"
        assert patch.json()["is_active"] is False

        delete = await client.delete(f"/api/admin/users/{user_id}", headers=admin_headers)
        assert_matches_openapi(delete, "/api/admin/users/{user_id}", "delete", openapi_spec)
        assert delete.status_code == 204


class TestAdminRoles:
    async def test_crud_role(
        self, client: AsyncClient, admin_headers: dict, unique_name: str, openapi_spec: dict
    ):
        name = f"role-{unique_name}"
        create = await client.post(
            "/api/admin/roles",
            headers=admin_headers,
            json={
                "name": name,
                "description": "e2e custom role",
                "permission_names": ["mirrors:read"],
            },
        )
        assert_matches_openapi(create, "/api/admin/roles", "post", openapi_spec)
        assert create.status_code == 201
        role = create.json()
        assert role["name"] == name
        assert role["is_custom"] is True
        role_id = role["id"]

        get = await client.get(f"/api/admin/roles/{role_id}", headers=admin_headers)
        assert_matches_openapi(get, "/api/admin/roles/{role_id}", "get", openapi_spec)
        assert get.status_code == 200
        assert get.json()["name"] == name

        patch = await client.patch(
            f"/api/admin/roles/{role_id}",
            headers=admin_headers,
            json={"description": "updated"},
        )
        assert_matches_openapi(patch, "/api/admin/roles/{role_id}", "patch", openapi_spec)
        assert patch.status_code == 200
        assert patch.json()["description"] == "updated"

        users = await client.get(f"/api/admin/roles/{role_id}/users", headers=admin_headers)
        assert_matches_openapi(users, "/api/admin/roles/{role_id}/users", "get", openapi_spec)
        assert users.status_code == 200
        assert isinstance(users.json(), list)

        delete = await client.delete(f"/api/admin/roles/{role_id}", headers=admin_headers)
        assert_matches_openapi(delete, "/api/admin/roles/{role_id}", "delete", openapi_spec)
        assert delete.status_code == 204

    async def test_cannot_modify_builtin_role(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        # admin (id=1) is a built-in role — PATCH must return 403.
        patch = await client.patch(
            "/api/admin/roles/1", headers=admin_headers, json={"description": "nope"}
        )
        assert patch.status_code == 403


class TestAdminRoleScopes:
    """Exercise scope resource types.

    GET/PUT/empty-list/DELETE are FK-safe (no inserts with unknown resource
    ids), so they are exercised for all four resource types. POST inserts a
    scope row with a real FK, so it runs only for resources that can be
    created via pure-DB endpoints (providers use the seeded id=1, credentials
    and sync-groups are created on the fly).
    """

    @pytest.fixture
    async def role(self, client: AsyncClient, admin_headers: dict, unique_name: str) -> dict:
        role = await _create_role(client, admin_headers, f"scope-{unique_name}")
        yield role
        await client.delete(f"/api/admin/roles/{role['id']}", headers=admin_headers)

    @pytest.mark.parametrize(
        "resource,id_field",
        [
            ("source-groups", "source_group_id"),
            ("credentials", "credential_id"),
            ("sync-groups", "sync_group_id"),
            ("providers", "provider_id"),
        ],
    )
    async def test_scope_get_put_delete(
        self,
        client: AsyncClient,
        admin_headers: dict,
        role: dict,
        openapi_spec: dict,
        resource: str,
        id_field: str,
    ):
        role_id = role["id"]
        base = f"/api/admin/roles/{role_id}/scopes/{resource}"

        get_empty = await client.get(base, headers=admin_headers)
        assert_matches_openapi(get_empty, base, "get", openapi_spec)
        assert get_empty.status_code == 200
        assert get_empty.json()[f"{id_field}s"] == []

        # Empty-list PUT clears scope atomically (no FK insert).
        put = await client.put(base, headers=admin_headers, json={f"{id_field}s": []})
        assert_matches_openapi(put, base, "put", openapi_spec)
        assert put.status_code == 200
        assert put.json()[f"{id_field}s"] == []

        # DELETE is idempotent and never checks the referenced resource.
        delete = await client.delete(f"{base}/999999", headers=admin_headers)
        assert_matches_openapi(delete, f"{base}/{{{id_field}}}", "delete", openapi_spec)
        assert delete.status_code == 204

    async def test_add_scope_provider(
        self, client: AsyncClient, admin_headers: dict, role: dict, openapi_spec: dict
    ):
        base = f"/api/admin/roles/{role['id']}/scopes/providers"
        add = await client.post(base, headers=admin_headers, json={"provider_id": 1})
        assert_matches_openapi(add, base, "post", openapi_spec)
        assert add.status_code == 201
        assert add.json()["provider_ids"] == [1]

    async def test_add_scope_credential(
        self,
        client: AsyncClient,
        admin_headers: dict,
        role: dict,
        openapi_spec: dict,
        unique_name: str,
    ):
        cred = await client.post(
            "/api/credentials/",
            headers=admin_headers,
            json={
                "name": f"scope-cred-{unique_name}",
                "credential_type": "github_token",
                "provider": "github",
                "secret": "ghp_scope_secret",
            },
        )
        assert cred.status_code == 201
        credential_id = cred.json()["id"]
        try:
            base = f"/api/admin/roles/{role['id']}/scopes/credentials"
            add = await client.post(
                base, headers=admin_headers, json={"credential_id": credential_id}
            )
            assert_matches_openapi(add, base, "post", openapi_spec)
            assert add.status_code == 201
            assert add.json()["credential_ids"] == [credential_id]
        finally:
            await client.delete(f"/api/credentials/{credential_id}", headers=admin_headers)

    async def test_add_scope_sync_group(
        self,
        client: AsyncClient,
        admin_headers: dict,
        role: dict,
        openapi_spec: dict,
        unique_name: str,
    ):
        sg = await client.post(
            "/api/mirroring/sync-groups",
            headers=admin_headers,
            json={"name": f"scope-sg-{unique_name}"},
        )
        assert sg.status_code == 201
        sg_id = sg.json()["id"]
        try:
            base = f"/api/admin/roles/{role['id']}/scopes/sync-groups"
            add = await client.post(base, headers=admin_headers, json={"sync_group_id": sg_id})
            assert_matches_openapi(add, base, "post", openapi_spec)
            assert add.status_code == 201
            assert add.json()["sync_group_ids"] == [sg_id]
        finally:
            await client.delete(f"/api/mirroring/sync-groups/{sg_id}", headers=admin_headers)

    async def test_add_scope_source_group(
        self,
        client: AsyncClient,
        admin_headers: dict,
        role: dict,
        openapi_spec: dict,
        unique_name: str,
    ):
        # A github-typed source repository auto-creates its SourceGroup.
        repo = await client.post(
            "/api/mirroring/repositories",
            headers=admin_headers,
            json={
                "provider_type": "github",
                "clone_url": f"https://github.com/e2e-scope-{unique_name}/repo.git",
            },
        )
        assert repo.status_code == 201, repo.text
        repo_id = repo.json()["id"]
        group_id = repo.json()["source_group"]["id"]
        try:
            base = f"/api/admin/roles/{role['id']}/scopes/source-groups"
            add = await client.post(base, headers=admin_headers, json={"source_group_id": group_id})
            assert_matches_openapi(add, base, "post", openapi_spec)
            assert add.status_code == 201
            assert add.json()["source_group_ids"] == [group_id]
        finally:
            await client.delete(f"/api/mirroring/repositories/{repo_id}", headers=admin_headers)
            await client.delete(f"/api/mirroring/groups/{group_id}", headers=admin_headers)

    async def test_add_scope_requires_field(
        self, client: AsyncClient, admin_headers: dict, role: dict
    ):
        resp = await client.post(
            f"/api/admin/roles/{role['id']}/scopes/providers",
            headers=admin_headers,
            json={},
        )
        assert resp.status_code == 400


class TestAdminMaintenance:
    async def test_admin_cleanup_200(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.post("/api/admin/cleanup", headers=admin_headers)
        assert_matches_openapi(response, "/api/admin/cleanup", "post", openapi_spec)
        assert response.status_code == 200
