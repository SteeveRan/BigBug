"""
@file test_mirroring_repositories.py
@description E2E tests for the mirroring SourceRepository API
              (/api/mirroring/repositories) against a live backend. A
              github-typed repository is created (pure DB I/O, auto-creating its
              SourceGroup), then exercised through detail/readme/releases and
              soft-delete/restore. The documented 422 paths (invalid integer
              path params and empty-body create) are covered without external
              calls. No mocks, no sqlite.
@dependencies backend/tests/e2e/conftest.py
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.e2e.conftest import assert_matches_openapi

pytestmark = pytest.mark.e2e


class TestSourceRepositoryCrud:
    async def test_repository_crud(
        self, client: AsyncClient, admin_headers: dict, unique_name: str, openapi_spec: dict
    ):
        org = f"e2e-org-{unique_name}"
        create_repo = await client.post(
            "/api/mirroring/repositories",
            headers=admin_headers,
            json={"provider_type": "github", "clone_url": f"https://github.com/{org}/repo.git"},
        )
        assert_matches_openapi(create_repo, "/api/mirroring/repositories", "post", openapi_spec)
        assert create_repo.status_code == 201
        repo_id = create_repo.json()["id"]
        group_id = create_repo.json()["source_group"]["id"]

        try:
            get_repo = await client.get(
                f"/api/mirroring/repositories/{repo_id}", headers=admin_headers
            )
            assert_matches_openapi(
                get_repo, "/api/mirroring/repositories/{repository_id}", "get", openapi_spec
            )
            assert get_repo.status_code == 200

            readme = await client.get(
                f"/api/mirroring/repositories/{repo_id}/readme", headers=admin_headers
            )
            assert_matches_openapi(
                readme, "/api/mirroring/repositories/{repository_id}/readme", "get", openapi_spec
            )
            assert readme.status_code == 200

            releases = await client.get(
                f"/api/mirroring/repositories/{repo_id}/releases", headers=admin_headers
            )
            assert_matches_openapi(
                releases,
                "/api/mirroring/repositories/{repository_id}/releases",
                "get",
                openapi_spec,
            )
            assert releases.status_code == 200

            del_repo = await client.delete(
                f"/api/mirroring/repositories/{repo_id}", headers=admin_headers
            )
            assert_matches_openapi(
                del_repo, "/api/mirroring/repositories/{repository_id}", "delete", openapi_spec
            )
            assert del_repo.status_code == 204

            restore_repo = await client.post(
                f"/api/mirroring/repositories/{repo_id}/restore", headers=admin_headers
            )
            assert_matches_openapi(
                restore_repo,
                "/api/mirroring/repositories/{repository_id}/restore",
                "post",
                openapi_spec,
            )
            assert restore_repo.status_code == 200
        finally:
            await client.delete(f"/api/mirroring/repositories/{repo_id}", headers=admin_headers)
            await client.delete(f"/api/mirroring/groups/{group_id}", headers=admin_headers)


class TestSourceRepositoryValidation:
    """Documented 422 validation paths (invalid path params / empty body)."""

    @pytest.mark.parametrize(
        ("method", "url", "template"),
        [
            (
                "get",
                "/api/mirroring/repositories/abc",
                "/api/mirroring/repositories/{repository_id}",
            ),
            (
                "get",
                "/api/mirroring/repositories/abc/readme",
                "/api/mirroring/repositories/{repository_id}/readme",
            ),
            (
                "get",
                "/api/mirroring/repositories/abc/releases",
                "/api/mirroring/repositories/{repository_id}/releases",
            ),
            (
                "delete",
                "/api/mirroring/repositories/abc",
                "/api/mirroring/repositories/{repository_id}",
            ),
            (
                "post",
                "/api/mirroring/repositories/abc/refresh",
                "/api/mirroring/repositories/{repository_id}/refresh",
            ),
            (
                "post",
                "/api/mirroring/repositories/abc/restore",
                "/api/mirroring/repositories/{repository_id}/restore",
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
        body = {} if method == "post" else None
        response = await client.request(method, url, headers=admin_headers, json=body)
        assert_matches_openapi(response, template, method, openapi_spec)
        assert response.status_code == 422

    async def test_create_empty_body_422(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.post("/api/mirroring/repositories", headers=admin_headers, json={})
        assert_matches_openapi(response, "/api/mirroring/repositories", "post", openapi_spec)
        assert response.status_code == 422
