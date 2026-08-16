"""
@file test_readonly_apis.py
@description E2E tests for read-only admin/reporting/mirroring/schedule endpoints
              against a live backend. These endpoints return their current
              (possibly empty) state without external side effects, so they are
              exercised with the admin token and validated against the frozen
              OpenAPI contract. No mocks, no sqlite.
@dependencies backend/tests/e2e/conftest.py
"""

import pytest
from httpx import AsyncClient

from tests.e2e.conftest import assert_matches_openapi

pytestmark = pytest.mark.e2e


class TestHealth:
    async def test_health(self, client: AsyncClient, openapi_spec: dict):
        response = await client.get("/api/health")
        assert_matches_openapi(response, "/api/health", "get", openapi_spec)
        assert response.status_code == 200


class TestAdminReadOnly:
    async def test_list_permissions(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.get("/api/admin/permissions", headers=admin_headers)
        assert_matches_openapi(response, "/api/admin/permissions", "get", openapi_spec)
        assert response.status_code == 200

    async def test_list_roles(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.get("/api/admin/roles", headers=admin_headers)
        assert_matches_openapi(response, "/api/admin/roles", "get", openapi_spec)
        assert response.status_code == 200

    async def test_list_users(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.get("/api/admin/users", headers=admin_headers)
        assert_matches_openapi(response, "/api/admin/users", "get", openapi_spec)
        assert response.status_code == 200


class TestCredentialsReadOnly:
    async def test_list_credentials(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.get("/api/credentials/", headers=admin_headers)
        assert_matches_openapi(response, "/api/credentials/", "get", openapi_spec)
        assert response.status_code == 200


class TestReportsReadOnly:
    async def test_report_duplicates(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.get("/api/reports/duplicates", headers=admin_headers)
        assert_matches_openapi(response, "/api/reports/duplicates", "get", openapi_spec)
        assert response.status_code == 200

    async def test_report_status(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.get("/api/reports/status", headers=admin_headers)
        assert_matches_openapi(response, "/api/reports/status", "get", openapi_spec)
        assert response.status_code == 200

    async def test_report_storage(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.get("/api/reports/storage", headers=admin_headers)
        assert_matches_openapi(response, "/api/reports/storage", "get", openapi_spec)
        assert response.status_code == 200

    async def test_report_syncs(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.get("/api/reports/syncs", headers=admin_headers)
        assert_matches_openapi(response, "/api/reports/syncs", "get", openapi_spec)
        assert response.status_code == 200


class TestSchedulesReadOnly:
    async def test_list_build_schedules(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.get("/api/schedules/build", headers=admin_headers)
        assert_matches_openapi(response, "/api/schedules/build", "get", openapi_spec)
        assert response.status_code == 200

    async def test_list_sync_schedules(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.get("/api/schedules/sync", headers=admin_headers)
        assert_matches_openapi(response, "/api/schedules/sync", "get", openapi_spec)
        assert response.status_code == 200


class TestSystemReadOnly:
    async def test_system(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.get("/api/system", headers=admin_headers)
        assert_matches_openapi(response, "/api/system", "get", openapi_spec)
        assert response.status_code == 200


class TestMirroringReadOnly:
    async def test_list_mirroring_groups(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.get("/api/mirroring/groups", headers=admin_headers)
        assert_matches_openapi(response, "/api/mirroring/groups", "get", openapi_spec)
        assert response.status_code == 200

    async def test_list_mirrors(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.get("/api/mirroring/mirrors", headers=admin_headers)
        assert_matches_openapi(response, "/api/mirroring/mirrors", "get", openapi_spec)
        assert response.status_code == 200

    async def test_list_sync_groups(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.get("/api/mirroring/sync-groups", headers=admin_headers)
        assert_matches_openapi(
            response, "/api/mirroring/sync-groups", "get", openapi_spec
        )
        assert response.status_code == 200


class TestImagesReadOnly:
    async def test_list_app_images(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.get("/api/app-images", headers=admin_headers)
        assert_matches_openapi(response, "/api/app-images", "get", openapi_spec)
        assert response.status_code == 200
