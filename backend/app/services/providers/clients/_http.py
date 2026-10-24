"""
@file _http.py
@description Shared base for the thin provider HTTP clients. Provides an
             ``httpx.AsyncClient`` factory with a stable timeout, optional basic
             auth and an injectable transport for tests. Never logs secrets or
             Authorization headers.
@dependencies httpx
@relatedFiles ./git_github.py, ./git_gitlab.py, ./git_generic.py, ./docker_registry.py,
./docker_harbor.py, ./helm_repo.py
"""

from __future__ import annotations

import ssl

import httpx

from app.core.http import ssl_verify

DEFAULT_TIMEOUT = 15.0


class ProviderClientError(RuntimeError):
    """Raised when a provider HTTP call fails (transport or non-2xx).

    ``status_code`` carries the upstream HTTP status for non-2xx responses so
    the service layer can map it to a meaningful :class:`DomainError` (e.g. a
    401 from an anonymous provider becomes an actionable message instead of a
    blind "HTTP 401").
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def build_auth(secret: str | None, username: str | None = None) -> httpx.Auth | None:
    """Return basic auth from a decrypted secret, or ``None`` for anonymous."""
    if secret is None or secret == "":
        return None
    if username:
        return httpx.BasicAuth(username, secret)
    return httpx.BasicAuth("x", secret)


def make_client(
    verify_ssl: bool = True,
    transport: httpx.AsyncBaseTransport | None = None,
    auth: httpx.Auth | None = None,
    headers: dict[str, str] | None = None,
    ssl_context: bool | str | ssl.SSLContext | None = None,
) -> httpx.AsyncClient:
    """Build an ``httpx.AsyncClient`` with a stable timeout.

    ``transport`` is injectable so tests can use ``httpx.MockTransport`` without
    monkey-patching network calls. ``headers`` are applied to every request.
    ``ssl_context`` (ADR-0037) overrides the default computation when given:
    an :class:`ssl.SSLContext` built from a provider trust store, a CA bundle
    path, or ``False``.
    """
    verify = ssl_context if ssl_context is not None else (ssl_verify() if verify_ssl else False)
    return httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT,
        verify=verify,
        transport=transport,
        auth=auth,
        headers=headers,
    )
