"""
@file test_docker_auth.py
@description Unit tests for the OCI/Docker bearer-challenge handshake
              (parse_bearer_challenge, scope_for_url, TokenCache, fetch_token,
              oci_request).
"""

import asyncio

import httpx

from app.services.providers.clients.docker_auth import (
    TokenCache,
    fetch_token,
    oci_request,
    parse_bearer_challenge,
    scope_for_url,
)


def test_parse_bearer_challenge():
    header = (
        'Bearer realm="https://auth.docker.io/token",'
        'service="registry.docker.io",scope="repository:library/nginx:pull"'
    )
    assert parse_bearer_challenge(header) == {
        "realm": "https://auth.docker.io/token",
        "service": "registry.docker.io",
        "scope": "repository:library/nginx:pull",
    }


def test_parse_bearer_challenge_not_bearer():
    assert parse_bearer_challenge('Basic realm="x"') == {}


def test_scope_for_url():
    assert scope_for_url("/v2/library/nginx/tags/list") == "repository:library/nginx:pull"
    assert scope_for_url("/v2/org/img/manifests/1.0") == "repository:org/img:pull"
    assert scope_for_url("/v2/") == ""


class TestTokenCache:
    def test_get_miss(self):
        assert TokenCache().get("service", "scope") is None

    def test_put_get(self):
        cache = TokenCache()
        cache.put("s", "p", "tok")
        assert cache.get("s", "p") == "tok"

    def test_expiry(self):
        cache = TokenCache(ttl=-1)
        cache.put("s", "p", "tok")
        assert cache.get("s", "p") is None


def _token_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"token": "bearer-token"})


class TestOciRequest:
    def _basic_200_handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization", "").startswith("Basic ")
        return httpx.Response(200, json={"tags": ["latest"]})

    def test_basic_200_no_handshake(self):
        transport = httpx.MockTransport(self._basic_200_handler)

        async def run():
            async with httpx.AsyncClient(transport=transport) as client:
                return await oci_request(
                    client,
                    "GET",
                    "https://harbor/v2/library/nginx/tags/list",
                    basic=("user", "pass"),
                )

        resp = asyncio.run(run())
        assert resp.status_code == 200

    def test_anonymous_401_then_token_then_200(self):
        calls = {"token": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "auth.docker.io/token" in url:
                calls["token"] += 1
                return httpx.Response(200, json={"token": "tok"})
            auth = request.headers.get("Authorization", "")
            if not auth:
                return httpx.Response(
                    401,
                    headers={
                        "WWW-Authenticate": (
                            'Bearer realm="https://auth.docker.io/token",'
                            'service="registry.docker.io"'
                        )
                    },
                )
            if auth == "Bearer tok":
                return httpx.Response(200, json={"tags": ["latest"]})
            return httpx.Response(401)

        transport = httpx.MockTransport(handler)

        async def run():
            async with httpx.AsyncClient(transport=transport) as client:
                return await oci_request(
                    client, "GET", "https://registry-1.docker.io/v2/library/nginx/tags/list"
                )

        resp = asyncio.run(run())
        assert resp.status_code == 200
        assert calls["token"] == 1

    def test_cache_reuses_token(self):
        calls = {"token": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "auth.docker.io/token" in url:
                calls["token"] += 1
                return httpx.Response(200, json={"token": "tok"})
            if request.headers.get("Authorization") == "Bearer tok":
                return httpx.Response(200, json={"tags": []})
            return httpx.Response(
                401,
                headers={
                    "WWW-Authenticate": 'Bearer realm="https://auth.docker.io/token",service="registry.docker.io"'
                },
            )

        transport = httpx.MockTransport(handler)
        cache = TokenCache()

        async def run():
            async with httpx.AsyncClient(transport=transport) as client:
                url = "https://registry-1.docker.io/v2/library/nginx/tags/list"
                await oci_request(client, "GET", url, cache=cache)
                await oci_request(client, "GET", url, cache=cache)

        asyncio.run(run())
        assert calls["token"] == 1

    def test_401_without_challenge_passthrough(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401)

        transport = httpx.MockTransport(handler)

        async def run():
            async with httpx.AsyncClient(transport=transport) as client:
                return await oci_request(client, "GET", "https://harbor/v2/")

        resp = asyncio.run(run())
        assert resp.status_code == 401


def test_fetch_token_with_basic():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization", "").startswith("Basic ")
        return httpx.Response(200, json={"token": "tok"})

    transport = httpx.MockTransport(handler)

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetch_token(
                client,
                "https://auth.docker.io/token",
                "registry.docker.io",
                "repository:library/nginx:pull",
                basic=("user", "pass"),
            )

    assert asyncio.run(run()) == "tok"
