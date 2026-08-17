"""
@file test_mirroring_groups.py
@description E2E tests for the mirroring SourceGroup API (/api/mirroring/groups)
              against a live backend. A github-typed source repository auto-creates
              its SourceGroup, which is then exercised through detail/repositories
              and soft-delete/restore — all pure DB I/O. groups/import requires a
              provider_id query param, so its missing-query 422 path is also covered.
              No mocks, no sqlite.
@dependencies backend/tests/e2e/conftest.py
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.e2e.conftest import assert_matches_openapi

pytestmark = pytest.mark.e2e


class TestSourceGroupCrud:
    async def test_group_crud(
        self, client: AsyncClient, admin_headers: dict, unique_name: str, openapi_spec: dict
    ):
        org = f"e2e-org-{unique_name}"
        create_repo = await client.post(
            "/api/mirroring/repositories",
            headers=admin_headers,
            json={"provider_type": "github", "clone_url": f"https://github.com/{org}/repo.git"},
        )
        assert create_repo.status_code == 201, create_repo.text
        repo_id = create_repo.json()["id"]
        group_id = create_repo.json()["source_group"]["id"]

        try:
            get_group = await client.get(f"/api/mirroring/groups/{group_id}", headers=admin_headers)
            assert_matches_openapi(
                get_group, "/api/mirroring/groups/{group_id}", "get", openapi_spec
            )
            assert get_group.status_code == 200

            list_repos = await client.get(
                f"/api/mirroring/groups/{group_id}/repositories", headers=admin_headers
            )
            assert_matches_openapi(
                list_repos,
                "/api/mirroring/groups/{group_id}/repositories",
                "get",
                openapi_spec,
            )
            assert list_repos.status_code == 200

            del_group = await client.delete(
                f"/api/mirroring/groups/{group_id}", headers=admin_headers
            )
            assert_matches_openapi(
                del_group, "/api/mirroring/groups/{group_id}", "delete", openapi_spec
            )
            assert del_group.status_code == 204

            restore_group = await client.post(
                f"/api/mirroring/groups/{group_id}/restore", headers=admin_headers
            )
            assert_matches_openapi(
                restore_group,
                "/api/mirroring/groups/{group_id}/restore",
                "post",
                openapi_spec,
            )
            assert restore_group.status_code == 200
        finally:
            await client.delete(f"/api/mirroring/repositories/{repo_id}", headers=admin_headers)
            await client.delete(f"/api/mirroring/groups/{group_id}", headers=admin_headers)


class TestSourceGroupImportValidation:
    async def test_groups_import_missing_query_422(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.post("/api/mirroring/groups/import", headers=admin_headers)
        assert_matches_openapi(response, "/api/mirroring/groups/import", "post", openapi_spec)
        assert response.status_code == 422
