"""
@file git_github.py
@description Thin GitHub client for provider actions (test_connection, list_groups,
             list_repositories, get_commit). Uses httpx against the GitHub REST API.
@dependencies httpx, ./_http
@relatedFiles ./git_gitlab.py, ./git_generic.py
"""

from __future__ import annotations

import httpx

from app.services.providers.clients._http import ProviderClientError, make_client


class GitHubClient:
    def __init__(
        self,
        api_url: str = "https://api.github.com",
        secret: str | None = None,
        verify_ssl: bool = True,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self._secret = secret
        self._verify_ssl = verify_ssl
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "BigBug/1.0",
        }
        if self._secret:
            headers["Authorization"] = f"Bearer {self._secret}"
        return make_client(
            verify_ssl=self._verify_ssl,
            transport=self._transport,
            headers=headers,
        )

    async def test_connection(self) -> dict:
        try:
            async with self._client() as client:
                resp = await client.get(f"{self.api_url}/rate_limit")
        except httpx.RequestError as exc:
            raise ProviderClientError(f"GitHub request failed: {exc}") from exc
        if resp.is_success:
            return {"ok": True, "rate_limit": resp.json().get("rate", {})}
        raise ProviderClientError(
            f"GitHub returned HTTP {resp.status_code}", status_code=resp.status_code
        )

    async def list_groups(self) -> list[dict]:
        items: list[dict] = []
        try:
            async with self._client() as client:
                resp = await client.get(f"{self.api_url}/user/orgs")
        except httpx.RequestError as exc:
            raise ProviderClientError(f"GitHub request failed: {exc}") from exc
        if resp.is_success:
            for org in resp.json():
                items.append({"id": str(org.get("id")), "name": org.get("login")})
            return items
        raise ProviderClientError(
            f"GitHub returned HTTP {resp.status_code}", status_code=resp.status_code
        )

    async def list_repositories(self, group_external_id: str) -> list[dict]:
        items: list[dict] = []
        try:
            async with self._client() as client:
                resp = await client.get(f"{self.api_url}/orgs/{group_external_id}/repos")
        except httpx.RequestError as exc:
            raise ProviderClientError(f"GitHub request failed: {exc}") from exc
        if resp.is_success:
            for repo in resp.json():
                items.append(
                    {
                        "id": str(repo.get("id")),
                        "name": repo.get("name"),
                        "full_name": repo.get("full_name"),
                        "clone_url": repo.get("clone_url"),
                    }
                )
            return items
        raise ProviderClientError(
            f"GitHub returned HTTP {resp.status_code}", status_code=resp.status_code
        )

    async def get_commit(self, repo_external_id: str, ref: str | None = None) -> dict:
        path = f"{self.api_url}/repos/{repo_external_id}/commits"
        params = {"per_page": 1}
        if ref:
            params["sha"] = ref
        try:
            async with self._client() as client:
                resp = await client.get(path, params=params)
        except httpx.RequestError as exc:
            raise ProviderClientError(f"GitHub request failed: {exc}") from exc
        if resp.is_success:
            data = resp.json()
            if not data:
                return {}
            commit = data[0]
            return {
                "sha": commit.get("sha"),
                "message": (commit.get("commit") or {}).get("message"),
                "author": ((commit.get("commit") or {}).get("author") or {}).get("name"),
            }
        raise ProviderClientError(
            f"GitHub returned HTTP {resp.status_code}", status_code=resp.status_code
        )
