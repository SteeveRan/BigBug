"""
@file helm_repo.py
@description Thin Helm repository client (fetch + parse ``index.yaml``). Supports
             test_connection and list_charts with an optional chart allowlist.
@dependencies httpx, ./_http
@relatedFiles ./docker_registry.py
"""

from __future__ import annotations

import httpx
import yaml

from app.services.providers.clients._http import ProviderClientError, build_auth, make_client


class HelmRepoClient:
    def __init__(
        self,
        base_url: str,
        secret: str | None = None,
        username: str | None = None,
        verify_ssl: bool = True,
        index_path: str = "/index.yaml",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.index_url = f"{self.base_url}{index_path}"
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

    async def _fetch_index(self) -> dict:
        try:
            async with self._client() as client:
                resp = await client.get(self.index_url)
        except httpx.RequestError as exc:
            raise ProviderClientError(f"Helm request failed: {exc}") from exc
        if not resp.is_success:
            raise ProviderClientError(f"Helm returned HTTP {resp.status_code}")
        try:
            data = yaml.safe_load(resp.text)
        except yaml.YAMLError as exc:
            raise ProviderClientError(f"Invalid index.yaml: {exc}") from exc
        return data or {}

    async def test_connection(self) -> dict:
        index = await self._fetch_index()
        entries = index.get("entries", {})
        return {"ok": True, "chart_count": len(entries)}

    async def list_charts(self, chart_allowlist: list[str] | None = None) -> list[dict]:
        index = await self._fetch_index()
        entries = index.get("entries", {})
        allowlist = set(chart_allowlist or [])
        items: list[dict] = []
        for name, versions in entries.items():
            if allowlist and name not in allowlist:
                continue
            latest = versions[0] if versions else {}
            items.append(
                {
                    "name": name,
                    "version": latest.get("version"),
                    "app_version": latest.get("appVersion"),
                }
            )
        return items
