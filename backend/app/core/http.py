"""
@file http.py
@description Shared TLS verification helper for outgoing httpx clients.
              httpx (unlike requests) ignores SSL_CERT_FILE/REQUESTS_CA_BUNDLE
              and builds its trust store from certifi — so the dev-stand CA
              bundle (entrypoint.sh → /run/bigbug-ca/ca-bundle.crt) would be
              invisible to every client. This helper returns the bundle path
              when the environment exports one, letting callers pass it as
              ``verify=``. ADR-0030 §4.
@dependencies os
@relatedFiles bin/entrypoint.sh, services/oidc.py, services/providers/clients/_http.py
"""

from __future__ import annotations

import os


def ssl_verify() -> bool | str:
    """Return the CA bundle path from SSL_CERT_FILE, or True for certifi defaults.

    Every outgoing httpx client must pass ``verify=ssl_verify()`` so the
    stand CA (dev) and corporate proxies (prod) are trusted uniformly.
    """
    bundle = os.environ.get("SSL_CERT_FILE", "")
    return bundle if bundle else True
