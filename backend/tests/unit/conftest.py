"""
@file unit/conftest.py
@description Unit-test specific fixtures. The ENCRYPTION_KEY mock is applied
             automatically to every test so that service-layer cryptography
             works without a real .env file.
@dependencies pytest, app.core.secrets
@relatedFiles ../conftest.py, test_secrets.py
"""

from unittest.mock import patch

import pytest

from app.services.oidc_config import _CachedOIDCConfig

# Valid Fernet key generated for test purposes.
_VALID_FERNET_KEY = "Z0lZSjZpc3gyMDI1Y29vbHByb2plY3RmZXJuZXRrZXk="


@pytest.fixture(autouse=True)
def _patch_encryption_key():
    """Make encrypt_secret/decrypt_secret work in the test environment.

    Mocks settings.encryption_key and clears the get_cipher LRU cache so that
    the mock takes effect immediately.
    """
    with patch("app.core.secrets.settings") as mock_settings:
        mock_settings.encryption_key = _VALID_FERNET_KEY
        from app.core.secrets import get_cipher

        get_cipher.cache_clear()
        yield
        get_cipher.cache_clear()


@pytest.fixture
def test_oidc_config() -> _CachedOIDCConfig:
    """
    Provide a static OIDC configuration snapshot matching the default
    settings-based values used in the OIDC unit tests (issuer, audience,
    frontend client id etc.).
    """
    return _CachedOIDCConfig(
        issuer_url="http://localhost:8180",
        client_id="bigbug-backend",
        client_secret="",
        frontend_client_id="bigbug-frontend",
        enabled=True,
        public_url="http://localhost:8180",
        role_mapping={"admin": "admin", "operator": "operator", "viewer": "viewer"},
    )
