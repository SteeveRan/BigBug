"""
@file git_generic.py
@description Thin client for generic Git providers (no API discovery). Supports
             test_connection (ls-remote via HTTP) and manual repository discovery.
@dependencies httpx, ./_http
@relatedFiles ./git_github.py, ./git_gitlab.py
"""

from __future__ import annotations

import httpx

from app.services.providers.clients._http import ProviderClientError, build_auth, make_client


class GenericGitClient:
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
                resp = await client.get(self.base_url)
        except httpx.RequestError as exc:
            raise ProviderClientError(f"Git request failed: {exc}") from exc
        if resp.is_success or resp.status_code == 401:
            # A 401 still proves the endpoint is reachable (credentials may differ).
            return {"ok": True, "status_code": resp.status_code}
        raise ProviderClientError(f"Git returned HTTP {resp.status_code}")

    async def list_repositories(self, group_external_id: str) -> list[dict]:
        """Manual discovery mode returns the single configured repository."""
        return [{"id": group_external_id, "name": group_external_id}]
