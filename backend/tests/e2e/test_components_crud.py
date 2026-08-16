"""
@file test_components_crud.py
@description E2E tests for GitLab Component CRUD (/api/components) against a live
              backend. Component registration is pure DB I/O (the provider_id FK
              only needs an existing resource_providers row), so full CRUD is
              exercised with data isolation via unique names. No sqlite, no mocks.
@dependencies backend/tests/e2e/conftest.py
"""

import pytest
from httpx import AsyncClient

from tests.e2e.conftest import assert_matches_openapi

pytestmark = pytest.mark.e2e


class TestComponentsCrud:
    async def test_crud(
        self, client: AsyncClient, admin_headers: dict, unique_name: str, openapi_spec: dict
    ):
        name = f"component-{unique_name}"
        create = await client.post(
            "/api/components",
            headers=admin_headers,
            json={
                "name": name,
                "provider_id": 1,
                "project_path": "e2e/project",
                "component_path": ".gitlab/components/e2e.yml",
            },
        )
        assert_matches_openapi(create, "/api/components", "post", openapi_spec)
        assert create.status_code == 201
        created = create.json()
        assert created["name"] == name

        get = await client.get(f"/api/components/{created['id']}", headers=admin_headers)
        assert_matches_openapi(get, "/api/components/{component_id}", "get", openapi_spec)
        assert get.status_code == 200
        assert get.json()["name"] == name

        patch = await client.patch(
            f"/api/components/{created['id']}",
            headers=admin_headers,
            json={"description": "updated"},
        )
        assert_matches_openapi(patch, "/api/components/{component_id}", "patch", openapi_spec)
        assert patch.status_code == 200
        assert patch.json()["description"] == "updated"

        delete = await client.delete(
            f"/api/components/{created['id']}", headers=admin_headers
        )
        assert_matches_openapi(delete, "/api/components/{component_id}", "delete", openapi_spec)
        assert delete.status_code == 204
