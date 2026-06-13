"""
@file test_source_provider_model.py
@description Unit tests for SourceProvider model — verifies instantiation with
             all provider_type enum values and credential relationship.
@dependencies backend/app/models/source_provider.py, backend/app/models/credential.py
"""

from app.models.source_provider import ProviderType, SourceProvider
from app.models.credential import Credential, CredentialType


class TestSourceProviderModel:
    """Tests for the SourceProvider SQLAlchemy model."""

    def test_source_provider_creation_github(self):
        """Create a SourceProvider with github type."""
        sp = SourceProvider(
            provider_type=ProviderType.github,
            label="GitHub (org-account)",
        )
        assert sp.provider_type == ProviderType.github
        assert sp.label == "GitHub (org-account)"
        assert sp.credential_id is None

    def test_source_provider_creation_gitlab(self):
        """Create a SourceProvider with gitlab type."""
        sp = SourceProvider(
            provider_type=ProviderType.gitlab,
            label="GitLab (self-hosted)",
            credential_id=5,
        )
        assert sp.provider_type == ProviderType.gitlab
        assert sp.label == "GitLab (self-hosted)"
        assert sp.credential_id == 5

    def test_source_provider_creation_bitbucket(self):
        """Create a SourceProvider with bitbucket type."""
        sp = SourceProvider(
            provider_type=ProviderType.bitbucket,
            label="Bitbucket Cloud",
        )
        assert sp.provider_type == ProviderType.bitbucket
        assert sp.label == "Bitbucket Cloud"

    def test_provider_type_enum_values(self):
        """Verify all provider type enum values."""
        assert ProviderType.github.value == "github"
        assert ProviderType.gitlab.value == "gitlab"
        assert ProviderType.bitbucket.value == "bitbucket"

    def test_source_provider_with_credential(self):
        """Verify relationship — SourceProvider can reference a Credential."""
        cred = Credential(
            name="gh-token",
            credential_type=CredentialType.github_token,
            provider="github",
        )
        sp = SourceProvider(
            provider_type=ProviderType.github,
            label="GitHub with token",
        )
        sp.credential = cred
        assert sp.credential is cred
        assert sp.credential.name == "gh-token"

    def test_source_provider_defaults(self):
        """Verify SourceProvider instantiation with minimal fields."""
        sp = SourceProvider(
            provider_type=ProviderType.github,
            label="test",
        )
        assert sp.credential_id is None
        # DB-level defaults (is_deleted=False) are applied at INSERT time.
