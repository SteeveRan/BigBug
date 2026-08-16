"""
@file test_sync_groups_crud.py
@description E2E tests for SyncGroup CRUD (/api/mirroring/sync-groups) against a
              live backend. SyncGroup create/read/update/soft-delete/restore are
              pure DB I/O; apply-pipeline needs an existing pipeline config and
              bulk-mirror-assignment validates mirror IDs. Data isolation via
              unique names. No sqlite, no mocks.
@dependencies backend/tests/e2e/conftest.py
"""

import pytest
from httpx import AsyncClient

from tests.e2e.conftest import assert_matches_openapi

pytestmark = pytest.mark.e2e


class TestSyncGroupsCrud:
    async def test_crud_restore_and_apply_pipeline(
        self, client: AsyncClient, admin_headers: dict, unique_name: str, openapi_spec: dict
    ):
        name = f"sg-{unique_name}"
        create = await client.post(
            "/api/mirroring/sync-groups",
            headers=admin_headers,
            json={"name": name, "description": "e2e sync group"},
        )
        assert_matches_openapi(create, "/api/mirroring/sync-groups", "post", openapi_spec)
        assert create.status_code == 201
        created = create.json()
        assert created["name"] == name
        group_id = created["id"]

        get = await client.get(f"/api/mirroring/sync-groups/{group_id}", headers=admin_headers)
        assert_matches_openapi(
            get, "/api/mirroring/sync-groups/{group_id}", "get", openapi_spec
        )
        assert get.status_code == 200

        patch = await client.patch(
            f"/api/mirroring/sync-groups/{group_id}",
            headers=admin_headers,
            json={"description": "updated"},
        )
        assert_matches_openapi(
            patch, "/api/mirroring/sync-groups/{group_id}", "patch", openapi_spec
        )
        assert patch.status_code == 200
        assert patch.json()["description"] == "updated"

        # Create a pipeline config to apply.
        pipeline = await client.post(
            "/api/pipelines/configs",
            headers=admin_headers,
            json={"name": f"sgpipeline-{unique_name}"},
        )
        assert pipeline.status_code == 201
        pipeline_id = pipeline.json()["id"]

        apply = await client.post(
            f"/api/mirroring/sync-groups/{group_id}/apply-pipeline",
            headers=admin_headers,
            json={"pipeline_id": pipeline_id},
        )
        assert_matches_openapi(
            apply,
            "/api/mirroring/sync-groups/{group_id}/apply-pipeline",
            "post",
            openapi_spec,
        )
        assert apply.status_code == 200
        assert apply.json()["pipeline_id"] == pipeline_id

        delete = await client.delete(
            f"/api/mirroring/sync-groups/{group_id}", headers=admin_headers
        )
        assert_matches_openapi(
            delete, "/api/mirroring/sync-groups/{group_id}", "delete", openapi_spec
        )
        assert delete.status_code == 204

        restore = await client.post(
            f"/api/mirroring/sync-groups/{group_id}/restore", headers=admin_headers
        )
        assert_matches_openapi(
            restore,
            "/api/mirroring/sync-groups/{group_id}/restore",
            "post",
            openapi_spec,
        )
        assert restore.status_code == 200
        assert restore.json()["is_deleted"] is False

        # Cleanup: delete group again, then pipeline.
        await client.delete(f"/api/mirroring/sync-groups/{group_id}", headers=admin_headers)
        await client.delete(
            f"/api/pipelines/configs/{pipeline_id}", headers=admin_headers
        )

    async def test_bulk_assign_mirrors_empty(
        self, client: AsyncClient, admin_headers: dict, unique_name: str, openapi_spec: dict
    ):
        name = f"sg-empty-{unique_name}"
        create = await client.post(
            "/api/mirroring/sync-groups",
            headers=admin_headers,
            json={"name": name},
        )
        assert create.status_code == 201
        group_id = create.json()["id"]
        try:
            # AssignMirrorsRequest requires min_length=1 → empty list is 422.
            bulk = await client.post(
                f"/api/mirroring/sync-groups/{group_id}/mirrors/bulk",
                headers=admin_headers,
                json={"mirror_ids": []},
            )
            assert_matches_openapi(
                bulk,
                "/api/mirroring/sync-groups/{group_id}/mirrors/bulk",
                "post",
                openapi_spec,
            )
            assert bulk.status_code == 422
        finally:
            await client.delete(f"/api/mirroring/sync-groups/{group_id}", headers=admin_headers)

    async def test_create_duplicate_name_409(
        self, client: AsyncClient, admin_headers: dict, unique_name: str
    ):
        name = f"sg-dup-{unique_name}"
        first = await client.post(
            "/api/mirroring/sync-groups",
            headers=admin_headers,
            json={"name": name},
        )
        assert first.status_code == 201
        try:
            second = await client.post(
                "/api/mirroring/sync-groups",
                headers=admin_headers,
                json={"name": name},
            )
            assert second.status_code == 409
        finally:
            await client.delete(
                f"/api/mirroring/sync-groups/{first.json()['id']}", headers=admin_headers
            )
