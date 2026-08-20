"""
@file test_pipeline_configs_crud.py
@description E2E tests for Pipeline configuration CRUD (/api/pipelines/configs)
              against a live backend. Configs are pure DB I/O (no GitLab call),
              with soft-delete/restore/duplicate exercised and data isolation via
              unique names. No sqlite, no mocks.
@dependencies backend/tests/e2e/conftest.py
"""

import pytest
from httpx import AsyncClient

from tests.e2e.conftest import assert_matches_openapi

pytestmark = pytest.mark.e2e


class TestPipelineConfigsCrud:
    async def test_crud_duplicate_restore(
        self, client: AsyncClient, admin_headers: dict, unique_name: str, openapi_spec: dict
    ):
        name = f"pipeline-{unique_name}"
        create = await client.post(
            "/api/pipelines/configs",
            headers=admin_headers,
            json={"name": name, "description": "e2e pipeline"},
        )
        assert_matches_openapi(create, "/api/pipelines/configs", "post", openapi_spec)
        assert create.status_code == 201
        created = create.json()
        assert created["name"] == name
        pipeline_id = created["id"]

        get = await client.get(f"/api/pipelines/configs/{pipeline_id}", headers=admin_headers)
        assert_matches_openapi(get, "/api/pipelines/configs/{pipeline_id}", "get", openapi_spec)
        assert get.status_code == 200

        patch = await client.patch(
            f"/api/pipelines/configs/{pipeline_id}",
            headers=admin_headers,
            json={"description": "updated"},
        )
        assert_matches_openapi(patch, "/api/pipelines/configs/{pipeline_id}", "patch", openapi_spec)
        assert patch.status_code == 200
        assert patch.json()["description"] == "updated"

        dup = await client.post(
            f"/api/pipelines/configs/{pipeline_id}/duplicate",
            headers=admin_headers,
            json={"name": f"{name}-copy"},
        )
        assert_matches_openapi(
            dup,
            "/api/pipelines/configs/{pipeline_id}/duplicate",
            "post",
            openapi_spec,
        )
        assert dup.status_code == 200
        dup_id = dup.json()["id"]
        assert dup.json()["name"] == f"{name}-copy"
        assert dup.json()["is_default"] is False

        # Clean up the duplicate first (it may be soft-deleted, no references).
        await client.delete(f"/api/pipelines/configs/{dup_id}", headers=admin_headers)

        delete = await client.delete(f"/api/pipelines/configs/{pipeline_id}", headers=admin_headers)
        assert_matches_openapi(
            delete, "/api/pipelines/configs/{pipeline_id}", "delete", openapi_spec
        )
        assert delete.status_code == 204

        restore = await client.post(
            f"/api/pipelines/configs/{pipeline_id}/restore", headers=admin_headers
        )
        assert_matches_openapi(
            restore,
            "/api/pipelines/configs/{pipeline_id}/restore",
            "post",
            openapi_spec,
        )
        assert restore.status_code == 200
        assert restore.json()["is_deleted"] is False

        # Final cleanup: soft-delete again to leave no trace.
        await client.delete(f"/api/pipelines/configs/{pipeline_id}", headers=admin_headers)

    async def test_create_duplicate_name_409(
        self, client: AsyncClient, admin_headers: dict, unique_name: str
    ):
        name = f"pipeline-dup-{unique_name}"
        first = await client.post(
            "/api/pipelines/configs",
            headers=admin_headers,
            json={"name": name},
        )
        assert first.status_code == 201
        try:
            second = await client.post(
                "/api/pipelines/configs",
                headers=admin_headers,
                json={"name": name},
            )
            assert second.status_code == 409
        finally:
            await client.delete(
                f"/api/pipelines/configs/{first.json()['id']}", headers=admin_headers
            )
