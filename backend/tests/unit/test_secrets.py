"""
@file test_secrets.py
@description Unit tests for app.core.secrets — symmetric encryption/decryption
             of Helm/Docker registry credentials using Fernet.
"""

from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

from app.core.secrets import (
    SecretCipher,
    SecretEncryptionError,
    decrypt_secret,
    encrypt_secret,
)

# A valid Fernet key for module-level helper tests (URL-safe base64 32 bytes).
_VALID_FERNET_KEY = "mWcJRzG34XG8yDTrgmK7YfO4s2t1IC1Bq-8xO7GMHPg="


class TestSecretCipher:
    """Tests for the SecretCipher class in isolation."""

    @pytest.fixture
    def key(self) -> bytes:
        return Fernet.generate_key()

    @pytest.fixture
    def cipher(self, key: bytes) -> SecretCipher:
        return SecretCipher(key)

    def test_encrypt_decrypt_roundtrip(self, cipher: SecretCipher):
        """Encrypting and then decrypting should return the original text."""
        plaintext = "my-super-secret-registry-password"
        token = cipher.encrypt(plaintext)
        assert token != plaintext
        assert cipher.decrypt(token) == plaintext

    def test_encrypt_special_characters(self, cipher: SecretCipher):
        """Characters beyond ASCII should survive the round-trip."""
        plaintext = "пароль-Δ@#$%^&*()🤖"
        token = cipher.encrypt(plaintext)
        assert cipher.decrypt(token) == plaintext

    def test_decrypt_invalid_token(self, cipher: SecretCipher):
        """Decrypting a non-Fernet token must raise SecretEncryptionError."""
        with pytest.raises(SecretEncryptionError):
            cipher.decrypt("this-is-not-a-valid-fernet-token")

    def test_decrypt_wrong_key(self, key: bytes):
        """Decrypting with a different key must raise SecretEncryptionError."""
        cipher_a = SecretCipher(key)
        cipher_b = SecretCipher(Fernet.generate_key())
        token = cipher_a.encrypt("secret-value")
        with pytest.raises(SecretEncryptionError):
            cipher_b.decrypt(token)

    def test_encrypt_empty_string(self, cipher: SecretCipher):
        """Explicitly test that empty string encrypts to something decryptable."""
        token = cipher.encrypt("")
        assert cipher.decrypt(token) == ""


class TestModuleLevelHelpers:
    """Tests for encrypt_secret / decrypt_secret convenience functions.

    These mock settings.encryption_key so they don't depend on a real .env file.
    """

    @pytest.fixture(autouse=True)
    def _patch_encryption_key(self):
        with patch("app.core.secrets.settings") as mock_settings:
            mock_settings.encryption_key = _VALID_FERNET_KEY
            # Clear the cached get_cipher result so the mock takes effect.
            from app.core.secrets import get_cipher

            get_cipher.cache_clear()
            yield
            get_cipher.cache_clear()

    def test_encrypt_none(self):
        assert encrypt_secret(None) is None

    def test_encrypt_empty_string(self):
        assert encrypt_secret("") is None

    def test_decrypt_none(self):
        assert decrypt_secret(None) is None

    def test_decrypt_empty_string(self):
        assert decrypt_secret("") is None

    def test_decrypt_invalid_token_module_level(self):
        """Non-Fernet garbage must raise SecretEncryptionError from decrypt_secret."""
        with pytest.raises(SecretEncryptionError):
            decrypt_secret("garbage-token-text")

    def test_encrypt_decrypt_module_level_roundtrip(self):
        """encrypt_secret + decrypt_secret should perform a full round-trip."""
        plaintext = "a-module-level-secret"
        token = encrypt_secret(plaintext)
        assert token is not None
        assert decrypt_secret(token) == plaintext
