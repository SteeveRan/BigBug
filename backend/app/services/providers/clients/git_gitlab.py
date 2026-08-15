"""
@file git_gitlab.py
@description Thin GitLab client for provider actions (test_connection, list_groups,
             list_repositories, get_commit). Uses httpx against the GitLab REST API.
@dependencies httpx, ./_http
@relatedFiles ./git_github.py, ./git_generic.py
"""

from __future__ import annotations

import httpx

from app.services.providers.clients._http import ProviderClientError, make_client


class GitLabClient:
    def __init__(
        self,
        base_url: str,
        secret: str | None = None,
        verify_ssl: bool = True,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._secret = secret
        self._verify_ssl = verify_ssl
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        headers = {"User-Agent": "BigBug/1.0"}
        if self._secret:
            headers["PRIVATE-TOKEN"] = self._secret
        return make_client(
            verify_ssl=self._verify_ssl,
            transport=self._transport,
            headers=headers,
        )

    async def test_connection(self) -> dict:
        try:
            async with self._client() as client:
                resp = await client.get(f"{self.base_url}/api/v4/version")
        except httpx.RequestError as exc:
            raise ProviderClientError(f"GitLab request failed: {exc}") from exc
        if resp.is_success:
            return {"ok": True, "version": resp.json().get("version")}
        raise ProviderClientError(
            f"GitLab returned HTTP {resp.status_code}", status_code=resp.status_code
        )

    async def list_groups(self) -> list[dict]:
        try:
            async with self._client() as client:
                resp = await client.get(f"{self.base_url}/api/v4/groups")
        except httpx.RequestError as exc:
            raise ProviderClientError(f"GitLab request failed: {exc}") from exc
        if resp.is_success:
            return [
                {"id": str(g.get("id")), "name": g.get("name"), "full_path": g.get("full_path")}
                for g in resp.json()
            ]
        raise ProviderClientError(
            f"GitLab returned HTTP {resp.status_code}", status_code=resp.status_code
        )

    async def list_repositories(self, group_external_id: str) -> list[dict]:
        try:
            async with self._client() as client:
                resp = await client.get(
                    f"{self.base_url}/api/v4/groups/{group_external_id}/projects"
                )
        except httpx.RequestError as exc:
            raise ProviderClientError(f"GitLab request failed: {exc}") from exc
        if resp.is_success:
            return [
                {
                    "id": str(p.get("id")),
                    "name": p.get("name"),
                    "path_with_namespace": p.get("path_with_namespace"),
                    "http_url_to_repo": p.get("http_url_to_repo"),
                }
                for p in resp.json()
            ]
        raise ProviderClientError(
            f"GitLab returned HTTP {resp.status_code}", status_code=resp.status_code
        )

    async def get_commit(self, repo_external_id: str, ref: str | None = None) -> dict:
        params = {}
        if ref:
            params["ref_name"] = ref
        try:
            async with self._client() as client:
                resp = await client.get(
                    f"{self.base_url}/api/v4/projects/{repo_external_id}/repository/commits",
                    params=params,
                )
        except httpx.RequestError as exc:
            raise ProviderClientError(f"GitLab request failed: {exc}") from exc
        if resp.is_success:
            data = resp.json()
            if not data:
                return {}
            commit = data[0]
            return {
                "sha": commit.get("id"),
                "message": commit.get("title"),
                "author": commit.get("author_name"),
            }
        raise ProviderClientError(
            f"GitLab returned HTTP {resp.status_code}", status_code=resp.status_code
        )
