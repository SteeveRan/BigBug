"""
@file test_source_provider_generic_git.py
@description Unit tests for GenericGitSourceProvider — check_access, list_groups,
             list_repositories, get_repository, get_commit_info, verify_mirror,
             license detection, tag parsing, and URL helpers.
@dependencies pytest, unittest.mock
@relatedFiles ../../app/services/source_providers/generic_git.py,
              ../../app/core/exceptions.py
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import DomainException
from app.models.credential import Credential, CredentialType
from app.models.source_provider import ProviderType, SourceProvider
from app.services.source_providers.generic_git import (
    GenericGitSourceProvider,
    _build_auth_url,
    _detect_license_from_file,
    _extract_repo_info_from_url,
    _parse_ls_remote_tags,
    _parse_version,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_credential(**overrides) -> Credential:
    """Build a Credential ORM model for generic git."""
    defaults = {
        "id": 1,
        "name": "test-generic-credential",
        "credential_type": CredentialType.https_basic,
        "provider": "generic",
        "encrypted_secret": "encrypted:test-token-generic",
        "base_url": None,
    }
    defaults.update(overrides)
    return Credential(**defaults)


def _make_provider(**overrides) -> SourceProvider:
    """Build a SourceProvider ORM model for generic git."""
    credential = overrides.pop("credential", _make_credential())
    defaults = {
        "id": 1,
        "credential_id": 1,
        "provider_type": ProviderType.generic,
        "label": "Test Generic Provider",
        "is_deleted": False,
    }
    defaults.update(overrides)
    sp = SourceProvider(**defaults)
    sp.credential = credential
    return sp


# Mock subprocess result: (returncode, stdout, stderr)
_MOCK_GIT_SUCCESS = (0, "output\n", "")
_MOCK_GIT_AUTH_FAIL = (
    128,
    "",
    "fatal: Authentication failed for 'https://example.com/repo.git/'\n",
)
_MOCK_GIT_NOT_FOUND = (
    128,
    "",
    "fatal: repository 'https://example.com/nonexistent.git/' not found\n",
)
_MOCK_GIT_TIMEOUT_MSG = "fatal: could not resolve host\n"


def _make_mock_run_git(returncode=0, stdout="", stderr=""):
    """Create an AsyncMock that returns (returncode, stdout, stderr)."""

    async def _mock(*args, **kwargs):
        return returncode, stdout, stderr

    return AsyncMock(side_effect=_mock)


# ---------------------------------------------------------------------------
# Tests: _extract_repo_info_from_url
# ---------------------------------------------------------------------------


class TestExtractRepoInfoFromUrl:
    """Tests for _extract_repo_info_from_url() — URL parsing helper."""

    def test_https_url_with_git_suffix(self):
        """HTTPS URL with .git suffix is parsed correctly."""
        info = _extract_repo_info_from_url("https://github.com/owner/repo.git")
        assert info["name"] == "repo"
        assert info["full_name"] == "owner/repo"
        assert info["clone_url"] == "https://github.com/owner/repo.git"
        assert info["html_url"] == "https://github.com/owner/repo.git"
        assert info["ssh_url"] is None

    def test_https_url_without_git_suffix(self):
        """HTTPS URL without .git suffix is parsed correctly."""
        info = _extract_repo_info_from_url("https://gitlab.example.com/group/subgroup/project")
        assert info["name"] == "project"
        assert info["full_name"] == "group/subgroup/project"

    def test_ssh_url(self):
        """SSH URL is parsed correctly."""
        info = _extract_repo_info_from_url("git@github.com:owner/repo.git")
        assert info["name"] == "repo"
        assert info["full_name"] == "owner/repo"
        assert info["ssh_url"] == "git@github.com:owner/repo.git"

    def test_trailing_slash(self):
        """URL with trailing slash is handled."""
        info = _extract_repo_info_from_url("https://github.com/owner/repo.git/")
        assert info["name"] == "repo"


# ---------------------------------------------------------------------------
# Tests: _build_auth_url
# ---------------------------------------------------------------------------


class TestBuildAuthUrl:
    """Tests for _build_auth_url() — credential embedding helper."""

    def test_https_url_embed_token(self):
        """HTTPS URL gets credentials embedded."""
        result = _build_auth_url("https://github.com/owner/repo.git", "my-token")
        assert result == "https://git:my-token@github.com/owner/repo.git"

    def test_https_url_with_port(self):
        """HTTPS URL with custom port."""
        result = _build_auth_url("https://gitlab.example.com:8443/group/project.git", "token123")
        assert result == "https://git:token123@gitlab.example.com:8443/group/project.git"

    def test_ssh_url_not_modified(self):
        """SSH URLs are returned unchanged."""
        result = _build_auth_url("git@github.com:owner/repo.git", "my-key")
        assert result == "git@github.com:owner/repo.git"


# ---------------------------------------------------------------------------
# Tests: _parse_version
# ---------------------------------------------------------------------------


class TestParseVersion:
    """Tests for _parse_version() — semantic version parsing."""

    def test_simple_version(self):
        assert _parse_version("1.2.3") == (1, 2, 3)

    def test_v_prefix(self):
        assert _parse_version("2.0.0") == (2, 0, 0)

    def test_two_component(self):
        assert _parse_version("1.0") == (1, 0)

    def test_single_component(self):
        assert _parse_version("42") == (42,)


# ---------------------------------------------------------------------------
# Tests: _parse_ls_remote_tags
# ---------------------------------------------------------------------------


class TestParseLsRemoteTags:
    """Tests for _parse_ls_remote_tags() — git ls-remote tag parsing."""

    def test_empty_output(self):
        count, latest = _parse_ls_remote_tags("")
        assert count == 0
        assert latest is None

    def test_no_version_tags(self):
        output = "abc123\trefs/tags/some-label\n"
        count, latest = _parse_ls_remote_tags(output)
        assert count == 0
        assert latest is None

    def test_version_tags_semver(self):
        output = "abc123\trefs/tags/v1.0.0\ndef456\trefs/tags/v2.0.0\nghi789\trefs/tags/v1.5.0\n"
        count, latest = _parse_ls_remote_tags(output)
        assert count == 3
        assert latest == "v2.0.0"

    def test_version_tags_without_v_prefix(self):
        output = "abc123\trefs/tags/1.0.0\ndef456\trefs/tags/3.2.1\n"
        count, latest = _parse_ls_remote_tags(output)
        assert count == 2
        assert latest == "3.2.1"

    def test_version_tags_mixed(self):
        output = (
            "abc123\trefs/tags/release-1.0.0\n"
            "def456\trefs/tags/release-2.0.0\n"
            "ghi789\trefs/tags/nightly\n"
        )
        count, latest = _parse_ls_remote_tags(output)
        assert count == 2
        assert latest == "release-2.0.0"


# ---------------------------------------------------------------------------
# Tests: _detect_license_from_file
# ---------------------------------------------------------------------------


class TestDetectLicenseFromFile:
    """Tests for _detect_license_from_file() — license detection heuristics."""

    def test_empty_content(self):
        spdx, name = _detect_license_from_file("")
        assert spdx is None
        assert name is None

    def test_mit_license(self):
        content = "MIT License\n\nPermission is hereby granted, free of charge..."
        spdx, name = _detect_license_from_file(content)
        assert spdx == "MIT"
        assert name == "MIT License"

    def test_apache_2_0(self):
        content = "Apache License\nVersion 2.0, January 2004\nhttp://www.apache.org/licenses/"
        spdx, name = _detect_license_from_file(content)
        assert spdx == "Apache-2.0"

    def test_gpl_3_0(self):
        content = "GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007"
        spdx, name = _detect_license_from_file(content)
        assert spdx == "GPL-3.0-only"

    def test_gpl_2_0(self):
        content = "GNU GENERAL PUBLIC LICENSE\nVersion 2, June 1991"
        spdx, name = _detect_license_from_file(content)
        assert spdx == "GPL-2.0-only"

    def test_bsd_3_clause(self):
        content = (
            "Redistribution and use in source and binary forms, with or without modification,\n"
            "are permitted provided that...\n"
            "neither the name of the copyright holder nor the names of its contributors..."
        )
        spdx, name = _detect_license_from_file(content)
        assert spdx == "BSD-3-Clause"

    def test_bsd_2_clause(self):
        content = (
            "Redistribution and use in source and binary forms, with or without modification,\n"
            "are permitted provided that the following conditions are met:"
        )
        spdx, name = _detect_license_from_file(content)
        assert spdx == "BSD-2-Clause"

    def test_lgpl_2_1(self):
        content = "GNU LESSER GENERAL PUBLIC LICENSE\nVersion 2.1, February 1999"
        spdx, name = _detect_license_from_file(content)
        assert spdx == "LGPL-2.1-only"

    def test_mpl_2_0(self):
        content = "Mozilla Public License Version 2.0"
        spdx, name = _detect_license_from_file(content)
        assert spdx == "MPL-2.0"

    def test_unlicense(self):
        content = "This is free and unencumbered software released into the public domain."
        spdx, name = _detect_license_from_file(content)
        assert spdx == "Unlicense"

    def test_agpl_3_0(self):
        content = "GNU AFFERO GENERAL PUBLIC LICENSE\nVersion 3, 19 November 2007"
        spdx, name = _detect_license_from_file(content)
        assert spdx == "AGPL-3.0-only"

    def test_unknown_license(self):
        content = "Some custom proprietary license text that doesn't match any known pattern."
        spdx, name = _detect_license_from_file(content)
        assert spdx is None
        assert name is None

    def test_mit_without_mit_word(self):
        """MIT detected even without 'MIT' in text — broader Permission is hereby granted."""
        content = "Permission is hereby granted, free of charge, to any person obtaining a copy..."
        spdx, name = _detect_license_from_file(content)
        assert spdx == "MIT"
        assert name == "MIT License"


# ---------------------------------------------------------------------------
# Tests: check_access
# ---------------------------------------------------------------------------


class TestCheckAccess:
    """Tests for GenericGitSourceProvider.check_access()"""

    @pytest.mark.asyncio
    async def test_check_access_success(self):
        """check_access returns True when git ls-remote succeeds."""
        provider = _make_provider()
        gsp = GenericGitSourceProvider(provider, credential_secret="test-token")

        with patch(
            "app.services.source_providers.generic_git._run_git",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = (0, "abc123\trefs/heads/main\n", "")
            result = await gsp.check_access()
            assert result is True

    @pytest.mark.asyncio
    async def test_check_access_auth_failure(self):
        """check_access raises DomainException(401) on authentication failure."""
        provider = _make_provider()
        gsp = GenericGitSourceProvider(provider, credential_secret="bad-token")

        with patch(
            "app.services.source_providers.generic_git._run_git",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = (128, "", "fatal: Authentication failed")
            with pytest.raises(DomainException) as exc_info:
                await gsp.check_access()
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_check_access_not_found(self):
        """check_access raises DomainException(404) on repository not found."""
        provider = _make_provider()
        gsp = GenericGitSourceProvider(provider, credential_secret="test-token")

        with patch(
            "app.services.source_providers.generic_git._run_git",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = (128, "", "fatal: repository not found")
            with pytest.raises(DomainException) as exc_info:
                await gsp.check_access()
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_check_access_resolve_failure(self):
        """check_access raises DomainException(502) on DNS resolution failure."""
        provider = _make_provider()
        gsp = GenericGitSourceProvider(provider, credential_secret="test-token")

        with patch(
            "app.services.source_providers.generic_git._run_git",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = (128, "", "fatal: could not resolve host")
            with pytest.raises(DomainException) as exc_info:
                await gsp.check_access()
            assert exc_info.value.status_code == 502

    @pytest.mark.asyncio
    async def test_check_access_generic_error(self):
        """check_access raises DomainException(502) on unknown git error."""
        provider = _make_provider()
        gsp = GenericGitSourceProvider(provider, credential_secret="test-token")

        with patch(
            "app.services.source_providers.generic_git._run_git",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = (1, "", "some random git error")
            with pytest.raises(DomainException) as exc_info:
                await gsp.check_access()
            assert exc_info.value.status_code == 502


# ---------------------------------------------------------------------------
# Tests: list_groups
# ---------------------------------------------------------------------------


class TestListGroups:
    """Tests for GenericGitSourceProvider.list_groups()"""

    @pytest.mark.asyncio
    async def test_list_groups_always_empty(self):
        """list_groups always returns an empty list for generic git."""
        provider = _make_provider()
        gsp = GenericGitSourceProvider(provider, credential_secret="test-token")
        result = await gsp.list_groups()
        assert result == []


# ---------------------------------------------------------------------------
# Tests: list_repositories
# ---------------------------------------------------------------------------


class TestListRepositories:
    """Tests for GenericGitSourceProvider.list_repositories()"""

    @pytest.mark.asyncio
    async def test_list_repositories_with_valid_https_url(self):
        """list_repositories returns one repo for a valid HTTPS URL."""
        provider = _make_provider()
        gsp = GenericGitSourceProvider(provider, credential_secret="test-token")
        result = await gsp.list_repositories("https://github.com/owner/repo.git")
        assert len(result) == 1
        assert result[0]["name"] == "repo"
        assert result[0]["full_name"] == "owner/repo"

    @pytest.mark.asyncio
    async def test_list_repositories_with_valid_ssh_url(self):
        """list_repositories returns one repo for a valid SSH URL."""
        provider = _make_provider()
        gsp = GenericGitSourceProvider(provider, credential_secret="test-token")
        result = await gsp.list_repositories("git@gitlab.example.com:group/project.git")
        assert len(result) == 1
        assert result[0]["name"] == "project"

    @pytest.mark.asyncio
    async def test_list_repositories_with_invalid_url(self):
        """list_repositories returns empty list for an invalid URL."""
        provider = _make_provider()
        gsp = GenericGitSourceProvider(provider, credential_secret="test-token")
        result = await gsp.list_repositories("not-a-valid-url")
        assert result == []

    @pytest.mark.asyncio
    async def test_list_repositories_with_empty_string(self):
        """list_repositories returns empty list for empty string."""
        provider = _make_provider()
        gsp = GenericGitSourceProvider(provider, credential_secret="test-token")
        result = await gsp.list_repositories("")
        assert result == []

    @pytest.mark.asyncio
    async def test_list_repositories_with_none(self):
        """list_repositories returns empty list for None."""
        provider = _make_provider()
        gsp = GenericGitSourceProvider(provider, credential_secret="test-token")
        result = await gsp.list_repositories(None)
        assert result == []


# ---------------------------------------------------------------------------
# Tests: get_repository
# ---------------------------------------------------------------------------


class TestGetRepository:
    """Tests for GenericGitSourceProvider.get_repository()"""

    @pytest.mark.asyncio
    async def test_get_repository_success(self):
        """get_repository returns full metadata on successful clone."""
        provider = _make_provider()
        gsp = GenericGitSourceProvider(provider, credential_secret="test-token")

        # git clone --bare → success
        # HEAD → ref: refs/heads/main
        # git log -1 → commit info
        # git show HEAD:LICENSE → MIT
        # git show HEAD:README.md → readme content
        # git ls-remote --tags → version tags
        call_results = {
            ("clone", "--bare"): (0, "", ""),
            ("log", "-1"): (0, "abc123def\n2025-06-01T12:00:00+00:00\nDev User\n", ""),
            ("ls-remote", "--tags"): (
                0,
                "abc123\trefs/tags/v1.0.0\ndef456\trefs/tags/v2.0.0\n",
                "",
            ),
            ("show", "HEAD:README.md"): (0, "# Test Repo\n\nThis is a test.", ""),
            ("show", "HEAD:LICENSE"): (0, "MIT License\n\nPermission is hereby granted...", ""),
            ("ls-tree", "--name-only"): (0, "README.md\nLICENSE\nsrc/\n", ""),
        }

        async def _mock_run(*args, **kwargs):
            cmd_key = tuple(
                a for a in args if not a.startswith("https://") and not a.startswith("git@")
            )
            for expected_key, result in call_results.items():
                if all(k in cmd_key for k in expected_key if k):
                    return result[0], result[1], result[2]
            return 0, "", ""

        # We need to mock _run_git, _get_default_branch, _detect_license_from_clone,
        # _detect_readme_from_clone
        with (
            patch(
                "app.services.source_providers.generic_git._run_git",
                new_callable=AsyncMock,
                side_effect=_mock_run,
            ),
            patch(
                "app.services.source_providers.generic_git._get_default_branch",
                new_callable=AsyncMock,
                return_value="main",
            ),
            patch(
                "app.services.source_providers.generic_git._detect_license_from_clone",
                new_callable=AsyncMock,
                return_value=("MIT", "MIT License"),
            ),
            patch(
                "app.services.source_providers.generic_git._detect_readme_from_clone",
                new_callable=AsyncMock,
                return_value="# Test Repo\n\nThis is a test.",
            ),
        ):
            repo = await gsp.get_repository("https://github.com/owner/repo.git")

        assert repo["name"] == "repo"
        assert repo["full_name"] == "owner/repo"
        assert repo["default_branch"] == "main"
        assert repo["last_commit_sha"] == "abc123def"
        assert repo["last_commit_date"] == "2025-06-01T12:00:00+00:00"
        assert repo["last_commit_author"] == "Dev User"
        assert repo["license_spdx"] == "MIT"
        assert repo["license_name"] == "MIT License"
        assert repo["readme_html"] == "# Test Repo\n\nThis is a test."
        assert repo["releases_count"] == 2
        assert repo["latest_release_tag"] == "v2.0.0"
        assert repo["fork"] is False
        assert repo["private"] is False

    @pytest.mark.asyncio
    async def test_get_repository_auth_failure(self):
        """get_repository raises DomainException(401) on auth failure."""
        provider = _make_provider()
        gsp = GenericGitSourceProvider(provider, credential_secret="bad-token")

        with patch(
            "app.services.source_providers.generic_git._run_git",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = (128, "", "fatal: Authentication failed")
            with pytest.raises(DomainException) as exc_info:
                await gsp.get_repository("https://github.com/owner/repo.git")
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_repository_not_found(self):
        """get_repository raises DomainException(404) on not found."""
        provider = _make_provider()
        gsp = GenericGitSourceProvider(provider, credential_secret="test-token")

        with patch(
            "app.services.source_providers.generic_git._run_git",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = (128, "", "fatal: repository not found")
            with pytest.raises(DomainException) as exc_info:
                await gsp.get_repository("https://github.com/owner/nonexistent.git")
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_repository_unknown_license(self):
        """get_repository returns None for license when unknown."""
        provider = _make_provider()
        gsp = GenericGitSourceProvider(provider, credential_secret="test-token")

        async def _mock_run(*args, **kwargs):
            cmd_str = " ".join(args)
            if "clone" in cmd_str:
                return 0, "", ""
            if "ls-remote --tags" in cmd_str:
                return 0, "", ""
            return 0, "", ""

        with (
            patch(
                "app.services.source_providers.generic_git._run_git",
                new_callable=AsyncMock,
                side_effect=_mock_run,
            ),
            patch(
                "app.services.source_providers.generic_git._get_default_branch",
                new_callable=AsyncMock,
                return_value="master",
            ),
            patch(
                "app.services.source_providers.generic_git._detect_license_from_clone",
                new_callable=AsyncMock,
                return_value=(None, None),
            ),
            patch(
                "app.services.source_providers.generic_git._detect_readme_from_clone",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            repo = await gsp.get_repository("https://github.com/owner/repo.git")

        assert repo["license_spdx"] is None
        assert repo["license_name"] is None
        assert repo["readme_html"] is None

    @pytest.mark.asyncio
    async def test_get_repository_no_readme(self):
        """get_repository returns None for readme_html when no README found."""
        provider = _make_provider()
        gsp = GenericGitSourceProvider(provider, credential_secret="test-token")

        async def _mock_run(*args, **kwargs):
            cmd_str = " ".join(args)
            if "clone" in cmd_str:
                return 0, "", ""
            if "ls-remote --tags" in cmd_str:
                return 0, "", ""
            return 0, "", ""

        with (
            patch(
                "app.services.source_providers.generic_git._run_git",
                new_callable=AsyncMock,
                side_effect=_mock_run,
            ),
            patch(
                "app.services.source_providers.generic_git._get_default_branch",
                new_callable=AsyncMock,
                return_value="main",
            ),
            patch(
                "app.services.source_providers.generic_git._detect_license_from_clone",
                new_callable=AsyncMock,
                return_value=(None, None),
            ),
            patch(
                "app.services.source_providers.generic_git._detect_readme_from_clone",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            repo = await gsp.get_repository("https://github.com/owner/repo.git")

        assert repo["readme_html"] is None

    @pytest.mark.asyncio
    async def test_get_repository_no_tags(self):
        """get_repository returns 0 releases_count when no version tags exist."""
        provider = _make_provider()
        gsp = GenericGitSourceProvider(provider, credential_secret="test-token")

        async def _mock_run(*args, **kwargs):
            cmd_str = " ".join(args)
            if "clone" in cmd_str:
                return 0, "", ""
            if "ls-remote --tags" in cmd_str:
                return 0, "abc123\trefs/tags/nightly\n", ""
            return 0, "", ""

        with (
            patch(
                "app.services.source_providers.generic_git._run_git",
                new_callable=AsyncMock,
                side_effect=_mock_run,
            ),
            patch(
                "app.services.source_providers.generic_git._get_default_branch",
                new_callable=AsyncMock,
                return_value="main",
            ),
            patch(
                "app.services.source_providers.generic_git._detect_license_from_clone",
                new_callable=AsyncMock,
                return_value=(None, None),
            ),
            patch(
                "app.services.source_providers.generic_git._detect_readme_from_clone",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            repo = await gsp.get_repository("https://github.com/owner/repo.git")

        assert repo["releases_count"] == 0
        assert repo["latest_release_tag"] is None

    @pytest.mark.asyncio
    async def test_get_repository_clone_error(self):
        """get_repository raises DomainException(502) on generic clone error."""
        provider = _make_provider()
        gsp = GenericGitSourceProvider(provider, credential_secret="test-token")

        with patch(
            "app.services.source_providers.generic_git._run_git",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = (128, "", "fatal: unable to connect to host")
            with pytest.raises(DomainException) as exc_info:
                await gsp.get_repository("https://github.com/owner/repo.git")
            assert exc_info.value.status_code == 502


# ---------------------------------------------------------------------------
# Tests: get_commit_info
# ---------------------------------------------------------------------------


class TestGetCommitInfo:
    """Tests for GenericGitSourceProvider.get_commit_info()"""

    @pytest.mark.asyncio
    async def test_get_commit_info_default_branch(self):
        """get_commit_info returns commit on default branch when ref is None."""
        provider = _make_provider()
        gsp = GenericGitSourceProvider(provider, credential_secret="test-token")

        call_count = 0

        async def _mock_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            cmd_str = " ".join(args)
            if "clone" in cmd_str:
                return 0, "", ""
            if "ls-remote" in cmd_str:
                return 0, "abc123\trepo.git\n", ""
            if "fetch" in cmd_str:
                return 0, "", ""
            if "log" in cmd_str:
                return 0, "abc123\n2025-06-01T12:00:00+00:00\nDev\nfeat: test\n", ""
            if "init" in cmd_str:
                return 0, "", ""
            return 0, "", ""

        with (
            patch(
                "app.services.source_providers.generic_git._run_git",
                new_callable=AsyncMock,
                side_effect=_mock_run,
            ),
            patch(
                "app.services.source_providers.generic_git._get_default_branch",
                new_callable=AsyncMock,
                return_value="main",
            ),
        ):
            commit = await gsp.get_commit_info("https://github.com/owner/repo.git")

        assert commit["sha"] == "abc123"
        assert commit["date"] == "2025-06-01T12:00:00+00:00"
        assert commit["author"] == "Dev"
        assert commit["message"] == "feat: test"

    @pytest.mark.asyncio
    async def test_get_commit_info_with_explicit_ref(self):
        """get_commit_info with explicit ref resolves that ref."""
        provider = _make_provider()
        gsp = GenericGitSourceProvider(provider, credential_secret="test-token")

        async def _mock_run(*args, **kwargs):
            cmd_str = " ".join(args)
            if "ls-remote" in cmd_str and "v1.0" in cmd_str:
                return 0, "def456\trefs/tags/v1.0\n", ""
            if "fetch" in cmd_str:
                return 0, "", ""
            if "log" in cmd_str:
                return 0, "def456\n2025-01-01T00:00:00+00:00\nAuthor\nchore: release\n", ""
            if "init" in cmd_str:
                return 0, "", ""
            return 0, "", ""

        with patch(
            "app.services.source_providers.generic_git._run_git",
            new_callable=AsyncMock,
            side_effect=_mock_run,
        ):
            commit = await gsp.get_commit_info("https://github.com/owner/repo.git", ref="v1.0")

        assert commit["sha"] == "def456"
        assert commit["author"] == "Author"

    @pytest.mark.asyncio
    async def test_get_commit_info_ref_not_found(self):
        """get_commit_info raises DomainException(404) when ref not found."""
        provider = _make_provider()
        gsp = GenericGitSourceProvider(provider, credential_secret="test-token")

        with patch(
            "app.services.source_providers.generic_git._run_git",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = (128, "", "fatal: not found")
            with pytest.raises(DomainException) as exc_info:
                await gsp.get_commit_info("https://github.com/owner/repo.git", ref="nonexistent")
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_commit_info_empty_ls_remote(self):
        """get_commit_info raises DomainException(404) when ls-remote returns nothing."""
        provider = _make_provider()
        gsp = GenericGitSourceProvider(provider, credential_secret="test-token")

        with patch(
            "app.services.source_providers.generic_git._run_git",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = (0, "", "")
            with pytest.raises(DomainException) as exc_info:
                await gsp.get_commit_info("https://github.com/owner/repo.git", ref="unknown-branch")
            assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Tests: verify_mirror
# ---------------------------------------------------------------------------


class TestVerifyMirror:
    """Tests for GenericGitSourceProvider.verify_mirror()"""

    @pytest.mark.asyncio
    async def test_verify_mirror_matching(self):
        """verify_mirror returns True when all refs match."""
        provider = _make_provider()
        gsp = GenericGitSourceProvider(provider, credential_secret="test-token")

        source_output = "abc123\trefs/heads/main\ndef456\trefs/tags/v1.0\n"
        target_output = "abc123\trefs/heads/main\ndef456\trefs/tags/v1.0\n"

        async def _mock_run(*args, **kwargs):
            url_arg = args[1] if len(args) > 1 else ""
            if "source" in url_arg:
                return 0, source_output, ""
            elif "target" in url_arg:
                return 0, target_output, ""
            return 0, "", ""

        with patch(
            "app.services.source_providers.generic_git._run_git",
            new_callable=AsyncMock,
            side_effect=_mock_run,
        ):
            result = await gsp.verify_mirror(
                "https://source.example.com/repo.git", "https://target.example.com/repo.git"
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_verify_mirror_diverged(self):
        """verify_mirror returns False when refs differ."""
        provider = _make_provider()
        gsp = GenericGitSourceProvider(provider, credential_secret="test-token")

        source_output = "abc123\trefs/heads/main\n"
        target_output = "xyz789\trefs/heads/main\n"

        async def _mock_run(*args, **kwargs):
            url_arg = args[1] if len(args) > 1 else ""
            if "source" in url_arg:
                return 0, source_output, ""
            elif "target" in url_arg:
                return 0, target_output, ""
            return 0, "", ""

        with patch(
            "app.services.source_providers.generic_git._run_git",
            new_callable=AsyncMock,
            side_effect=_mock_run,
        ):
            result = await gsp.verify_mirror(
                "https://source.example.com/repo.git", "https://target.example.com/repo.git"
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_verify_mirror_source_empty(self):
        """verify_mirror returns False when source has no refs."""
        provider = _make_provider()
        gsp = GenericGitSourceProvider(provider, credential_secret="test-token")

        async def _mock_run(*args, **kwargs):
            url_arg = args[1] if len(args) > 1 else ""
            if "source" in url_arg:
                return 0, "", ""
            elif "target" in url_arg:
                return 0, "abc123\trefs/heads/main\n", ""
            return 0, "", ""

        with patch(
            "app.services.source_providers.generic_git._run_git",
            new_callable=AsyncMock,
            side_effect=_mock_run,
        ):
            result = await gsp.verify_mirror(
                "https://source.example.com/repo.git", "https://target.example.com/repo.git"
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_verify_mirror_no_common_refs(self):
        """verify_mirror returns False when source and target have no common refs."""
        provider = _make_provider()
        gsp = GenericGitSourceProvider(provider, credential_secret="test-token")

        source_output = "abc123\trefs/heads/main\n"
        target_output = "def456\trefs/heads/develop\n"

        async def _mock_run(*args, **kwargs):
            url_arg = args[1] if len(args) > 1 else ""
            if "source" in url_arg:
                return 0, source_output, ""
            elif "target" in url_arg:
                return 0, target_output, ""
            return 0, "", ""

        with patch(
            "app.services.source_providers.generic_git._run_git",
            new_callable=AsyncMock,
            side_effect=_mock_run,
        ):
            result = await gsp.verify_mirror(
                "https://source.example.com/repo.git", "https://target.example.com/repo.git"
            )
            assert result is False


# ---------------------------------------------------------------------------
# Tests: constructor / repr
# ---------------------------------------------------------------------------


class TestConstructor:
    """Tests for GenericGitSourceProvider.__init__() and basic properties."""

    def test_constructor_stores_credential(self):
        """Constructor stores provider and credential_secret."""
        provider = _make_provider()
        gsp = GenericGitSourceProvider(provider, credential_secret="test-token")
        assert gsp.provider is provider
        assert gsp.credential_secret == "test-token"
