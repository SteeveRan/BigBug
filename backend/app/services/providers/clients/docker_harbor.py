"""
@file docker_harbor.py
@description Thin Harbor client for provider actions (test_connection, list_projects,
             list_repositories). Uses the Harbor v2 REST API.
@dependencies httpx, ./_http
@relatedFiles ./docker_registry.py
"""

from __future__ import annotations

import httpx

from app.services.providers.clients._http import ProviderClientError, build_auth, make_client


class HarborClient:
    def __init__(
        self,
        base_url: str,
        secret: str | None = None,
        username: str | None = None,
        verify_ssl: bool = True,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._secret = secret
        self._username = username
        self._verify_ssl = verify_ssl
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return make_client(
            verify_ssl=self._verify_ssl,
            transport=self._transport,
            auth=build_auth(self._secret, self._username),
        )

    async def test_connection(self) -> dict:
        try:
            async with self._client() as client:
                resp = await client.get(f"{self.base_url}/api/v2.0/systeminfo")
        except httpx.RequestError as exc:
            raise ProviderClientError(f"Harbor request failed: {exc}") from exc
        if resp.is_success:
            return {"ok": True}
        raise ProviderClientError(f"Harbor returned HTTP {resp.status_code}")

    async def list_projects(self) -> list[dict]:
        try:
            async with self._client() as client:
                resp = await client.get(f"{self.base_url}/api/v2.0/projects")
        except httpx.RequestError as exc:
            raise ProviderClientError(f"Harbor request failed: {exc}") from exc
        if not resp.is_success:
            raise ProviderClientError(f"Harbor returned HTTP {resp.status_code}")
        return [{"id": str(p.get("project_id")), "name": p.get("name")} for p in resp.json()]

    async def list_repositories(self, project_name: str) -> list[dict]:
        try:
            async with self._client() as client:
                resp = await client.get(
                    f"{self.base_url}/api/v2.0/projects/{project_name}/repositories"
                )
        except httpx.RequestError as exc:
            raise ProviderClientError(f"Harbor request failed: {exc}") from exc
        if not resp.is_success:
            raise ProviderClientError(f"Harbor returned HTTP {resp.status_code}")
        return [{"name": r.get("name")} for r in resp.json()]
