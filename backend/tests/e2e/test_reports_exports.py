"""
@file test_reports_exports.py
@description E2E tests for Reports export/bulk endpoints (/api/reports) against a
              live backend. The export endpoints return CSV/JSON downloads, the
              storage refresh touches GitLab (empty when no mirrors), and the
              bulk operations are pure DB I/O over empty mirror sets. No sqlite,
              no mocks.
@dependencies backend/tests/e2e/conftest.py
"""

import pytest
from httpx import AsyncClient

from tests.e2e.conftest import assert_matches_openapi

pytestmark = pytest.mark.e2e


class TestReportsExports:
    @pytest.mark.parametrize(
        "path",
        [
            "/api/reports/duplicates/export",
            "/api/reports/status/export",
            "/api/reports/storage/export",
            "/api/reports/syncs/export",
        ],
    )
    async def test_export(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict, path: str
    ):
        # Export endpoints default to CSV (raw text); request JSON so the
        # OpenAPI contract validator can parse ``response.json()``.
        response = await client.get(path, headers=admin_headers, params={"format": "json"})
        assert_matches_openapi(response, path, "get", openapi_spec)
        assert response.status_code == 200

    async def test_storage_refresh(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.post("/api/reports/storage/refresh", headers=admin_headers)
        assert_matches_openapi(response, "/api/reports/storage/refresh", "post", openapi_spec)
        assert response.status_code == 200


class TestReportsBulk:
    async def test_bulk_reassign_sync_group(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.post(
            "/api/reports/bulk/reassign-sync-group",
            headers=admin_headers,
            json={"mirror_ids": [999999], "sync_group_id": 1},
        )
        assert_matches_openapi(
            response, "/api/reports/bulk/reassign-sync-group", "post", openapi_spec
        )
        assert response.status_code == 200

    async def test_bulk_change_target_gitlab(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.post(
            "/api/reports/bulk/change-target-gitlab",
            headers=admin_headers,
            json={"mirror_ids": [999999], "sync_group_id": 1},
        )
        assert_matches_openapi(
            response, "/api/reports/bulk/change-target-gitlab", "post", openapi_spec
        )
        assert response.status_code == 200

    async def test_bulk_apply_pipeline(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.post(
            "/api/reports/bulk/apply-pipeline",
            headers=admin_headers,
            json={"mirror_ids": [999999], "pipeline_id": 1},
        )
        assert_matches_openapi(response, "/api/reports/bulk/apply-pipeline", "post", openapi_spec)
        assert response.status_code == 200
