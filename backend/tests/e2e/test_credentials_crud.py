"""
@file test_credentials_crud.py
@description E2E tests for Credentials CRUD (/api/credentials) against a live
              backend: create, get, patch, test and soft-delete. CRUD is pure
              DB I/O (secret encryption is local), with data isolation via
              unique names. No sqlite, no mocks.
@dependencies backend/tests/e2e/conftest.py
"""

import pytest
from httpx import AsyncClient

from tests.e2e.conftest import assert_matches_openapi

pytestmark = pytest.mark.e2e


class TestCredentialsCrud:
    async def test_crud_and_test(
        self, client: AsyncClient, admin_headers: dict, unique_name: str, openapi_spec: dict
    ):
        name = f"cred-{unique_name}"
        create = await client.post(
            "/api/credentials/",
            headers=admin_headers,
            json={
                "name": name,
                "credential_type": "github_token",
                "provider": "github",
                "username": "e2e-user",
                "secret": "ghp_e2e_secret_token",
            },
        )
        assert_matches_openapi(create, "/api/credentials/", "post", openapi_spec)
        assert create.status_code == 201
        created = create.json()
        assert created["name"] == name
        assert created["credential_type"] == "github_token"
        # secret is never returned
        assert "secret" not in created
        assert "encrypted_secret" not in created

        get = await client.get(
            f"/api/credentials/{created['id']}", headers=admin_headers
        )
        assert_matches_openapi(get, "/api/credentials/{credential_id}", "get", openapi_spec)
        assert get.status_code == 200
        assert get.json()["name"] == name

        patch = await client.patch(
            f"/api/credentials/{created['id']}",
            headers=admin_headers,
            json={"username": "e2e-user-renamed"},
        )
        assert_matches_openapi(
            patch, "/api/credentials/{credential_id}", "patch", openapi_spec
        )
        assert patch.status_code == 200
        assert patch.json()["username"] == "e2e-user-renamed"

        test = await client.post(
            f"/api/credentials/{created['id']}/test", headers=admin_headers
        )
        assert_matches_openapi(
            test, "/api/credentials/{credential_id}/test", "post", openapi_spec
        )
        assert test.status_code == 200
        assert test.json()["last_tested_at"] is not None

        delete = await client.delete(
            f"/api/credentials/{created['id']}", headers=admin_headers
        )
        assert_matches_openapi(
            delete, "/api/credentials/{credential_id}", "delete", openapi_spec
        )
        assert delete.status_code == 204

        # soft-deleted credential is no longer visible
        gone = await client.get(
            f"/api/credentials/{created['id']}", headers=admin_headers
        )
        assert gone.status_code == 404

