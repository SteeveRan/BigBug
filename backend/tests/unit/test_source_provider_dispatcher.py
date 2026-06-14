"""
@file test_source_provider_dispatcher.py
@description Unit tests for ProviderDispatcher — get_provider_class() and
             create_source_provider() factory functions.
@dependencies pytest, unittest.mock
@relatedFiles ../../app/services/source_providers/dispatcher.py,
              ../../app/services/source_providers/github.py,
              ../../app/services/source_providers/gitlab.py,
              ../../app/models/source_provider.py
"""

from unittest.mock import MagicMock, patch

import pytest

from app.models.credential import Credential, CredentialType
from app.models.source_provider import ProviderType, SourceProvider
from app.services.source_provider import BaseSourceProvider
from app.services.source_providers.dispatcher import (
    create_source_provider,
    get_provider_class,
)
from app.services.source_providers.generic_git import GenericGitSourceProvider
from app.services.source_providers.github import GitHubSourceProvider
from app.services.source_providers.gitlab import GitLabSourceProvider

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def github_provider_db():
    """Create a GitHub SourceProvider ORM model."""
    credential = Credential(
        id=1,
        name="test-github",
        credential_type=CredentialType.github_token,
        provider="github",
        encrypted_secret="encrypted:test-token",
    )
    sp = SourceProvider(
        id=1,
        label="Test GitHub",
        provider_type=ProviderType.github,
        credential_id=1,
        is_deleted=False,
    )
    sp.credential = credential
    return sp


@pytest.fixture
def gitlab_provider_db():
    """Create a GitLab SourceProvider ORM model."""
    credential = Credential(
        id=2,
        name="test-gitlab",
        credential_type=CredentialType.gitlab_token,
        provider="gitlab",
        encrypted_secret="encrypted:test-token-gitlab",
    )
    sp = SourceProvider(
        id=2,
        label="Test GitLab",
        provider_type=ProviderType.gitlab,
        credential_id=2,
        is_deleted=False,
    )
    sp.credential = credential
    return sp


@pytest.fixture
def generic_provider_db():
    """Create a GenericGit SourceProvider ORM model."""
    credential = Credential(
        id=3,
        name="test-generic",
        credential_type=CredentialType.https_basic,
        provider="generic",
        encrypted_secret="encrypted:test-token-generic",
    )
    sp = SourceProvider(
        id=3,
        label="Test Generic",
        provider_type=ProviderType.generic,
        credential_id=3,
        is_deleted=False,
    )
    sp.credential = credential
    return sp


# ---------------------------------------------------------------------------
# Tests: get_provider_class
# ---------------------------------------------------------------------------


class TestGetProviderClass:
    """Tests for get_provider_class() — synchronous class resolver."""

    def test_github(self):
        """'github' returns GitHubSourceProvider class."""
        klass = get_provider_class("github")
        assert klass is GitHubSourceProvider

    def test_gitlab(self):
        """'gitlab' returns GitLabSourceProvider class."""
        klass = get_provider_class("gitlab")
        assert klass is GitLabSourceProvider

    def test_case_insensitive_not_supported(self):
        """'GitHub' (mixed case) raises ValueError — no case-insensitive matching."""
        with pytest.raises(ValueError, match="Unsupported provider type"):
            get_provider_class("GitHub")

    def test_generic(self):
        """'generic' returns GenericGitSourceProvider class."""
        klass = get_provider_class("generic")
        assert klass is GenericGitSourceProvider

    def test_unknown(self):
        """'unknown_provider' raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported provider type"):
            get_provider_class("unknown_provider")

    def test_empty(self):
        """Empty string raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported provider type"):
            get_provider_class("")


# ---------------------------------------------------------------------------
# Tests: create_source_provider
# ---------------------------------------------------------------------------


class TestCreateSourceProvider:
    """Tests for create_source_provider() — async factory function."""

    @pytest.mark.asyncio
    async def test_create_github_provider(self, github_provider_db):
        """create_source_provider with GitHub type returns a GitHubSourceProvider."""
        with patch(
            "app.services.source_providers.github.GitHubSourceProvider",
        ) as mock_gh_class:
            mock_gh_class.__name__ = "GitHubSourceProvider"
            mock_instance = MagicMock(spec=BaseSourceProvider)
            mock_gh_class.return_value = mock_instance

            result = await create_source_provider(github_provider_db, "test-token")

        mock_gh_class.assert_called_once_with(github_provider_db, "test-token")
        assert result is mock_instance

    @pytest.mark.asyncio
    async def test_create_gitlab_provider(self, gitlab_provider_db):
        """create_source_provider with GitLab type returns a GitLabSourceProvider."""
        with patch(
            "app.services.source_providers.gitlab.GitLabSourceProvider",
        ) as mock_gl_class:
            mock_gl_class.__name__ = "GitLabSourceProvider"
            mock_instance = MagicMock(spec=BaseSourceProvider)
            mock_gl_class.return_value = mock_instance

            result = await create_source_provider(gitlab_provider_db, "test-token-gl")

        mock_gl_class.assert_called_once_with(gitlab_provider_db, "test-token-gl")
        assert result is mock_instance

    @pytest.mark.asyncio
    async def test_create_provider_unknown_type(self):
        """create_source_provider with unsupported type raises ValueError."""
        sp = MagicMock(spec=SourceProvider)
        sp.provider_type = "unsupported_type"
        with pytest.raises(ValueError, match="Unsupported provider type"):
            await create_source_provider(sp, "test-token")

    @pytest.mark.asyncio
    async def test_create_generic_provider(self, generic_provider_db):
        """create_source_provider with generic type returns a GenericGitSourceProvider."""
        with patch(
            "app.services.source_providers.generic_git.GenericGitSourceProvider",
        ) as mock_gen_class:
            mock_gen_class.__name__ = "GenericGitSourceProvider"
            mock_instance = MagicMock(spec=BaseSourceProvider)
            mock_gen_class.return_value = mock_instance

            result = await create_source_provider(generic_provider_db, "test-token-generic")

        mock_gen_class.assert_called_once_with(generic_provider_db, "test-token-generic")
        assert result is mock_instance

    @pytest.mark.asyncio
    async def test_create_provider_passes_credential(self, github_provider_db):
        """create_source_provider passes credential_secret to the constructor."""
        with patch(
            "app.services.source_providers.github.GitHubSourceProvider",
        ) as mock_gh_class:
            mock_gh_class.__name__ = "GitHubSourceProvider"
            mock_instance = MagicMock(spec=BaseSourceProvider)
            mock_gh_class.return_value = mock_instance

            await create_source_provider(github_provider_db, "my-secret-token")

        mock_gh_class.assert_called_once_with(github_provider_db, "my-secret-token")

    @pytest.mark.asyncio
    async def test_create_anon_provider_passes_none_credential(self):
        """create_source_provider with is_anon=True passes credential_secret=None."""
        sp = SourceProvider(
            id=10,
            label="Test Anon GitHub",
            provider_type=ProviderType.github,
            is_anon=True,
            is_deleted=False,
        )

        with patch(
            "app.services.source_providers.github.GitHubSourceProvider",
        ) as mock_gh_class:
            mock_gh_class.__name__ = "GitHubSourceProvider"
            mock_instance = MagicMock(spec=BaseSourceProvider)
            mock_gh_class.return_value = mock_instance

            await create_source_provider(sp, "this-should-be-ignored")

        mock_gh_class.assert_called_once_with(sp, None)

    @pytest.mark.asyncio
    async def test_create_anon_provider_raises_without_credential_when_not_anon(self):
        """create_source_provider raises ValueError when not is_anon and no credential_secret."""
        sp = SourceProvider(
            id=11,
            label="Test Auth GitHub",
            provider_type=ProviderType.github,
            is_anon=False,
            is_deleted=False,
        )

        with pytest.raises(ValueError, match="no credential_secret provided"):
            await create_source_provider(sp, None)

    @pytest.mark.asyncio
    async def test_create_anon_gitlab_provider(self):
        """create_source_provider with is_anon GitLab passes None credential."""
        sp = SourceProvider(
            id=12,
            label="Test Anon GitLab",
            provider_type=ProviderType.gitlab,
            is_anon=True,
            is_deleted=False,
        )

        with patch(
            "app.services.source_providers.gitlab.GitLabSourceProvider",
        ) as mock_gl_class:
            mock_gl_class.__name__ = "GitLabSourceProvider"
            mock_instance = MagicMock(spec=BaseSourceProvider)
            mock_gl_class.return_value = mock_instance

            await create_source_provider(sp, "ignored")

        mock_gl_class.assert_called_once_with(sp, None)

    @pytest.mark.asyncio
    async def test_create_anon_generic_provider(self):
        """create_source_provider with is_anon Generic passes None credential."""
        sp = SourceProvider(
            id=13,
            label="Test Anon Generic",
            provider_type=ProviderType.generic,
            is_anon=True,
            is_deleted=False,
        )

        with patch(
            "app.services.source_providers.generic_git.GenericGitSourceProvider",
        ) as mock_gen_class:
            mock_gen_class.__name__ = "GenericGitSourceProvider"
            mock_instance = MagicMock(spec=BaseSourceProvider)
            mock_gen_class.return_value = mock_instance

            await create_source_provider(sp, "ignored")

        mock_gen_class.assert_called_once_with(sp, None)
