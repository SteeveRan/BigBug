"""
@file docker_registry.py
@description Thin OCI/Docker Registry V2 client + per-subtype helpers (docker_hub,
             quay, gcr, ecr, acr, ghcr, generic_registry). Lists repositories via
             ``/v2/_catalog`` and tags via ``/v2/<name>/tags/list``.
@dependencies httpx, ./_http
@relatedFiles ./docker_harbor.py, ./helm_repo.py
"""

from __future__ import annotations

import httpx

from app.services.providers.clients._http import ProviderClientError, build_auth, make_client

# Canonical registry endpoints per subtype. Custom ``base_url`` overrides these.
_DEFAULT_ENDPOINTS: dict[str, str] = {
    "docker_hub": "https://registry-1.docker.io",
    "quay": "https://quay.io",
    "ghcr": "https://ghcr.io",
    "gcr": "https://gcr.io",
    "ecr": "https://public.ecr.aws",
    "acr": "https://azurecr.io",
    "generic_registry": "",
}


class DockerRegistryClient:
    def __init__(
        self,
        subtype: str,
        base_url: str | None = None,
        secret: str | None = None,
        username: str | None = None,
        verify_ssl: bool = True,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.subtype = subtype
        self.base_url = base_url.rstrip("/") if base_url else _DEFAULT_ENDPOINTS.get(subtype, "")
        if not self.base_url:
            raise ProviderClientError(f"base_url is required for subtype '{subtype}'")
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
                resp = await client.get(f"{self.base_url}/v2/")
        except httpx.RequestError as exc:
            raise ProviderClientError(f"Registry request failed: {exc}") from exc
        if resp.is_success:
            return {"ok": True}
        if resp.status_code == 401:
            return {"ok": True, "authenticated": False}
        raise ProviderClientError(f"Registry returned HTTP {resp.status_code}")

    async def list_repositories(self, namespace: str | None = None) -> list[dict]:
        try:
            async with self._client() as client:
                resp = await client.get(f"{self.base_url}/v2/_catalog")
        except httpx.RequestError as exc:
            raise ProviderClientError(f"Registry request failed: {exc}") from exc
        if not resp.is_success:
            raise ProviderClientError(f"Registry returned HTTP {resp.status_code}")
        repos = resp.json().get("repositories", [])
        if namespace:
            repos = [r for r in repos if r.startswith(f"{namespace}/")]
        return [{"name": r} for r in repos]

    async def list_tags(self, repository: str) -> list[str]:
        try:
            async with self._client() as client:
                resp = await client.get(f"{self.base_url}/v2/{repository}/tags/list")
        except httpx.RequestError as exc:
            raise ProviderClientError(f"Registry request failed: {exc}") from exc
        if not resp.is_success:
            raise ProviderClientError(f"Registry returned HTTP {resp.status_code}")
        return resp.json().get("tags") or []


def registry_client_for_subtype(
    subtype: str,
    base_url: str | None = None,
    secret: str | None = None,
    username: str | None = None,
    verify_ssl: bool = True,
    transport: httpx.AsyncBaseTransport | None = None,
) -> DockerRegistryClient:
    """Construct a registry client for any docker/OCI subtype."""
    return DockerRegistryClient(
        subtype=subtype,
        base_url=base_url,
        secret=secret,
        username=username,
        verify_ssl=verify_ssl,
        transport=transport,
    )
