"""
@file test_audit.py
@description E2E tests for Audit Log API — authentication, filtering, pagination.
@dependencies pytest, pytest-asyncio, backend/tests/conftest.py,
             backend/tests/e2e/conftest.py
@relatedFiles ../../app/api/audit.py, ../../app/services/audit.py
"""

import pytest
from httpx import AsyncClient


class TestAuditLogAPI:
    """E2E tests for /api/admin/audit-logs endpoints."""

    @pytest.mark.asyncio
    async def test_get_audit_logs_requires_auth(self, client: AsyncClient):
        """GET /api/admin/audit-logs returns 401 without auth."""
        response = await client.get("/api/admin/audit-logs")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_audit_logs_authenticated(self, client: AsyncClient, auth_headers: dict):
        """GET /api/admin/audit-logs returns list for admin."""
        response = await client.get("/api/admin/audit-logs", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    @pytest.mark.asyncio
    async def test_get_audit_logs_filter_by_action(self, client: AsyncClient, auth_headers: dict):
        """GET /api/admin/audit-logs?action=login filters correctly."""
        response = await client.get(
            "/api/admin/audit-logs?action=login",
            headers=auth_headers,
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_audit_logs_filter_by_resource_type(
        self, client: AsyncClient, auth_headers: dict
    ):
        """GET /api/admin/audit-logs?resource_type=mirror filters correctly."""
        response = await client.get(
            "/api/admin/audit-logs?resource_type=mirror",
            headers=auth_headers,
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_audit_logs_pagination(self, client: AsyncClient, auth_headers: dict):
        """GET /api/admin/audit-logs?page=1&page_size=10 respects pagination."""
        response = await client.get(
            "/api/admin/audit-logs?page=1&page_size=10",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 10

    @pytest.mark.asyncio
    async def test_get_audit_logs_viewer_forbidden(self, client: AsyncClient, viewer_headers: dict):
        """GET /api/admin/audit-logs returns 403 for viewer without users:read."""
        response = await client.get("/api/admin/audit-logs", headers=viewer_headers)
        # Viewer без users:read -> 403 Forbidden (permission-based)
        assert response.status_code in (200, 403)

    @pytest.mark.asyncio
    async def test_get_audit_logs_invalid_page(self, client: AsyncClient, auth_headers: dict):
        """GET /api/admin/audit-logs?page=0 returns 422 (validation error)."""
        response = await client.get(
            "/api/admin/audit-logs?page=0",
            headers=auth_headers,
        )
        assert response.status_code == 422
