"""
@file test_image_details.py
@description E2E tests for image/docker detail endpoints against a live backend:
              gold/app image versions + build schedule (GET/PATCH), and docker
              source detail, compare, and sync schedules. Image/source creation
              is pure DB I/O (docker POST without image_name does not index), so
              these detail paths are exercised without external registry calls.
              Data isolation via unique names. No sqlite, no mocks.
@dependencies backend/tests/e2e/conftest.py
"""

import pytest
from httpx import AsyncClient

from tests.e2e.conftest import assert_matches_openapi

pytestmark = pytest.mark.e2e


class TestGoldImageDetails:
    async def test_versions_and_schedule(
        self, client: AsyncClient, admin_headers: dict, unique_name: str, openapi_spec: dict
    ):
        create = await client.post(
            "/api/gold-images",
            headers=admin_headers,
            json={
                "name": f"gold-detail-{unique_name}",
                "os_family": "alpine",
                "dockerfile": "FROM alpine:3.19",
            },
        )
        assert create.status_code == 201
        image_id = create.json()["id"]
        try:
            versions = await client.get(
                f"/api/gold-images/{image_id}/versions", headers=admin_headers
            )
            assert_matches_openapi(
                versions, "/api/gold-images/{image_id}/versions", "get", openapi_spec
            )
            assert versions.status_code == 200
            assert versions.json() == []

            schedule = await client.get(
                f"/api/gold-images/{image_id}/schedule", headers=admin_headers
            )
            assert_matches_openapi(
                schedule, "/api/gold-images/{image_id}/schedule", "get", openapi_spec
            )
            assert schedule.status_code == 200

            patch = await client.patch(
                f"/api/gold-images/{image_id}/schedule",
                headers=admin_headers,
                json={"is_enabled": False},
            )
            assert_matches_openapi(
                patch, "/api/gold-images/{image_id}/schedule", "patch", openapi_spec
            )
            assert patch.status_code == 200
            assert patch.json()["is_enabled"] is False
        finally:
            await client.delete(f"/api/gold-images/{image_id}", headers=admin_headers)


class TestAppImageDetails:
    async def test_versions_and_schedule(
        self, client: AsyncClient, admin_headers: dict, unique_name: str, openapi_spec: dict
    ):
        create = await client.post(
            "/api/app-images",
            headers=admin_headers,
            json={
                "name": f"app-detail-{unique_name}",
                "dockerfile": "FROM scratch",
            },
        )
        assert create.status_code == 201
        image_id = create.json()["id"]
        try:
            versions = await client.get(
                f"/api/app-images/{image_id}/versions", headers=admin_headers
            )
            assert_matches_openapi(
                versions, "/api/app-images/{image_id}/versions", "get", openapi_spec
            )
            assert versions.status_code == 200
            assert versions.json() == []

            schedule = await client.get(
                f"/api/app-images/{image_id}/schedule", headers=admin_headers
            )
            assert_matches_openapi(
                schedule, "/api/app-images/{image_id}/schedule", "get", openapi_spec
            )
            assert schedule.status_code == 200

            patch = await client.patch(
                f"/api/app-images/{image_id}/schedule",
                headers=admin_headers,
                json={"is_enabled": False},
            )
            assert_matches_openapi(
                patch, "/api/app-images/{image_id}/schedule", "patch", openapi_spec
            )
            assert patch.status_code == 200
            assert patch.json()["is_enabled"] is False
        finally:
            await client.delete(f"/api/app-images/{image_id}", headers=admin_headers)


class TestDockerImageDetails:
    async def test_detail_compare_and_schedule(
        self, client: AsyncClient, admin_headers: dict, unique_name: str, openapi_spec: dict
    ):
        source_a = await client.post(
            "/api/docker-images",
            headers=admin_headers,
            json={"name": f"docker-detail-a-{unique_name}", "registry_url": "https://registry.example.com"},
        )
        assert source_a.status_code == 201
        source_b = await client.post(
            "/api/docker-images",
            headers=admin_headers,
            json={"name": f"docker-detail-b-{unique_name}", "registry_url": "https://registry.example.com"},
        )
        assert source_b.status_code == 201
        source_a_id = source_a.json()["id"]
        source_b_id = source_b.json()["id"]
        try:
            detail = await client.get(
                f"/api/docker-images/{source_a_id}", headers=admin_headers
            )
            assert_matches_openapi(
                detail, "/api/docker-images/{source_id}", "get", openapi_spec
            )
            assert detail.status_code == 200

            compare = await client.get(
                f"/api/docker-images/{source_a_id}/compare/{source_b_id}",
                headers=admin_headers,
            )
            assert_matches_openapi(
                compare,
                "/api/docker-images/{source_id}/compare/{other_source_id}",
                "get",
                openapi_spec,
            )
            assert compare.status_code == 200
            assert compare.json()["summary"]["total_tags"] == 0

            # Schedule CRUD (create → get → patch → delete).
            sched_create = await client.post(
                f"/api/docker-images/{source_a_id}/schedule",
                headers=admin_headers,
                json={"is_enabled": True, "use_default_schedule": True},
            )
            assert_matches_openapi(
                sched_create, "/api/docker-images/{source_id}/schedule", "post", openapi_spec
            )
            assert sched_create.status_code == 201
            schedule_id = sched_create.json()["id"]

            sched_get = await client.get(
                f"/api/docker-images/{source_a_id}/schedule", headers=admin_headers
            )
            assert_matches_openapi(
                sched_get, "/api/docker-images/{source_id}/schedule", "get", openapi_spec
            )
            assert sched_get.status_code == 200

            sched_patch = await client.patch(
                f"/api/docker-images/{source_a_id}/schedule/{schedule_id}",
                headers=admin_headers,
                json={"is_enabled": False},
            )
            assert_matches_openapi(
                sched_patch,
                "/api/docker-images/{source_id}/schedule/{schedule_id}",
                "patch",
                openapi_spec,
            )
            assert sched_patch.status_code == 200

            sched_delete = await client.delete(
                f"/api/docker-images/{source_a_id}/schedule/{schedule_id}",
                headers=admin_headers,
            )
            assert_matches_openapi(
                sched_delete,
                "/api/docker-images/{source_id}/schedule/{schedule_id}",
                "delete",
                openapi_spec,
            )
            assert sched_delete.status_code == 204

            # httpx's delete() does not accept a JSON body — use request().
            batch_delete = await client.request(
                "DELETE",
                f"/api/docker-images/{source_a_id}/tags/batch",
                headers=admin_headers,
                json={"tag_ids": [999999]},
            )
            assert_matches_openapi(
                batch_delete,
                "/api/docker-images/{source_id}/tags/batch",
                "delete",
                openapi_spec,
            )
            assert batch_delete.status_code == 204
        finally:
            await client.delete(f"/api/docker-images/{source_a_id}", headers=admin_headers)
            await client.delete(f"/api/docker-images/{source_b_id}", headers=admin_headers)
