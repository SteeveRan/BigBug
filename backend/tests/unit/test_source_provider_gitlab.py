"""
@file test_source_provider_gitlab.py
@description Unit tests for GitLabSourceProvider — check_access, list_groups,
             list_repositories, get_repository, get_commit_info, import_group,
             exception mapping, and initialization.
@dependencies pytest, unittest.mock, gitlab.Gitlab, gitlab.exceptions
@relatedFiles ../../app/services/source_providers/gitlab.py,
              ../../app/core/exceptions.py
"""

from unittest.mock import MagicMock, patch

import pytest
from gitlab.exceptions import GitlabAuthenticationError, GitlabError

from app.core.exceptions import DomainError
from app.models.credential import Credential, CredentialType
from app.models.source_provider import ProviderType, SourceProvider
from app.services.source_providers.gitlab import (
    GitLabSourceProvider,
    _map_gitlab_exception,
    _resolve_license_spdx,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_credential(**overrides) -> Credential:
    """Build a Credential ORM model for GitLab."""
    defaults = {
        "id": 1,
        "name": "test-gitlab-credential",
        "credential_type": CredentialType.gitlab_token,
        "provider": "gitlab",
        "encrypted_secret": "encrypted:test-token-gitlab",
        "base_url": "https://gitlab.example.com",
    }
    defaults.update(overrides)
    return Credential(**defaults)


def _make_provider(**overrides) -> SourceProvider:
    """Build a SourceProvider ORM model for GitLab (no DB session needed)."""
    credential = overrides.pop("credential", _make_credential())
    defaults = {
        "id": 1,
        "credential_id": 1,
        "provider_type": ProviderType.gitlab,
        "label": "Test GitLab Provider",
        "is_deleted": False,
    }
    defaults.update(overrides)
    sp = SourceProvider(**defaults)
    sp.credential = credential
    return sp


def _make_mock_group(**overrides):
    """Build a MagicMock that looks like a python-gitlab Group."""
    defaults = {
        "id": 42,
        "name": "Test Group",
        "full_name": "Test Group",
        "full_path": "test-group",
        "description": "A test group",
        "web_url": "https://gitlab.example.com/groups/test-group",
        "avatar_url": "https://gitlab.example.com/uploads/group/avatar/42/avatar.png",
        "parent_id": None,
    }
    defaults.update(overrides)
    group = MagicMock()
    group.configure_mock(**defaults)
    return group


def _make_mock_project(**overrides):
    """Build a MagicMock that looks like a python-gitlab Project."""
    defaults = {
        "id": 12345,
        "name": "test-project",
        "name_with_namespace": None,
        "path_with_namespace": "test-group/test-project",
        "description": "A test project",
        "default_branch": "main",
        "web_url": "https://gitlab.example.com/test-group/test-project",
        "ssh_url_to_repo": "git@gitlab.example.com:test-group/test-project.git",
        "http_url_to_repo": "https://gitlab.example.com/test-group/test-project.git",
        "archived": False,
        "visibility": "private",
    }
    defaults.update(overrides)
    project = MagicMock()
    project.configure_mock(**defaults)
    return project


# ---------------------------------------------------------------------------
# Tests: Initialization
# ---------------------------------------------------------------------------


class TestInit:
    """Tests for GitLabSourceProvider.__init__()"""

    @pytest.mark.asyncio
    async def test_init_with_custom_url(self):
        """GitLab client is created with credential base_url and token."""
        mock_gitlab_cls = MagicMock()

        with patch(
            "app.services.source_providers.gitlab.gitlab.Gitlab",
            mock_gitlab_cls,
        ):
            provider = _make_provider()
            GitLabSourceProvider(provider, credential_secret="test-token-123")

        mock_gitlab_cls.assert_called_once_with(
            url="https://gitlab.example.com",
            private_token="test-token-123",
        )

    @pytest.mark.asyncio
    async def test_init_defaults_to_gitlab_com(self):
        """When credential has no base_url, defaults to gitlab.com."""
        mock_gitlab_cls = MagicMock()

        with patch(
            "app.services.source_providers.gitlab.gitlab.Gitlab",
            mock_gitlab_cls,
        ):
            credential = _make_credential(base_url=None)
            provider = _make_provider(credential=credential)
            GitLabSourceProvider(provider, credential_secret="test-token-123")

        mock_gitlab_cls.assert_called_once_with(
            url="https://gitlab.com",
            private_token="test-token-123",
        )

    @pytest.mark.asyncio
    async def test_init_no_credential_defaults_to_gitlab_com(self):
        """When provider has no credential at all, defaults to gitlab.com."""
        mock_gitlab_cls = MagicMock()

        with patch(
            "app.services.source_providers.gitlab.gitlab.Gitlab",
            mock_gitlab_cls,
        ):
            sp = SourceProvider(
                id=1,
                credential_id=None,
                provider_type=ProviderType.gitlab,
                label="No-Cred Provider",
                is_deleted=False,
            )
            sp.credential = None
            GitLabSourceProvider(sp, credential_secret="test-token-123")

        mock_gitlab_cls.assert_called_once_with(
            url="https://gitlab.com",
            private_token="test-token-123",
        )

    def test_repr_hides_token(self):
        """repr() does not expose the access token."""
        mock_gitlab_cls = MagicMock()

        with patch(
            "app.services.source_providers.gitlab.gitlab.Gitlab",
            mock_gitlab_cls,
        ):
            provider = _make_provider()
            gl_provider = GitLabSourceProvider(provider, credential_secret="secret-token")

        r = repr(gl_provider)
        assert "secret-token" not in r
        assert "***" in r
        assert "provider_id=1" in r
        assert "gitlab.example.com" in r


# ---------------------------------------------------------------------------
# Tests: check_access
# ---------------------------------------------------------------------------


class TestCheckAccess:
    """Tests for GitLabSourceProvider.check_access()"""

    @pytest.mark.asyncio
    async def test_check_access_success(self):
        """check_access returns True when auth succeeds."""
        mock_gitlab_cls = MagicMock()

        with patch(
            "app.services.source_providers.gitlab.gitlab.Gitlab",
            mock_gitlab_cls,
        ):
            provider = _make_provider()
            gl_provider = GitLabSourceProvider(provider, credential_secret="fake-token")

        mock_gl = MagicMock()
        mock_gl.auth.return_value = True

        with patch.object(gl_provider, "_get_client", return_value=mock_gl):
            result = await gl_provider.check_access()

        assert result is True
        mock_gl.auth.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_access_failure(self):
        """check_access raises DomainError on auth failure."""
        mock_gitlab_cls = MagicMock()

        with patch(
            "app.services.source_providers.gitlab.gitlab.Gitlab",
            mock_gitlab_cls,
        ):
            provider = _make_provider()
            gl_provider = GitLabSourceProvider(provider, credential_secret="bad-token")

        mock_gl = MagicMock()
        mock_gl.auth.side_effect = GitlabAuthenticationError(
            response_code=401,
            error_message="401 Unauthorized",
        )

        with (
            patch.object(gl_provider, "_get_client", return_value=mock_gl),
            pytest.raises(DomainError) as exc_info,
        ):
            await gl_provider.check_access()

        assert exc_info.value.status_code == 401
        assert "authentication failed" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Tests: list_groups
# ---------------------------------------------------------------------------


class TestListGroups:
    """Tests for GitLabSourceProvider.list_groups()"""

    @pytest.mark.asyncio
    async def test_list_groups(self):
        """list_groups returns all groups with correct fields."""
        mock_gitlab_cls = MagicMock()

        with patch(
            "app.services.source_providers.gitlab.gitlab.Gitlab",
            mock_gitlab_cls,
        ):
            provider = _make_provider()
            gl_provider = GitLabSourceProvider(provider, credential_secret="fake-token")

        mock_group1 = _make_mock_group(
            id=42,
            name="Engineering",
            full_name="Engineering",
            full_path="engineering",
            description="Engineering department",
        )
        mock_group2 = _make_mock_group(
            id=99,
            name="DevOps",
            full_name="DevOps",
            full_path="devops",
            description="DevOps team",
            parent_id=42,
        )

        mock_gl = MagicMock()
        mock_gl.groups.list.return_value = [mock_group1, mock_group2]

        with patch.object(gl_provider, "_get_client", return_value=mock_gl):
            groups = await gl_provider.list_groups()

        assert len(groups) == 2
        assert groups[0]["external_id"] == 42
        assert groups[0]["name"] == "Engineering"
        assert groups[0]["full_name"] == "Engineering"
        assert groups[0]["full_path"] == "engineering"
        assert groups[0]["description"] == "Engineering department"
        assert "gitlab.example.com" in groups[0]["web_url"]
        assert groups[0]["avatar_url"] is not None
        assert groups[0]["parent_id"] is None

        assert groups[1]["external_id"] == 99
        assert groups[1]["name"] == "DevOps"
        assert groups[1]["parent_id"] == 42

    @pytest.mark.asyncio
    async def test_list_groups_empty(self):
        """list_groups returns empty list when no groups are accessible."""
        mock_gitlab_cls = MagicMock()

        with patch(
            "app.services.source_providers.gitlab.gitlab.Gitlab",
            mock_gitlab_cls,
        ):
            provider = _make_provider()
            gl_provider = GitLabSourceProvider(provider, credential_secret="fake-token")

        mock_gl = MagicMock()
        mock_gl.groups.list.return_value = []

        with patch.object(gl_provider, "_get_client", return_value=mock_gl):
            groups = await gl_provider.list_groups()

        assert len(groups) == 0

    @pytest.mark.asyncio
    async def test_list_groups_api_error(self):
        """list_groups raises DomainError on API error."""
        mock_gitlab_cls = MagicMock()

        with patch(
            "app.services.source_providers.gitlab.gitlab.Gitlab",
            mock_gitlab_cls,
        ):
            provider = _make_provider()
            gl_provider = GitLabSourceProvider(provider, credential_secret="fake-token")

        mock_gl = MagicMock()
        mock_gl.groups.list.side_effect = GitlabError(
            response_code=500,
            error_message="Internal Server Error",
        )

        with (
            patch.object(gl_provider, "_get_client", return_value=mock_gl),
            pytest.raises(DomainError) as exc_info,
        ):
            await gl_provider.list_groups()

        assert exc_info.value.status_code == 502


# ---------------------------------------------------------------------------
# Tests: list_repositories
# ---------------------------------------------------------------------------


class TestListRepositories:
    """Tests for GitLabSourceProvider.list_repositories()"""

    @pytest.mark.asyncio
    async def test_list_repositories(self):
        """list_repositories returns projects in a group with correct fields."""
        mock_gitlab_cls = MagicMock()

        with patch(
            "app.services.source_providers.gitlab.gitlab.Gitlab",
            mock_gitlab_cls,
        ):
            provider = _make_provider()
            gl_provider = GitLabSourceProvider(provider, credential_secret="fake-token")

        mock_project = _make_mock_project(
            id=12345,
            name="awesome-project",
            path_with_namespace="engineering/awesome-project",
            visibility="public",
            default_branch="develop",
        )

        mock_group = MagicMock()
        mock_group.projects.list.return_value = [mock_project]

        mock_gl = MagicMock()
        mock_gl.groups.get.return_value = mock_group

        with patch.object(gl_provider, "_get_client", return_value=mock_gl):
            repos = await gl_provider.list_repositories("42")

        assert len(repos) == 1
        repo = repos[0]
        assert repo["external_id"] == 12345
        assert repo["name"] == "awesome-project"
        assert repo["full_name"] == "engineering/awesome-project"
        assert repo["http_url"] == "https://gitlab.example.com/test-group/test-project.git"
        assert repo["ssh_url"] == "git@gitlab.example.com:test-group/test-project.git"
        assert repo["web_url"] == "https://gitlab.example.com/test-group/test-project"
        assert repo["is_archived"] is False
        assert repo["is_private"] is False  # visibility=public
        assert repo["default_branch"] == "develop"

    @pytest.mark.asyncio
    async def test_list_repositories_empty(self):
        """list_repositories returns empty list when group has no projects."""
        mock_gitlab_cls = MagicMock()

        with patch(
            "app.services.source_providers.gitlab.gitlab.Gitlab",
            mock_gitlab_cls,
        ):
            provider = _make_provider()
            gl_provider = GitLabSourceProvider(provider, credential_secret="fake-token")

        mock_group = MagicMock()
        mock_group.projects.list.return_value = []

        mock_gl = MagicMock()
        mock_gl.groups.get.return_value = mock_group

        with patch.object(gl_provider, "_get_client", return_value=mock_gl):
            repos = await gl_provider.list_repositories("42")

        assert len(repos) == 0

    @pytest.mark.asyncio
    async def test_list_repositories_invalid_id(self):
        """list_repositories raises DomainError(400) on non-integer group id."""
        mock_gitlab_cls = MagicMock()

        with patch(
            "app.services.source_providers.gitlab.gitlab.Gitlab",
            mock_gitlab_cls,
        ):
            provider = _make_provider()
            gl_provider = GitLabSourceProvider(provider, credential_secret="fake-token")

        with pytest.raises(DomainError) as exc_info:
            await gl_provider.list_repositories("not-a-number")

        assert exc_info.value.status_code == 400
        assert "invalid group_external_id" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_list_repositories_api_error(self):
        """list_repositories raises DomainError on API error."""
        mock_gitlab_cls = MagicMock()

        with patch(
            "app.services.source_providers.gitlab.gitlab.Gitlab",
            mock_gitlab_cls,
        ):
            provider = _make_provider()
            gl_provider = GitLabSourceProvider(provider, credential_secret="fake-token")

        mock_gl = MagicMock()
        mock_gl.groups.get.side_effect = GitlabError(
            response_code=403,
            error_message="Forbidden",
        )

        with (
            patch.object(gl_provider, "_get_client", return_value=mock_gl),
            pytest.raises(DomainError) as exc_info,
        ):
            await gl_provider.list_repositories("42")

        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Tests: get_repository
# ---------------------------------------------------------------------------


class TestGetRepository:
    """Tests for GitLabSourceProvider.get_repository()"""

    @pytest.mark.asyncio
    async def test_get_repository_basic(self):
        """get_repository returns basic project info."""
        mock_gitlab_cls = MagicMock()

        with patch(
            "app.services.source_providers.gitlab.gitlab.Gitlab",
            mock_gitlab_cls,
        ):
            provider = _make_provider()
            gl_provider = GitLabSourceProvider(provider, credential_secret="fake-token")

        mock_project = _make_mock_project(
            id=12345,
            name="awesome-project",
            path_with_namespace="engineering/awesome-project",
        )
        # Simulate: license is None
        mock_project.license = None
        # Simulate: repository_raw raises (no README)
        mock_project.repository_raw.side_effect = GitlabError(
            response_code=404,
            error_message="File not found",
        )
        # Simulate: releases.list raises (no releases)
        mock_project.releases.list.side_effect = GitlabError(
            response_code=404,
            error_message="Not found",
        )

        mock_gl = MagicMock()
        mock_gl.projects.get.return_value = mock_project

        with patch.object(gl_provider, "_get_client", return_value=mock_gl):
            repo = await gl_provider.get_repository("engineering/awesome-project")

        assert repo["external_id"] == 12345
        assert repo["name"] == "awesome-project"
        assert repo["full_name"] == "engineering/awesome-project"
        assert repo["license_spdx"] is None
        assert repo["license_name"] is None
        assert repo["readme_html"] is None
        assert repo["latest_release_tag"] is None
        assert repo["latest_release_name"] is None
        assert repo["latest_release_published_at"] is None
        assert repo["latest_release_author"] is None
        assert repo["latest_release_html_url"] is None

    @pytest.mark.asyncio
    async def test_get_repository_with_license(self):
        """get_repository resolves license SPDX and name."""
        mock_gitlab_cls = MagicMock()

        with patch(
            "app.services.source_providers.gitlab.gitlab.Gitlab",
            mock_gitlab_cls,
        ):
            provider = _make_provider()
            gl_provider = GitLabSourceProvider(provider, credential_secret="fake-token")

        mock_project = _make_mock_project(
            id=12345,
            name="licensed-project",
            path_with_namespace="engineering/licensed-project",
        )
        mock_project.license = {
            "key": "mit",
            "name": "MIT License",
        }
        mock_project.repository_raw.side_effect = GitlabError(response_code=404)
        mock_project.releases.list.side_effect = GitlabError(response_code=404)

        mock_gl = MagicMock()
        mock_gl.projects.get.return_value = mock_project

        with patch.object(gl_provider, "_get_client", return_value=mock_gl):
            repo = await gl_provider.get_repository("engineering/licensed-project")

        assert repo["license_spdx"] == "MIT"
        assert repo["license_name"] == "MIT License"

    @pytest.mark.asyncio
    async def test_get_repository_with_readme(self):
        """get_repository fetches and wraps README as HTML."""
        mock_gitlab_cls = MagicMock()

        with patch(
            "app.services.source_providers.gitlab.gitlab.Gitlab",
            mock_gitlab_cls,
        ):
            provider = _make_provider()
            gl_provider = GitLabSourceProvider(provider, credential_secret="fake-token")

        mock_project = _make_mock_project(
            id=12345,
            name="readme-project",
            path_with_namespace="engineering/readme-project",
        )
        mock_project.license = None
        mock_project.repository_raw.return_value = "# Hello World\nThis is a README."
        mock_project.releases.list.side_effect = GitlabError(response_code=404)

        mock_gl = MagicMock()
        mock_gl.projects.get.return_value = mock_project

        with patch.object(gl_provider, "_get_client", return_value=mock_gl):
            repo = await gl_provider.get_repository("engineering/readme-project")

        assert repo["readme_html"] is not None
        assert "gitlab-readme" in repo["readme_html"]
        assert "Hello World" in repo["readme_html"]

    @pytest.mark.asyncio
    async def test_get_repository_with_release(self):
        """get_repository returns latest release info."""
        mock_gitlab_cls = MagicMock()

        with patch(
            "app.services.source_providers.gitlab.gitlab.Gitlab",
            mock_gitlab_cls,
        ):
            provider = _make_provider()
            gl_provider = GitLabSourceProvider(provider, credential_secret="fake-token")

        mock_project = _make_mock_project(
            id=12345,
            name="released-project",
            path_with_namespace="engineering/released-project",
            web_url="https://gitlab.example.com/engineering/released-project",
        )
        mock_project.license = None
        mock_project.repository_raw.side_effect = GitlabError(response_code=404)

        mock_release = MagicMock()
        mock_release.tag_name = "v2.0.0"
        mock_release.name = "Version 2.0"
        mock_release.released_at = MagicMock()
        mock_release.released_at.isoformat.return_value = "2025-06-01T12:00:00+00:00"
        mock_release.author = {"name": "Release Bot"}

        mock_project.releases.list.return_value = [mock_release]

        mock_gl = MagicMock()
        mock_gl.projects.get.return_value = mock_project

        with patch.object(gl_provider, "_get_client", return_value=mock_gl):
            repo = await gl_provider.get_repository("engineering/released-project")

        assert repo["latest_release_tag"] == "v2.0.0"
        assert repo["latest_release_name"] == "Version 2.0"
        assert repo["latest_release_published_at"] == "2025-06-01T12:00:00+00:00"
        assert repo["latest_release_author"] == "Release Bot"
        assert "/-/releases/v2.0.0" in repo["latest_release_html_url"]

    @pytest.mark.asyncio
    async def test_get_repository_api_error(self):
        """get_repository raises DomainError on API error."""
        mock_gitlab_cls = MagicMock()

        with patch(
            "app.services.source_providers.gitlab.gitlab.Gitlab",
            mock_gitlab_cls,
        ):
            provider = _make_provider()
            gl_provider = GitLabSourceProvider(provider, credential_secret="fake-token")

        mock_gl = MagicMock()
        mock_gl.projects.get.side_effect = GitlabError(
            response_code=404,
            error_message="Project not found",
        )

        with (
            patch.object(gl_provider, "_get_client", return_value=mock_gl),
            pytest.raises(DomainError) as exc_info,
        ):
            await gl_provider.get_repository("nonexistent/project")

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Tests: get_commit_info
# ---------------------------------------------------------------------------


class TestGetCommitInfo:
    """Tests for GitLabSourceProvider.get_commit_info()"""

    @pytest.mark.asyncio
    async def test_get_commit_info_default_ref(self):
        """get_commit_info returns latest commit on default branch."""
        mock_gitlab_cls = MagicMock()

        with patch(
            "app.services.source_providers.gitlab.gitlab.Gitlab",
            mock_gitlab_cls,
        ):
            provider = _make_provider()
            gl_provider = GitLabSourceProvider(provider, credential_secret="fake-token")

        mock_commit = MagicMock()
        mock_commit.id = "abc123def456abc123def456abc123def456abc1"
        mock_commit.created_at = "2025-06-01T12:00:00Z"
        mock_commit.author_name = "Dev User"
        mock_commit.message = "feat: add awesome feature"

        mock_project = MagicMock()
        mock_project.commits.list.return_value = [mock_commit]

        mock_gl = MagicMock()
        mock_gl.projects.get.return_value = mock_project

        with patch.object(gl_provider, "_get_client", return_value=mock_gl):
            commit = await gl_provider.get_commit_info("engineering/awesome-project")

        assert commit["sha"] == "abc123def456abc123def456abc123def456abc1"
        assert commit["date"] == "2025-06-01T12:00:00Z"
        assert commit["author"] == "Dev User"
        assert commit["message"] == "feat: add awesome feature"

        # Verify ref_name was NOT passed (default branch used)
        mock_project.commits.list.assert_called_once_with(per_page=1)

    @pytest.mark.asyncio
    async def test_get_commit_info_with_ref(self):
        """get_commit_info with explicit ref passes ref_name parameter."""
        mock_gitlab_cls = MagicMock()

        with patch(
            "app.services.source_providers.gitlab.gitlab.Gitlab",
            mock_gitlab_cls,
        ):
            provider = _make_provider()
            gl_provider = GitLabSourceProvider(provider, credential_secret="fake-token")

        mock_commit = MagicMock()
        mock_commit.id = "def456abc123def456abc123def456abc123def4"
        mock_commit.created_at = "2025-05-01T12:00:00Z"
        mock_commit.author_name = "Tag Author"
        mock_commit.message = "chore: release v1.0"

        mock_project = MagicMock()
        mock_project.commits.list.return_value = [mock_commit]

        mock_gl = MagicMock()
        mock_gl.projects.get.return_value = mock_project

        with patch.object(gl_provider, "_get_client", return_value=mock_gl):
            commit = await gl_provider.get_commit_info("engineering/awesome-project", ref="v1.0")

        assert commit["sha"] == "def456abc123def456abc123def456abc123def4"
        assert commit["author"] == "Tag Author"
        assert "release v1.0" in commit["message"]
        mock_project.commits.list.assert_called_once_with(per_page=1, ref_name="v1.0")

    @pytest.mark.asyncio
    async def test_get_commit_info_empty(self):
        """get_commit_info raises DomainError(404) when no commits found."""
        mock_gitlab_cls = MagicMock()

        with patch(
            "app.services.source_providers.gitlab.gitlab.Gitlab",
            mock_gitlab_cls,
        ):
            provider = _make_provider()
            gl_provider = GitLabSourceProvider(provider, credential_secret="fake-token")

        mock_project = MagicMock()
        mock_project.commits.list.return_value = []

        mock_gl = MagicMock()
        mock_gl.projects.get.return_value = mock_project

        with (
            patch.object(gl_provider, "_get_client", return_value=mock_gl),
            pytest.raises(DomainError) as exc_info,
        ):
            await gl_provider.get_commit_info("engineering/empty-project")

        assert exc_info.value.status_code == 404
        assert "no commits found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_get_commit_info_api_error(self):
        """get_commit_info raises DomainError on API error."""
        mock_gitlab_cls = MagicMock()

        with patch(
            "app.services.source_providers.gitlab.gitlab.Gitlab",
            mock_gitlab_cls,
        ):
            provider = _make_provider()
            gl_provider = GitLabSourceProvider(provider, credential_secret="fake-token")

        mock_gl = MagicMock()
        mock_gl.projects.get.side_effect = GitlabError(
            response_code=403,
            error_message="Forbidden",
        )

        with (
            patch.object(gl_provider, "_get_client", return_value=mock_gl),
            pytest.raises(DomainError) as exc_info,
        ):
            await gl_provider.get_commit_info("private/project")

        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Tests: import_group
# ---------------------------------------------------------------------------


class TestImportGroup:
    """Tests for GitLabSourceProvider.import_group()"""

    @pytest.mark.asyncio
    async def test_import_group(self):
        """import_group returns group details by ID."""
        mock_gitlab_cls = MagicMock()

        with patch(
            "app.services.source_providers.gitlab.gitlab.Gitlab",
            mock_gitlab_cls,
        ):
            provider = _make_provider()
            gl_provider = GitLabSourceProvider(provider, credential_secret="fake-token")

        mock_group = _make_mock_group(
            id=42,
            name="Engineering",
            full_name="Engineering",
            full_path="engineering",
            description="Engineering department",
            web_url="https://gitlab.example.com/groups/engineering",
            avatar_url="https://gitlab.example.com/uploads/group/avatar/42/avatar.png",
            parent_id=None,
        )

        mock_gl = MagicMock()
        mock_gl.groups.get.return_value = mock_group

        with patch.object(gl_provider, "_get_client", return_value=mock_gl):
            group = await gl_provider.import_group("42")

        assert group["external_id"] == 42
        assert group["name"] == "Engineering"
        assert group["full_name"] == "Engineering"
        assert group["full_path"] == "engineering"
        assert group["description"] == "Engineering department"
        assert "gitlab.example.com" in group["web_url"]
        assert group["avatar_url"] is not None
        assert group["parent_id"] is None

    @pytest.mark.asyncio
    async def test_import_group_with_int_id(self):
        """import_group accepts an integer group_external_id."""
        mock_gitlab_cls = MagicMock()

        with patch(
            "app.services.source_providers.gitlab.gitlab.Gitlab",
            mock_gitlab_cls,
        ):
            provider = _make_provider()
            gl_provider = GitLabSourceProvider(provider, credential_secret="fake-token")

        mock_group = _make_mock_group(id=99, name="DevOps")

        mock_gl = MagicMock()
        mock_gl.groups.get.return_value = mock_group

        with patch.object(gl_provider, "_get_client", return_value=mock_gl):
            group = await gl_provider.import_group(99)

        assert group["external_id"] == 99
        mock_gl.groups.get.assert_called_once_with(99)

    @pytest.mark.asyncio
    async def test_import_group_invalid_id(self):
        """import_group raises DomainError(400) on non-integer id."""
        mock_gitlab_cls = MagicMock()

        with patch(
            "app.services.source_providers.gitlab.gitlab.Gitlab",
            mock_gitlab_cls,
        ):
            provider = _make_provider()
            gl_provider = GitLabSourceProvider(provider, credential_secret="fake-token")

        with pytest.raises(DomainError) as exc_info:
            await gl_provider.import_group("not-a-number")

        assert exc_info.value.status_code == 400
        assert "invalid group_external_id" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_import_group_api_error(self):
        """import_group raises DomainError on API error."""
        mock_gitlab_cls = MagicMock()

        with patch(
            "app.services.source_providers.gitlab.gitlab.Gitlab",
            mock_gitlab_cls,
        ):
            provider = _make_provider()
            gl_provider = GitLabSourceProvider(provider, credential_secret="fake-token")

        mock_gl = MagicMock()
        mock_gl.groups.get.side_effect = GitlabError(
            response_code=404,
            error_message="Group not found",
        )

        with (
            patch.object(gl_provider, "_get_client", return_value=mock_gl),
            pytest.raises(DomainError) as exc_info,
        ):
            await gl_provider.import_group("999")

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Tests: _map_gitlab_exception
# ---------------------------------------------------------------------------


class TestMapGitlabException:
    """Tests for _map_gitlab_exception() function."""

    def test_auth_error_maps_to_401(self):
        """GitlabAuthenticationError maps to 401."""
        exc = GitlabAuthenticationError(
            response_code=401,
            error_message="401 Unauthorized",
        )
        result = _map_gitlab_exception(exc, "check_access")
        assert result.status_code == 401
        assert "authentication failed" in str(result.detail).lower()

    def test_status_403_maps_to_403(self):
        """GitlabError with response_code=403 maps to 403."""
        exc = GitlabError(response_code=403, error_message="Forbidden")
        result = _map_gitlab_exception(exc, "list_groups")
        assert result.status_code == 403
        assert "access forbidden" in str(result.detail).lower()

    def test_status_404_maps_to_404(self):
        """GitlabError with response_code=404 maps to 404."""
        exc = GitlabError(response_code=404, error_message="Not found")
        result = _map_gitlab_exception(exc, "get_repository/foo/bar")
        assert result.status_code == 404
        assert "resource not found" in str(result.detail).lower()

    def test_status_422_maps_to_422(self):
        """GitlabError with response_code=422 maps to 422."""
        exc = GitlabError(response_code=422, error_message="Unprocessable")
        result = _map_gitlab_exception(exc, "import_group/42")
        assert result.status_code == 422
        assert "validation failed" in str(result.detail).lower()

    def test_status_429_maps_to_429(self):
        """GitlabError with response_code=429 maps to 429."""
        exc = GitlabError(response_code=429, error_message="Too Many Requests")
        result = _map_gitlab_exception(exc, "list_repositories/42")
        assert result.status_code == 429
        assert "rate limit" in str(result.detail).lower()

    def test_status_401_falls_into_auth(self):
        """GitlabError with response_code=401 maps to 401 even if not auth error class."""
        exc = GitlabError(response_code=401, error_message="Unauthorized")
        result = _map_gitlab_exception(exc, "check_access")
        assert result.status_code == 401

    def test_unknown_error_maps_to_502(self):
        """GitlabError with unrecognized response_code maps to 502."""
        exc = GitlabError(response_code=503, error_message="Service Unavailable")
        result = _map_gitlab_exception(exc, "list_groups")
        assert result.status_code == 502
        assert "status=503" in str(result.detail)

    def test_error_without_response_code_maps_to_502(self):
        """GitlabError without response_code maps to 502."""
        exc = GitlabError(error_message="Unknown network error")
        result = _map_gitlab_exception(exc, "list_groups")
        assert result.status_code == 502


# ---------------------------------------------------------------------------
# Tests: _resolve_license_spdx
# ---------------------------------------------------------------------------


class TestResolveLicenseSpdx:
    """Tests for _resolve_license_spdx() function."""

    def test_mit_key(self):
        """MIT license key maps to MIT SPDX."""
        spdx, name = _resolve_license_spdx({"key": "mit", "name": "MIT License"})
        assert spdx == "MIT"
        assert name == "MIT License"

    def test_apache_2_key(self):
        """Apache-2.0 key maps to Apache-2.0 SPDX."""
        spdx, name = _resolve_license_spdx({"key": "apache-2.0", "name": "Apache License 2.0"})
        assert spdx == "Apache-2.0"

    def test_gpl_3_key(self):
        """GPL-3.0 key maps to GPL-3.0-only SPDX."""
        spdx, name = _resolve_license_spdx(
            {"key": "gpl-3.0", "name": "GNU General Public License v3.0"}
        )
        assert spdx == "GPL-3.0-only"

    def test_full_name_fallback(self):
        """When key is unknown, full name is used as fallback."""
        spdx, name = _resolve_license_spdx({"key": "unknown-key", "name": "MIT License"})
        assert spdx == "MIT"

    def test_other_key_returns_none(self):
        """License key 'other' returns None SPDX."""
        spdx, name = _resolve_license_spdx({"key": "other", "name": "Other"})
        assert spdx is None
        assert name == "Other"

    def test_none_license(self):
        """None license returns None, None."""
        spdx, name = _resolve_license_spdx(None)
        assert spdx is None
        assert name is None

    def test_empty_dict_license(self):
        """Empty dict returns None, None."""
        spdx, name = _resolve_license_spdx({})
        assert spdx is None
        assert name is None

    def test_unknown_key_uppercase_fallback(self):
        """When key is not in mapping but looks valid, use uppercase key."""
        spdx, name = _resolve_license_spdx({"key": "bsl-1.0", "name": "Boost Software License 1.0"})
        assert spdx == "BSL-1.0"
        assert name == "Boost Software License 1.0"
