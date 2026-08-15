"""
@file test_provider_clients_git.py
@description Unit tests for git provider clients (stage 6): GitHub, GitLab, Generic.
             Uses httpx.MockTransport — no real network. Verifies anonymous mode,
             credential-derived auth and error messages never containing secrets.
@dependencies backend/app/services/providers/clients/git_*.py
"""

import httpx
import pytest

from app.services.providers.clients._http import ProviderClientError
from app.services.providers.clients.git_generic import GenericGitClient
from app.services.providers.clients.git_github import GitHubClient
from app.services.providers.clients.git_gitlab import GitLabClient


def _transport(handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


class TestGitHubClient:
    def test_test_connection_ok(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert "api.github.com" in str(request.url)
            return httpx.Response(200, json={"rate": {"limit": 5000}})

        client = GitHubClient(transport=_transport(handler))

        async def run():
            return await client.test_connection()

        import asyncio

        result = asyncio.run(run())
        assert result["ok"] is True

    def test_anonymous_has_no_authorization(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert "Authorization" not in request.headers
            return httpx.Response(200, json=[])

        client = GitHubClient(transport=_transport(handler))

        async def run():
            return await client.list_groups()

        import asyncio

        result = asyncio.run(run())
        assert result == []

    def test_error_message_no_secret(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500)

        client = GitHubClient(secret="supersecrettoken", transport=_transport(handler))

        async def run():
            return await client.test_connection()

        import asyncio

        with pytest.raises(ProviderClientError) as exc:
            asyncio.run(run())
        assert "supersecrettoken" not in str(exc.value)


class TestGitLabClient:
    def test_test_connection(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert "/api/v4/version" in str(request.url)
            return httpx.Response(200, json={"version": "17.0.0"})

        client = GitLabClient(base_url="https://gitlab.example.com", transport=_transport(handler))

        async def run():
            return await client.test_connection()

        import asyncio

        result = asyncio.run(run())
        assert result["version"] == "17.0.0"

    def test_list_groups(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[{"id": 1, "name": "g", "full_path": "g"}])

        client = GitLabClient(base_url="https://gitlab.example.com", transport=_transport(handler))

        async def run():
            return await client.list_groups()

        import asyncio

        items = asyncio.run(run())
        assert items[0]["name"] == "g"


class TestGenericGitClient:
    def test_test_connection_ok(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200)

        client = GenericGitClient(base_url="https://git.example.com", transport=_transport(handler))

        async def run():
            return await client.test_connection()

        import asyncio

        result = asyncio.run(run())
        assert result["ok"] is True

    def test_list_repositories_manual(self):
        client = GenericGitClient(base_url="https://git.example.com")

        async def run():
            return await client.list_repositories("repo-name")

        import asyncio

        items = asyncio.run(run())
        assert items == [{"id": "repo-name", "name": "repo-name"}]
