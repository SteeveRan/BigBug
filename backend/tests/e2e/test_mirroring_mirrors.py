"""
@file test_mirroring_mirrors.py
@description E2E tests for the mirroring Mirror API (/api/mirroring/mirrors)
              against a live backend. Mirror creation triggers a GitLab pipeline
              (external side effect), so these tests only cover the documented
              422 validation paths (invalid integer path params and empty-body
              POSTs) plus the sync-group legacy endpoints. No mocks, no sqlite.
@dependencies backend/tests/e2e/conftest.py
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.e2e.conftest import assert_matches_openapi

pytestmark = pytest.mark.e2e


class TestMirrorValidation:
    """Documented 422 validation paths (invalid path params)."""

    @pytest.mark.parametrize(
        ("method", "url", "template"),
        [
            ("get", "/api/mirroring/mirrors/abc", "/api/mirroring/mirrors/{mirror_id}"),
            ("get", "/api/mirroring/mirrors/abc/logs", "/api/mirroring/mirrors/{mirror_id}/logs"),
            ("patch", "/api/mirroring/mirrors/abc", "/api/mirroring/mirrors/{mirror_id}"),
            ("delete", "/api/mirroring/mirrors/abc", "/api/mirroring/mirrors/{mirror_id}"),
            ("post", "/api/mirroring/mirrors/abc/sync", "/api/mirroring/mirrors/{mirror_id}/sync"),
            (
                "post",
                "/api/mirroring/mirrors/abc/freshness",
                "/api/mirroring/mirrors/{mirror_id}/freshness",
            ),
            (
                "post",
                "/api/mirroring/mirrors/abc/integrity-check",
                "/api/mirroring/mirrors/{mirror_id}/integrity-check",
            ),
            (
                "post",
                "/api/mirroring/mirrors/abc/restore",
                "/api/mirroring/mirrors/{mirror_id}/restore",
            ),
        ],
    )
    async def test_invalid_path_param_422(
        self,
        client: AsyncClient,
        admin_headers: dict,
        openapi_spec: dict,
        method: str,
        url: str,
        template: str,
    ):
        body = {} if method in ("post", "patch") else None
        response = await client.request(method, url, headers=admin_headers, json=body)
        assert_matches_openapi(response, template, method, openapi_spec)
        assert response.status_code == 422

    @pytest.mark.parametrize(
        ("url", "template"),
        [
            ("/api/mirroring/mirrors", "/api/mirroring/mirrors"),
            ("/api/mirroring/mirrors/bulk", "/api/mirroring/mirrors/bulk"),
            (
                "/api/mirroring/mirrors/check-duplicates",
                "/api/mirroring/mirrors/check-duplicates",
            ),
            ("/api/mirroring/mirrors/import", "/api/mirroring/mirrors/import"),
        ],
    )
    async def test_empty_body_422(
        self,
        client: AsyncClient,
        admin_headers: dict,
        openapi_spec: dict,
        url: str,
        template: str,
    ):
        response = await client.post(url, headers=admin_headers, json={})
        assert_matches_openapi(response, template, "post", openapi_spec)
        assert response.status_code == 422


class TestLegacySyncGroupValidation:
    async def test_get_sync_group_invalid_path_param_422(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.get("/api/sync-group/abc", headers=admin_headers)
        assert_matches_openapi(response, "/api/sync-group/{sync_group_id}", "get", openapi_spec)
        assert response.status_code == 422
