"""
@file docker_auth.py
@description OCI/Docker Registry v2 token handshake helpers. Implements the
             ``Bearer`` challenge flow (``WWW-Authenticate: Bearer realm=…``) so a
             single client works against both Harbor (Basic-first, 200 on step 1)
             and Docker Hub (401 + challenge) without hardcoding any realm/service.
             Credentials are never logged.
@dependencies httpx
@relatedFiles ./docker_registry.py, ../../../services/docker.py
"""

from __future__ import annotations

import base64
import re
import time

import httpx

# TTL for cached bearer tokens, in seconds.
_TOKEN_TTL_SECONDS = 300

_CHALLENGE_PARAM_RE = re.compile(r'(realm|service|scope)\s*=\s*"([^"]*)"', re.IGNORECASE)


class TokenCache:
    """Simple in-memory bearer-token cache keyed by ``(service, scope)``.

    ponytail: plain dict with a 300s TTL and no LRU/eviction — fine for a single
    registry client that touches a handful of scopes per process. Upgrade to a
    bounded TTL cache if the number of cached scopes ever grows materially.
    """

    def __init__(self, ttl: int = _TOKEN_TTL_SECONDS) -> None:
        self._ttl = ttl
        self._tokens: dict[tuple[str, str], tuple[str, float]] = {}

    def get(self, service: str, scope: str) -> str | None:
        entry = self._tokens.get((service, scope))
        if entry is None:
            return None
        token, expires_at = entry
        if time.monotonic() >= expires_at:
            self._tokens.pop((service, scope), None)
            return None
        return token

    def put(self, service: str, scope: str, token: str) -> None:
        self._tokens[(service, scope)] = (token, time.monotonic() + self._ttl)


def parse_bearer_challenge(header: str) -> dict[str, str]:
    """Parse a ``WWW-Authenticate: Bearer realm=…,service=…,scope=…`` header.

    Returns a dict with the keys that were present. Values are unquoted.
    """
    result: dict[str, str] = {}
    if not header or "bearer" not in header.lower():
        return result
    for key, value in _CHALLENGE_PARAM_RE.findall(header):
        result[key.lower()] = value
    return result


def scope_for_url(path: str, actions: str = "pull") -> str:
    """Derive an OCI token scope from a registry API path.

    ``/v2/library/nginx/tags/list`` → ``repository:library/nginx:pull``.
    """
    parts = [p for p in path.split("/") if p]
    if parts and parts[0] == "v2":
        parts = parts[1:]
    repo_parts: list[str] = []
    for part in parts:
        # Well-known terminal endpoints start the trailing action/digest segment.
        if part in ("tags", "manifests", "blobs", "_catalog"):
            break
        repo_parts.append(part)
    repo = "/".join(repo_parts)
    if not repo:
        return ""
    return f"repository:{repo}:{actions}"


def _basic_header(basic: tuple[str, str]) -> str:
    raw = f"{basic[0]}:{basic[1]}".encode()
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _build_headers(
    basic: tuple[str, str] | None,
    headers: dict[str, str] | None,
    bearer: str | None = None,
) -> dict[str, str]:
    merged = dict(headers or {})
    if basic:
        merged["Authorization"] = _basic_header(basic)
    elif bearer:
        merged["Authorization"] = f"Bearer {bearer}"
    return merged


async def fetch_token(
    client: httpx.AsyncClient,
    realm: str,
    service: str,
    scope: str,
    basic: tuple[str, str] | None = None,
) -> str:
    """Request a bearer token from the challenge ``realm``.

    Docker Hub uses ``https://auth.docker.io/token?service=…&scope=…``; the realm
    comes entirely from the challenge so nothing is hardcoded here.
    """
    headers = {}
    if basic:
        headers["Authorization"] = _basic_header(basic)
    resp = await client.get(realm, params={"service": service, "scope": scope}, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    if not token:
        raise ValueError("Bearer token response did not contain 'token'")
    return token


async def oci_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    basic: tuple[str, str] | None = None,
    headers: dict[str, str] | None = None,
    scope_actions: str = "pull",
    cache: TokenCache | None = None,
) -> httpx.Response:
    """Perform an OCI registry request, transparently completing the bearer handshake.

    1. Send the request, including a Basic ``Authorization`` header when ``basic``
       is supplied (Harbor answers 200 here and the flow is done).
    2. On a 401 with a ``WWW-Authenticate: Bearer …`` challenge, fetch a token
       (from ``cache`` or ``fetch_token``) and retry exactly once with Bearer.
    3. Return the final response — the caller decides what a non-2xx means.
    """
    resp = await client.request(method, url, headers=_build_headers(basic, headers))

    if resp.status_code != 401:
        return resp

    parsed = parse_bearer_challenge(resp.headers.get("WWW-Authenticate", ""))
    realm = parsed.get("realm")
    if not realm:
        return resp

    service = parsed.get("service", "")
    scope = parsed.get("scope") or scope_for_url(url, scope_actions)
    if not scope:
        return resp

    token = None
    if cache is not None:
        token = cache.get(service, scope)
    if token is None:
        token = await fetch_token(client, realm, service, scope, basic=basic)
        if cache is not None:
            cache.put(service, scope, token)

    return await client.request(method, url, headers=_build_headers(basic, headers, bearer=token))
