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
        """Create a SourceRepository with optional fields populated."""
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
        )
        assert repo.description == "A test repository"
        assert repo.default_branch == "develop"
        assert repo.license_spdx == "MIT"
        assert repo.license_name == "MIT License"
        assert repo.latest_release_tag == "v2.0.0"
        assert repo.is_fork is True

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
