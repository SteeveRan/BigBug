"""
@file test_source_provider_dispatcher.py
@description Unit tests for ProviderDispatcher — get_provider_class() and
             create_source_provider() factory functions.
@dependencies pytest, unittest.mock
@relatedFiles ../../app/services/source_providers/dispatcher.py,
              ../../app/services/source_providers/github.py,
              ../../app/services/source_providers/gitlab.py,
              ../../app/models/resource_provider.py
"""

from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import BadRequestError
from app.models.credential import Credential, CredentialType
from app.models.resource_provider import (
    ProviderCategory,
    ProviderDirection,
    ProviderDomain,
    ProviderSubtype,
    ResourceProvider,
)
from app.services.source_provider import BaseSourceProvider
from app.services.source_providers.dispatcher import (
    create_source_provider,
    get_provider_class,
)
from app.services.source_providers.generic_git import GenericGitSourceProvider
from app.services.source_providers.github import GitHubSourceProvider
from app.services.source_providers.gitlab import GitLabSourceProvider

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(
    *, id: int, label: str, subtype: ProviderSubtype, credential: Credential | None = None
) -> ResourceProvider:
    """Build a detached git/external ResourceProvider for the dispatcher."""
    provider = ResourceProvider(
        id=id,
        domain=ProviderDomain.git,
        subtype=subtype,
        category=ProviderCategory.public,
        direction=ProviderDirection.external,
        name=label,
        label=label,
        credential_id=credential.id if credential is not None else None,
    )
    if credential is not None:
        provider.credential = credential
    return provider


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def github_provider_db():
    """Create a GitHub ResourceProvider ORM model."""
    credential = Credential(
        id=1,
        name="test-github",
        credential_type=CredentialType.github_token,
        provider="github",
        encrypted_secret="encrypted:test-token",
    )
    return _make_provider(
        id=1,
        label="Test GitHub",
        subtype=ProviderSubtype.github,
        credential=credential,
    )


@pytest.fixture
def gitlab_provider_db():
    """Create a GitLab ResourceProvider ORM model."""
    credential = Credential(
        id=2,
        name="test-gitlab",
        credential_type=CredentialType.gitlab_token,
        provider="gitlab",
        encrypted_secret="encrypted:test-token-gitlab",
    )
    return _make_provider(
        id=2,
        label="Test GitLab",
        subtype=ProviderSubtype.gitlab,
        credential=credential,
    )


@pytest.fixture
def generic_provider_db():
    """Create a GenericGit ResourceProvider ORM model."""
    credential = Credential(
        id=3,
        name="test-generic",
        credential_type=CredentialType.https_basic,
        provider="generic",
        encrypted_secret="encrypted:test-token-generic",
    )
    return _make_provider(
        id=3,
        label="Test Generic",
        subtype=ProviderSubtype.generic_git,
        credential=credential,
    )


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

        mock_gh_class.assert_called_once()
        adapter, secret = mock_gh_class.call_args[0]
        assert adapter.provider_type == "github"
        assert adapter.label == "Test GitHub"
        assert secret == "test-token"
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

        mock_gl_class.assert_called_once()
        adapter, secret = mock_gl_class.call_args[0]
        assert adapter.provider_type == "gitlab"
        assert adapter.label == "Test GitLab"
        assert secret == "test-token-gl"
        assert result is mock_instance

    @pytest.mark.asyncio
    async def test_create_provider_unknown_type(self):
        """create_source_provider with unsupported git subtype raises BadRequestError."""
        sp = MagicMock(spec=ResourceProvider)
        sp.domain = ProviderDomain.git
        sp.direction = ProviderDirection.external
        sp.subtype = "unsupported_type"
        sp.id = 99
        with pytest.raises(BadRequestError, match="is not a git source"):
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

        mock_gen_class.assert_called_once()
        adapter, secret = mock_gen_class.call_args[0]
        assert adapter.provider_type == "generic"
        assert adapter.label == "Test Generic"
        assert secret == "test-token-generic"
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

        mock_gh_class.assert_called_once()
        assert mock_gh_class.call_args[0][1] == "my-secret-token"

    @pytest.mark.asyncio
    async def test_create_anon_provider_passes_none_credential(self):
        """create_source_provider with anon provider passes credential_secret=None."""
        sp = _make_provider(
            id=10,
            label="Test Anon GitHub",
            subtype=ProviderSubtype.github,
        )

        with patch(
            "app.services.source_providers.github.GitHubSourceProvider",
        ) as mock_gh_class:
            mock_gh_class.__name__ = "GitHubSourceProvider"
            mock_instance = MagicMock(spec=BaseSourceProvider)
            mock_gh_class.return_value = mock_instance

            await create_source_provider(sp, "this-should-be-ignored")

        mock_gh_class.assert_called_once()
        adapter, secret = mock_gh_class.call_args[0]
        assert adapter.is_anon is True
        assert secret is None

    @pytest.mark.asyncio
    async def test_create_anon_provider_raises_without_credential_when_not_anon(self):
        """create_source_provider raises ValueError when not anon and no credential_secret."""
        credential = Credential(
            id=11,
            name="test-auth-github",
            credential_type=CredentialType.github_token,
            provider="github",
            encrypted_secret="encrypted:test-token",
        )
        sp = _make_provider(
            id=11,
            label="Test Auth GitHub",
            subtype=ProviderSubtype.github,
            credential=credential,
        )

        with pytest.raises(ValueError, match="no credential_secret provided"):
            await create_source_provider(sp, None)

    @pytest.mark.asyncio
    async def test_create_anon_gitlab_provider(self):
        """create_source_provider with anon GitLab passes None credential."""
        sp = _make_provider(
            id=12,
            label="Test Anon GitLab",
            subtype=ProviderSubtype.gitlab,
        )

        with patch(
            "app.services.source_providers.gitlab.GitLabSourceProvider",
        ) as mock_gl_class:
            mock_gl_class.__name__ = "GitLabSourceProvider"
            mock_instance = MagicMock(spec=BaseSourceProvider)
            mock_gl_class.return_value = mock_instance

            await create_source_provider(sp, "ignored")

        mock_gl_class.assert_called_once()
        adapter, secret = mock_gl_class.call_args[0]
        assert adapter.provider_type == "gitlab"
        assert adapter.is_anon is True
        assert secret is None

    @pytest.mark.asyncio
    async def test_create_anon_generic_provider(self):
        """create_source_provider with anon Generic passes None credential."""
        sp = _make_provider(
            id=13,
            label="Test Anon Generic",
            subtype=ProviderSubtype.generic_git,
        )

        with patch(
            "app.services.source_providers.generic_git.GenericGitSourceProvider",
        ) as mock_gen_class:
            mock_gen_class.__name__ = "GenericGitSourceProvider"
            mock_instance = MagicMock(spec=BaseSourceProvider)
            mock_gen_class.return_value = mock_instance

            await create_source_provider(sp, "ignored")

        mock_gen_class.assert_called_once()
        adapter, secret = mock_gen_class.call_args[0]
        assert adapter.provider_type == "generic"
        assert adapter.is_anon is True
        assert secret is None
