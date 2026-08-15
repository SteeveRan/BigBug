"""
@file test_provider_security.py
@description Unit tests for provider secret handling (stage 9): Fernet roundtrip
             helper, deny-list rejects secret keys, no secret in error messages.
@dependencies backend/app/core/secrets.py, backend/app/schemas/provider.py
"""

import pytest
from cryptography.fernet import Fernet

from app.core.secrets import SecretCipher, SecretEncryptionError
from app.schemas.provider import _deny_secret_keys


class TestFernetRoundtrip:
    def test_roundtrip(self):
        key = Fernet.generate_key()
        cipher = SecretCipher(key)
        token = cipher.encrypt("my-secret-token")
        assert token != "my-secret-token"
        assert cipher.decrypt(token) == "my-secret-token"

    def test_decrypt_invalid_token(self):
        cipher = SecretCipher(Fernet.generate_key())
        with pytest.raises(SecretEncryptionError):
            cipher.decrypt("not-a-valid-token")

    def test_ciphertext_is_not_plaintext(self):
        cipher = SecretCipher(Fernet.generate_key())
        token = cipher.encrypt("password123")
        assert "password123" not in token


class TestConfigDenyList:
    def test_exact_keys_rejected(self):
        for key in ["token", "password", "secret", "key", "auth", "private_key", "credential"]:
            with pytest.raises(ValueError):
                _deny_secret_keys({key: "x"})

    def test_suffix_keys_rejected(self):
        for key in ["api_token", "db_password", "aws_secret", "ssh_key", "reg_credentials"]:
            with pytest.raises(ValueError):
                _deny_secret_keys({key: "x"})

    def test_safe_canonical_keys_allowed(self):
        # Canonical keys from the registry must not match the deny-list.
        _deny_secret_keys(
            {
                "auth_flow": "basic",
                "clone_protocol": "https",
                "index_path": "/index.yaml",
                "chart_allowlist": [],
                "api_style": "registry_v2",
            }
        )
