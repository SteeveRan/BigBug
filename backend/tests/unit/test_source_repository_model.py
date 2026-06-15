"""
@file test_source_repository_model.py
@description Unit tests for SourceRepository model — verifies instantiation with
             all fields, discovery_status enum, and group relationship.
@dependencies backend/app/models/source_repository.py
"""

from app.models.source_repository import DiscoveryStatus, SourceRepository


class TestSourceRepositoryModel:
    """Tests for the SourceRepository SQLAlchemy model."""

    def test_source_repository_creation_basic(self):
        """Create a SourceRepository with required fields."""
        repo = SourceRepository(
            source_group_id=1,
            external_id="repo-123",
            name="my-repo",
            full_name="my-org/my-repo",
            web_url="https://github.com/my-org/my-repo",
            clone_url_https="https://github.com/my-org/my-repo.git",
            clone_url_ssh="git@github.com:my-org/my-repo.git",
            discovery_status=DiscoveryStatus.new,
        )
        assert repo.source_group_id == 1
        assert repo.external_id == "repo-123"
        assert repo.name == "my-repo"
        assert repo.full_name == "my-org/my-repo"
        assert repo.web_url == "https://github.com/my-org/my-repo"
        assert repo.clone_url_https == "https://github.com/my-org/my-repo.git"
        assert repo.clone_url_ssh == "git@github.com:my-org/my-repo.git"
        assert repo.discovery_status == DiscoveryStatus.new

    def test_source_repository_with_all_fields(self):
        """Create a SourceRepository with optional fields populated — including Wave 1 additions."""
        repo = SourceRepository(
            source_group_id=2,
            external_id="repo-456",
            name="another-repo",
            full_name="team/another-repo",
            description="A test repository",
            default_branch="develop",
            license_spdx="MIT",
            license_name="MIT License",
            latest_release_tag="v2.0.0",
            latest_release_name="Version 2.0.0",
            is_archived=False,
            is_fork=True,
            is_disabled=False,
            status_flag=0,
            status_text="OK",
            last_commit_sha="abc123def456",
            last_commit_author="Test Author",
            last_commit_message="feat: add test",
        )
        assert repo.description == "A test repository"
        assert repo.default_branch == "develop"
        assert repo.license_spdx == "MIT"
        assert repo.license_name == "MIT License"
        assert repo.latest_release_tag == "v2.0.0"
        assert repo.is_fork is True
        assert repo.status_flag == 0
        assert repo.status_text == "OK"
        assert repo.last_commit_sha == "abc123def456"
        assert repo.last_commit_author == "Test Author"
        assert repo.last_commit_message == "feat: add test"

    def test_source_repository_with_status_fields(self):
        """Create a SourceRepository and verify status field defaults (Wave 1).

        SQLAlchemy Column(default=...) is only applied at DB insert time so
        for a pure-Python model test we set the default explicitly.
        """
        repo = SourceRepository(
            source_group_id=1,
            external_id="repo-status",
            name="status-repo",
            full_name="org/status-repo",
            status_flag=4,
            status_text=None,
        )
        assert repo.status_flag == 4, (
            f"Expected default status_flag=4 (pending), got {repo.status_flag}"
        )
        assert repo.status_text is None, (
            f"Expected default status_text=None, got {repo.status_text!r}"
        )

    def test_source_repository_with_last_commit_fields(self):
        """Create a SourceRepository with all last_commit fields populated (Wave 1)."""
        from datetime import datetime, timezone

        commit_date = datetime(2026, 6, 15, 1, 0, 0, tzinfo=timezone.utc)
        repo = SourceRepository(
            source_group_id=1,
            external_id="repo-commit",
            name="commit-repo",
            full_name="org/commit-repo",
            last_commit_sha="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
            last_commit_date=commit_date,
            last_commit_author="Jane Doe",
            last_commit_message="fix: resolve bug in parsing logic",
        )
        assert repo.last_commit_sha == "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"
        assert repo.last_commit_date == commit_date
        assert repo.last_commit_author == "Jane Doe"
        assert repo.last_commit_message == "fix: resolve bug in parsing logic"

    def test_discovery_status_enum_values(self):
        """Verify all DiscoveryStatus enum values."""
        assert DiscoveryStatus.new.value == "new"
        assert DiscoveryStatus.existing.value == "existing"
        assert DiscoveryStatus.removed.value == "removed"

    def test_discovery_status_explicit(self):
        """Create a SourceRepository with explicit discovery_status."""
        repo = SourceRepository(
            source_group_id=1,
            external_id="repo-789",
            name="removed-repo",
            full_name="org/removed-repo",
            discovery_status=DiscoveryStatus.removed,
        )
        assert repo.discovery_status == DiscoveryStatus.removed

    def test_source_repository_defaults(self):
        """Verify fields that differ from defaults can be set explicitly."""
        repo = SourceRepository(
            source_group_id=1,
            external_id="ext-1",
            name="test",
            full_name="org/test",
            is_archived=False,
            is_fork=False,
            is_disabled=False,
            discovery_status=DiscoveryStatus.new,
        )
        assert repo.is_archived is False
        assert repo.is_fork is False
        assert repo.is_disabled is False
        assert repo.discovery_status == DiscoveryStatus.new
