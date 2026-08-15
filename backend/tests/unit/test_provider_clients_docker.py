"""
@file test_provider_clients_docker.py
@description Unit tests for docker/OCI and Harbor clients (stage 7): registry v2
             catalog/tags, harbor projects/repositories, subtype endpoint mapping.
@dependencies backend/app/services/providers/clients/docker_*.py
"""

import httpx
import pytest

from app.services.providers.clients._http import ProviderClientError
from app.services.providers.clients.docker_harbor import HarborClient
from app.services.providers.clients.docker_registry import (
    DockerRegistryClient,
    registry_client_for_subtype,
)


class TestDockerRegistryClient:
    def test_list_repositories(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if "/_catalog" in str(request.url):
                return httpx.Response(200, json={"repositories": ["ns/app", "ns/db"]})
            return httpx.Response(404)

        client = DockerRegistryClient(
            subtype="docker_hub",
            base_url="https://registry-1.docker.io",
            transport=httpx.MockTransport(handler),
        )

        async def run():
            return await client.list_repositories(namespace="ns")

        import asyncio

        items = asyncio.run(run())
        assert items == [{"name": "ns/app"}, {"name": "ns/db"}]

    def test_list_tags(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"tags": ["latest", "1.0"]})

        client = DockerRegistryClient(
            subtype="docker_hub",
            base_url="https://registry-1.docker.io",
            transport=httpx.MockTransport(handler),
        )

        async def run():
            return await client.list_tags("ns/app")

        import asyncio

        tags = asyncio.run(run())
        assert tags == ["latest", "1.0"]

    def test_requires_base_url_for_generic(self):
        with pytest.raises(ProviderClientError):
            DockerRegistryClient(subtype="generic_registry", base_url=None)

    def test_default_endpoint_for_docker_hub(self):
        client = registry_client_for_subtype("docker_hub")
        assert "docker.io" in client.base_url


class TestHarborClient:
    def test_list_projects(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert "/api/v2.0/projects" in str(request.url)
            return httpx.Response(200, json=[{"project_id": 1, "name": "library"}])

        client = HarborClient(
            base_url="https://harbor.example.com",
            transport=httpx.MockTransport(handler),
        )

        async def run():
            return await client.list_projects()

        import asyncio

        items = asyncio.run(run())
        assert items[0]["name"] == "library"

    def test_list_repositories(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[{"name": "library/app"}])

        client = HarborClient(
            base_url="https://harbor.example.com",
            transport=httpx.MockTransport(handler),
        )

        async def run():
            return await client.list_repositories("library")

        import asyncio

        items = asyncio.run(run())
        assert items[0]["name"] == "library/app"
