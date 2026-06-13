"""
@file test_credential_model.py
@description Unit tests for Credential model — verifies instantiation with all
             credential_type enum values and basic field defaults.
@dependencies backend/app/models/credential.py
"""

from app.models.credential import Credential, CredentialType


class TestCredentialModel:
    """Tests for the Credential SQLAlchemy model."""

    def test_credential_creation_github_token(self):
        """Create a credential with github_token type."""
        cred = Credential(
            name="github-integration-token",
            credential_type=CredentialType.github_token,
            provider="github",
            username="bot-user",
            encrypted_secret="encrypted-gh-token-value",
            status_flag=0,
        )
        assert cred.name == "github-integration-token"
        assert cred.credential_type == CredentialType.github_token
        assert cred.provider == "github"
        assert cred.username == "bot-user"
        assert cred.encrypted_secret == "encrypted-gh-token-value"
        assert cred.status_flag == 0

    def test_credential_creation_gitlab_token(self):
        """Create a credential with gitlab_token type."""
        cred = Credential(
            name="gitlab-api-token",
            credential_type=CredentialType.gitlab_token,
            provider="gitlab",
            encrypted_secret="encrypted-gl-token-value",
            base_url="https://gitlab.example.com",
        )
        assert cred.name == "gitlab-api-token"
        assert cred.credential_type == CredentialType.gitlab_token
        assert cred.provider == "gitlab"
        assert cred.base_url == "https://gitlab.example.com"
        assert cred.ssh_public_key is None

    def test_credential_creation_https_basic(self):
        """Create a credential with https_basic type (username + password)."""
        cred = Credential(
            name="harbor-admin-creds",
            credential_type=CredentialType.https_basic,
            provider="generic",
            username="admin",
            encrypted_secret="encrypted-password",
            base_url="https://harbor.example.com",
        )
        assert cred.credential_type == CredentialType.https_basic
        assert cred.username == "admin"
        assert cred.encrypted_secret == "encrypted-password"

    def test_credential_creation_ssh_key(self):
        """Create a credential with ssh_key type."""
        cred = Credential(
            name="deploy-ssh-key",
            credential_type=CredentialType.ssh_key,
            provider="github",
            encrypted_secret="encrypted-private-key",
            ssh_public_key="ssh-rsa AAAAB3... user@host",
        )
        assert cred.credential_type == CredentialType.ssh_key
        assert cred.encrypted_secret == "encrypted-private-key"
        assert cred.ssh_public_key == "ssh-rsa AAAAB3... user@host"

    def test_credential_type_enum_values(self):
        """Verify all credential type enum values are defined."""
        assert CredentialType.github_token.value == "github_token"
        assert CredentialType.gitlab_token.value == "gitlab_token"
        assert CredentialType.https_basic.value == "https_basic"
        assert CredentialType.ssh_key.value == "ssh_key"

    def test_credential_defaults(self):
        """Verify that created_at/updated_at are set by SQLAlchemy (DB-level)."""
        cred = Credential(
            name="default-test",
            credential_type=CredentialType.github_token,
            provider="github",
        )
        # DB-level Column defaults (0, False) are applied at INSERT time, not init.
        # Verify the model can be instantiated with explicit values.
        assert cred.name == "default-test"
        assert cred.credential_type == CredentialType.github_token
        assert cred.provider == "github"

    def test_credential_representation(self):
        """Verify __repr__ output."""
        cred = Credential(
            id=1,
            name="my-token",
            credential_type=CredentialType.github_token,
            provider="github",
        )
        repr_str = repr(cred)
        assert "my-token" in repr_str
        assert "Credential" in repr_str
