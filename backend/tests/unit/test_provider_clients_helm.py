"""
@file test_provider_clients_helm.py
@description Unit tests for the Helm repository client (stage 8): index.yaml fetch
             + parse, chart allowlist filtering.
@dependencies backend/app/services/providers/clients/helm_repo.py
"""

import httpx

from app.services.providers.clients.helm_repo import HelmRepoClient

_INDEX = """
apiVersion: v1
entries:
  app:
    - version: 1.2.3
      appVersion: "4.5.6"
  nginx:
    - version: 2.0.0
      appVersion: "1.27"
"""


class TestHelmRepoClient:
    def test_list_charts(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert "/index.yaml" in str(request.url)
            return httpx.Response(200, text=_INDEX)

        client = HelmRepoClient(
            base_url="https://charts.example.com",
            transport=httpx.MockTransport(handler),
        )

        async def run():
            return await client.list_charts()

        import asyncio

        items = asyncio.run(run())
        names = {item["name"] for item in items}
        assert names == {"app", "nginx"}

    def test_chart_allowlist(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=_INDEX)

        client = HelmRepoClient(
            base_url="https://charts.example.com",
            transport=httpx.MockTransport(handler),
        )

        async def run():
            return await client.list_charts(chart_allowlist=["nginx"])

        import asyncio

        items = asyncio.run(run())
        assert [item["name"] for item in items] == ["nginx"]

    def test_test_connection(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=_INDEX)

        client = HelmRepoClient(
            base_url="https://charts.example.com",
            transport=httpx.MockTransport(handler),
        )

        async def run():
            return await client.test_connection()

        import asyncio

        result = asyncio.run(run())
        assert result["ok"] is True
        assert result["chart_count"] == 2
