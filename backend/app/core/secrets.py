"""
@file secrets.py
@description Symmetric encryption helpers used to protect credentials at rest
             (Helm and Docker registry usernames/passwords). Wraps Fernet
             (AES-128-CBC + HMAC-SHA256) behind a tiny SecretCipher class so
             callers never touch raw key material.

The cipher is intentionally exposed only via a process-wide getter; key
rotation is not handled yet — when needed, switch to MultiFernet here and
re-encrypt existing rows in a one-off migration.

@dependencies cryptography (already in pyproject.toml via python-jose[cryptography])
"""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class SecretEncryptionError(RuntimeError):
    """Raised when a value cannot be decrypted (corrupt or wrong key)."""


class SecretCipher:
    """
    Symmetric encryption wrapper around a single Fernet key.

    The class is split from the module-level helpers below to keep the
    encryption primitive testable in isolation (inject a custom key without
    monkey-patching the settings singleton).
    """

    def __init__(self, key: str | bytes) -> None:
        if isinstance(key, str):
            key = key.encode("utf-8")
        # WHY: Fernet validates the key shape (URL-safe base64, 32 bytes)
        # eagerly so a misconfigured ENCRYPTION_KEY fails fast at startup
        # rather than on the first encrypt() call.
        self._fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a UTF-8 string, returning a URL-safe base64 token."""
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, token: str) -> str:
        """Decrypt a token previously produced by :meth:`encrypt`."""
        try:
            return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            # WHY: Surface a domain-specific error so API layers can map it to
            # a clear 500 instead of leaking cryptography internals.
            raise SecretEncryptionError(
                "Failed to decrypt secret (wrong key or corrupt data)"
            ) from exc


@lru_cache(maxsize=1)
def get_cipher() -> SecretCipher:
    """
    Return the process-wide SecretCipher instance.

    Cached so we pay the Fernet key validation only once per process. Tests
    can override the cipher by clearing the cache.
    """
    if not settings.encryption_key:
        # WHY: Refuse to silently fall back to a random key — that would lose
        # data on every restart and is far worse than a loud configuration
        # error during boot.
        raise RuntimeError(
            "ENCRYPTION_KEY is not configured. Generate one with "
            "`python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`"
        )
    return SecretCipher(settings.encryption_key)


def encrypt_secret(plaintext: str | None) -> str | None:
    """Encrypt ``plaintext`` or return ``None`` for empty inputs."""
    if plaintext is None or plaintext == "":
        return None
    return get_cipher().encrypt(plaintext)


def decrypt_secret(token: str | None) -> str | None:
    """Decrypt ``token`` produced by :func:`encrypt_secret` or return ``None``."""
    if token is None or token == "":
        return None
    return get_cipher().decrypt(token)
