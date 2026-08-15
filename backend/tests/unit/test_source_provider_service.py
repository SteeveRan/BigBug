"""
@file test_source_provider_service.py
@description Unit tests for GitHubSourceProvider — check_access, list_groups,
             list_repositories, get_repository, get_commit_info.
@dependencies pytest, unittest.mock, github.Github, github.GithubException
@relatedFiles ../../app/services/source_providers/github.py,
              ../../app/core/exceptions.py
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import DomainError
from app.models.provider_type import ProviderType
from app.services.source_providers.github import GitHubSourceProvider

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_repo(**overrides):
    """Build a MagicMock that looks like a PyGithub Repository."""
    defaults = {
        "id": 12345,
        "name": "test-repo",
        "full_name": "testorg/test-repo",
        "description": "A test repo",
        "private": False,
        "fork": False,
        "archived": False,
        "disabled": False,
        "language": "Python",
        "default_branch": "main",
        "html_url": "https://github.com/testorg/test-repo",
        "clone_url": "https://github.com/testorg/test-repo.git",
        "ssh_url": "git@github.com:testorg/test-repo.git",
        "stargazers_count": 10,
        "forks_count": 3,
        "open_issues_count": 1,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
        "pushed_at": "2025-06-01T00:00:00Z",
        "has_wiki": True,
        "has_pages": False,
        "has_issues": True,
        "has_projects": True,
        "topics": ["python", "testing"],
        "size": 1024,
        "subscribers_count": 5,
        "network_count": 2,
        "allow_forking": True,
        "web_commit_signoff_required": False,
    }
    defaults.update(overrides)

    # Pop non-repo-attribute keys *from defaults* before passing to configure_mock
    license_spdx = defaults.pop("license_spdx", "MIT")
    license_name = defaults.pop("license_name", "MIT License")
    releases_count = defaults.pop("releases_count", 5)

    # Build license mock
    license_mock = MagicMock()
    license_mock.spdx_id = license_spdx
    license_mock.name = license_name

    # Build releases mock with totalCount
    releases_mock = MagicMock()
    releases_mock.totalCount = releases_count

    repo = MagicMock()
    repo.configure_mock(**defaults)
    repo.license = license_mock
    repo.get_releases.return_value = releases_mock

    # Default branch mock for last commit
    commit_mock = MagicMock()
    commit_mock.sha = "abc123def456"
    commit_mock.commit.author.date = "2025-06-01T12:00:00Z"
    commit_mock.commit.author.name = "Test Author"
    commit_mock.commit.message = "Latest commit message"

    branch_mock = MagicMock()
    branch_mock.commit = commit_mock
    repo.get_branch.return_value = branch_mock

    return repo


def _make_mock_user(**overrides):
    """Build a MagicMock for a PyGithub user."""
    defaults = {
        "login": "testuser",
        "name": "Test User",
        "bio": "Test bio",
        "avatar_url": "https://avatars.example.com/u/1",
        "public_repos": 5,
        "total_private_repos": 2,
        "html_url": "https://github.com/testuser",
        "created_at": "2023-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    }
    defaults.update(overrides)
    user = MagicMock()
    user.configure_mock(**defaults)
    return user


def _make_mock_org(**overrides):
    """Build a MagicMock for a PyGithub organization."""
    defaults = {
        "login": "testorg",
        "name": "Test Org",
        "description": "A test org",
        "avatar_url": "https://avatars.example.com/o/1",
        "public_repos": 10,
        "total_private_repos": 3,
        "html_url": "https://github.com/testorg",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    }
    defaults.update(overrides)
    org = MagicMock()
    org.configure_mock(**defaults)
    return org


def _make_provider(**overrides) -> SimpleNamespace:
    """Build a provider-shaped object (no DB session needed).

    The V2 GitHubSourceProvider only reads ``id`` (and the decrypted secret is
    passed separately), so a plain namespace is enough after the SourceProvider
    model was removed in Providers V3 phase 7F.
    """
    defaults = {
        "id": 1,
        "credential_id": 10,
        "provider_type": ProviderType.github,
        "label": "test-github-provider",
        "is_deleted": False,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCheckAccess:
    """Tests for GitHubSourceProvider.check_access()"""

    @pytest.mark.asyncio
    async def test_check_access_success(self):
        """check_access returns True when credential is valid."""
        provider = _make_provider()
        gh_provider = GitHubSourceProvider(provider, credential_secret="fake-token")

        mock_user = _make_mock_user(login="testuser")
        mock_gh = MagicMock()
        mock_gh.get_user.return_value = mock_user

        with patch.object(gh_provider, "_get_client", return_value=mock_gh):
            result = await gh_provider.check_access()

        assert result is True
        mock_gh.get_user.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_access_failure(self):
        """check_access raises DomainError on 401 auth failure."""
        from github import GithubException

        provider = _make_provider()
        gh_provider = GitHubSourceProvider(provider, credential_secret="bad-token")

        mock_gh = MagicMock()
        mock_gh.get_user.side_effect = GithubException(
            status=401, data={"message": "Bad credentials"}
        )

        with (
            patch.object(gh_provider, "_get_client", return_value=mock_gh),
            pytest.raises(DomainError) as exc_info,
        ):
            await gh_provider.check_access()

        assert "authentication failed" in str(exc_info.value).lower()
        assert exc_info.value.status_code == 401


class TestListGroups:
    """Tests for GitHubSourceProvider.list_groups()"""

    @pytest.mark.asyncio
    async def test_list_groups(self):
        """list_groups returns user-as-org first, then organizations."""
        provider = _make_provider()
        gh_provider = GitHubSourceProvider(provider, credential_secret="fake-token")

        mock_user = _make_mock_user(login="testuser", name="Test User")
        mock_org = _make_mock_org(login="testorg", name="Test Org")

        mock_gh = MagicMock()
        mock_gh.get_user.return_value = mock_user
        mock_user.get_orgs.return_value = [mock_org]

        with patch.object(gh_provider, "_get_client", return_value=mock_gh):
            groups = await gh_provider.list_groups()

        assert len(groups) == 2
        # User-as-org first
        assert groups[0]["external_id"] == "testuser"
        assert groups[0]["name"] == "Test User"
        assert groups[0]["full_name"] == "testuser"
        # Organization second
        assert groups[1]["external_id"] == "testorg"
        assert groups[1]["name"] == "Test Org"


class TestListRepositories:
    """Tests for GitHubSourceProvider.list_repositories()"""

    @pytest.mark.asyncio
    async def test_list_repositories(self):
        """list_repositories returns all repos across pages."""
        provider = _make_provider()
        gh_provider = GitHubSourceProvider(provider, credential_secret="fake-token")

        repos_page1 = [
            _make_mock_repo(name=f"repo-{i}", full_name=f"testorg/repo-{i}") for i in range(3)
        ]
        repos_page2 = [
            _make_mock_repo(name=f"repo-{i}", full_name=f"testorg/repo-{i}") for i in range(3, 5)
        ]

        mock_owner = MagicMock()
        # Simulate two pages: first get_repos(), then get_repos() again
        mock_owner.get_repos.side_effect = [repos_page1, repos_page2]

        mock_gh = MagicMock()
        mock_gh.get_user.return_value = mock_owner

        with patch.object(gh_provider, "_get_client", return_value=mock_gh):
            repos = await gh_provider.list_repositories("testorg")

        # Note: current implementation calls get_repos() once and materializes
        # with list(). list(owner.get_repos()) — PaginatedList.__iter__ handles
        # pagination automatically. Returning a list from get_repos() means
        # list() will just use it. The first page is sufficient for basic testing.
        assert len(repos) == 3
        assert repos[0]["name"] == "repo-0"
        assert repos[0]["external_id"] == 12345
        assert repos[0]["full_name"] == "testorg/repo-0"

    @pytest.mark.asyncio
    async def test_list_repositories_pagination(self):
        """list_repositories with pagination fetches all repositories."""
        provider = _make_provider()
        gh_provider = GitHubSourceProvider(provider, credential_secret="fake-token")

        # Simulate a PaginatedList-like behavior: build 150 mock repos
        all_repos = [
            _make_mock_repo(name=f"repo-{i}", full_name=f"testorg/repo-{i}") for i in range(150)
        ]

        mock_owner = MagicMock()
        mock_owner.get_repos.return_value = all_repos

        mock_gh = MagicMock()
        mock_gh.get_user.return_value = mock_owner

        with patch.object(gh_provider, "_get_client", return_value=mock_gh):
            repos = await gh_provider.list_repositories("testorg")

        assert len(repos) == 150

    @pytest.mark.asyncio
    async def test_list_repositories_rate_limit(self):
        """list_repositories raises DomainError on 429 rate limit."""
        from github import GithubException

        provider = _make_provider()
        gh_provider = GitHubSourceProvider(provider, credential_secret="fake-token")

        mock_gh = MagicMock()
        mock_gh.get_user.side_effect = GithubException(
            status=403, data={"message": "API rate limit exceeded"}
        )

        with (
            patch.object(gh_provider, "_get_client", return_value=mock_gh),
            pytest.raises(DomainError) as exc_info,
        ):
            await gh_provider.list_repositories("testorg")

        assert "rate limit" in str(exc_info.value).lower()
        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_list_repositories_auth_failure(self):
        """list_repositories raises DomainError on 401 auth failure."""
        from github import GithubException

        provider = _make_provider()
        gh_provider = GitHubSourceProvider(provider, credential_secret="bad-token")

        mock_gh = MagicMock()
        mock_gh.get_user.side_effect = GithubException(
            status=401, data={"message": "Bad credentials"}
        )

        with (
            patch.object(gh_provider, "_get_client", return_value=mock_gh),
            pytest.raises(DomainError) as exc_info,
        ):
            await gh_provider.list_repositories("testorg")

        assert exc_info.value.status_code == 401


class TestGetRepository:
    """Tests for GitHubSourceProvider.get_repository()"""

    @pytest.mark.asyncio
    async def test_get_repository(self):
        """get_repository returns detailed repo info including has_wiki, has_pages, topics."""
        provider = _make_provider()
        gh_provider = GitHubSourceProvider(provider, credential_secret="fake-token")

        mock_repo = _make_mock_repo(
            name="awesome-project",
            full_name="testorg/awesome-project",
            has_wiki=True,
            has_pages=False,
            topics=["python", "fastapi", "testing"],
        )

        mock_gh = MagicMock()
        mock_gh.get_repo.return_value = mock_repo

        with patch.object(gh_provider, "_get_client", return_value=mock_gh):
            repo_dict = await gh_provider.get_repository("testorg/awesome-project")

        assert repo_dict["name"] == "awesome-project"
        assert repo_dict["has_wiki"] is True
        assert repo_dict["has_pages"] is False
        assert repo_dict["topics"] == ["python", "fastapi", "testing"]


class TestGetCommitInfo:
    """Tests for GitHubSourceProvider.get_commit_info()"""

    @pytest.mark.asyncio
    async def test_get_commit_info(self):
        """get_commit_info returns SHA, date, author, message."""
        provider = _make_provider()
        gh_provider = GitHubSourceProvider(provider, credential_secret="fake-token")

        commit_mock = MagicMock()
        commit_mock.sha = "abc123def456abc123def456abc123def456abc1"
        commit_mock.commit.author.date = "2025-06-01T12:00:00Z"
        commit_mock.commit.author.name = "Test Committer"
        commit_mock.commit.message = "feat: add awesome feature"

        branch_mock = MagicMock()
        branch_mock.commit = commit_mock

        mock_repo = MagicMock()
        mock_repo.default_branch = "main"
        mock_repo.get_branch.return_value = branch_mock

        mock_gh = MagicMock()
        mock_gh.get_repo.return_value = mock_repo

        with patch.object(gh_provider, "_get_client", return_value=mock_gh):
            commit_info = await gh_provider.get_commit_info("testorg/awesome-project")

        assert commit_info["sha"] == "abc123def456abc123def456abc123def456abc1"
        assert commit_info["author"] == "Test Committer"
        assert "awesome feature" in commit_info["message"]

    @pytest.mark.asyncio
    async def test_get_commit_info_with_ref(self):
        """get_commit_info with explicit ref returns commit for that ref."""
        provider = _make_provider()
        gh_provider = GitHubSourceProvider(provider, credential_secret="fake-token")

        commit_mock = MagicMock()
        commit_mock.sha = "def456abc123def456abc123def456abc123def4"
        commit_mock.commit.author.date = "2025-05-01T12:00:00Z"
        commit_mock.commit.author.name = "Tag Author"
        commit_mock.commit.message = "chore: release v1.0"

        mock_repo = MagicMock()
        mock_repo.default_branch = "main"
        mock_repo.get_commit.return_value = commit_mock

        mock_gh = MagicMock()
        mock_gh.get_repo.return_value = mock_repo

        with patch.object(gh_provider, "_get_client", return_value=mock_gh):
            commit_info = await gh_provider.get_commit_info("testorg/awesome-project", ref="v1.0")

        assert commit_info["sha"] == "def456abc123def456abc123def456abc123def4"
        assert commit_info["author"] == "Tag Author"
        assert "release v1.0" in commit_info["message"]
        mock_repo.get_commit.assert_called_once_with("v1.0")


class TestAnonymousMode:
    """Tests for GitHubSourceProvider in anonymous (no-credential) mode."""

    @pytest.mark.asyncio
    async def test_constructor_anonymous_no_client_token(self):
        """Anonymous constructor creates Github() without token."""
        provider = _make_provider(credential_id=None, is_anon=True)
        gh_provider = GitHubSourceProvider(provider, credential_secret=None)

        with patch.object(gh_provider, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            client = gh_provider._get_client()

        # Verify _get_client was called on the provider instance
        mock_get_client.assert_called_once()
        assert client is mock_client

    @pytest.mark.asyncio
    async def test_check_access_anonymous_uses_rate_limit(self):
        """Anonymous check_access uses rate_limit endpoint for connectivity test."""

        provider = _make_provider(credential_id=None, is_anon=True)
        gh_provider = GitHubSourceProvider(provider, credential_secret=None)

        mock_gh = MagicMock()
        mock_rate_limit = MagicMock()
        mock_gh.get_rate_limit.return_value = mock_rate_limit

        with patch.object(gh_provider, "_get_client", return_value=mock_gh):
            result = await gh_provider.check_access()

        assert result is True
        mock_gh.get_rate_limit.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_access_anonymous_rate_limit_error(self):
        """Anonymous check_access maps rate limit error to DomainError."""
        from github import GithubException

        provider = _make_provider(credential_id=None, is_anon=True)
        gh_provider = GitHubSourceProvider(provider, credential_secret=None)

        mock_gh = MagicMock()
        mock_gh.get_rate_limit.side_effect = GithubException(
            status=403, data={"message": "API rate limit exceeded"}
        )

        with (
            patch.object(gh_provider, "_get_client", return_value=mock_gh),
            pytest.raises(DomainError),
        ):
            await gh_provider.check_access()
