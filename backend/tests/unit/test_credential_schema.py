"""
@file test_credential_schema.py
@description Unit tests for Credential Pydantic schemas.
             Validates Create/Update/Out and verifies secret is never in Out.
@dependencies app.schemas.credential
"""

import pytest
from pydantic import ValidationError

from app.schemas.credential import CredentialCreate, CredentialUpdate, CredentialOut
from app.models.credential import CredentialType


class TestCredentialCreate:
    """Validation of CredentialCreate schema."""

    def test_create_minimal_github_token(self):
        """Create with minimal required fields for github_token type."""
        data = CredentialCreate(
            name="github-token-1",
            credential_type=CredentialType.github_token,
            provider="github",
            secret="ghp_abc123",
        )
        assert data.name == "github-token-1"
        assert data.credential_type == CredentialType.github_token
        assert data.provider == "github"
        assert data.secret == "ghp_abc123"
        assert data.username is None

    def test_create_https_basic_with_username(self):
        """Create https_basic credential with username and secret."""
        data = CredentialCreate(
            name="basic-auth",
            credential_type=CredentialType.https_basic,
            provider="generic",
            username="user1",
            secret="password123",
        )
        assert data.username == "user1"
        assert data.secret == "password123"

    def test_create_ssh_key_with_public_key(self):
        """Create ssh_key credential with ssh public key."""
        data = CredentialCreate(
            name="ssh-key-1",
            credential_type=CredentialType.ssh_key,
            provider="github",
            secret="-----BEGIN OPENSSH PRIVATE KEY-----...",
            ssh_public_key="ssh-ed25519 AAAAC3...",
        )
        assert data.ssh_public_key == "ssh-ed25519 AAAAC3..."
        assert data.credential_type == CredentialType.ssh_key

    def test_create_with_base_url(self):
        """Create self-hosted gitlab credential with base_url."""
        data = CredentialCreate(
            name="self-hosted-gitlab",
            credential_type=CredentialType.gitlab_token,
            provider="gitlab",
            secret="glpat-xyz789",
            base_url="https://gitlab.internal.com",
        )
        assert data.base_url == "https://gitlab.internal.com"

    def test_create_requires_secret(self):
        """secret is required for CredentialCreate."""
        with pytest.raises(ValidationError):
            CredentialCreate(
                name="no-secret",
                credential_type=CredentialType.github_token,
                provider="github",
            )

    def test_create_requires_name(self):
        """name is required."""
        with pytest.raises(ValidationError):
            CredentialCreate(
                credential_type=CredentialType.github_token,
                provider="github",
                secret="test",
            )


class TestCredentialUpdate:
    """Validation of CredentialUpdate schema."""

    def test_update_all_fields_optional(self):
        """All fields are optional — empty update is valid."""
        data = CredentialUpdate()
        assert data.name is None
        assert data.secret is None
        assert data.username is None

    def test_update_partial(self):
        """Only update username and secret."""
        data = CredentialUpdate(username="newuser", secret="newsecret")
        assert data.username == "newuser"
        assert data.secret == "newsecret"
        assert data.name is None


class TestCredentialOut:
    """Validation of CredentialOut — secret MUST NOT be present."""

    def test_out_has_no_secret_or_encrypted_secret(self):
        """CredentialOut has no 'secret' or 'encrypted_secret' fields."""
        fields = CredentialOut.model_fields
        assert "secret" not in fields
        assert "encrypted_secret" not in fields

    def test_out_has_expected_fields(self):
        """Verify all expected public fields are present."""
        fields = set(CredentialOut.model_fields.keys())
        expected = {
            "id", "name", "credential_type", "provider", "username",
            "ssh_public_key", "base_url", "status_flag", "status_text",
            "last_tested_at", "created_at", "updated_at",
        }
        assert fields == expected

    def test_out_from_attributes_config(self):
        """model_config enables from_attributes."""
        assert CredentialOut.model_config.get("from_attributes") is True
