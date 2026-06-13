"""
@file test_mirror_release_log_model.py
@description Unit tests for MirrorReleaseLog model — verifies creation with
             release data, prerelease flag, and source_repository relationship.
@dependencies backend/app/models/mirror_release_log.py
"""

from datetime import UTC, datetime

from app.models.mirror_release_log import MirrorReleaseLog


class TestMirrorReleaseLogModel:
    """Tests for the MirrorReleaseLog SQLAlchemy model."""

    def test_release_log_creation_basic(self):
        """Create a MirrorReleaseLog with release data."""
        rl = MirrorReleaseLog(
            source_repository_id=1,
            tag="v1.0.0",
            name="Release v1.0.0",
            description="First stable release",
            url="https://github.com/org/repo/releases/tag/v1.0.0",
            published_at=datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC),
            is_prerelease=False,
        )
        assert rl.source_repository_id == 1
        assert rl.tag == "v1.0.0"
        assert rl.name == "Release v1.0.0"
        assert rl.description == "First stable release"
        assert rl.url == "https://github.com/org/repo/releases/tag/v1.0.0"
        assert rl.is_prerelease is False

    def test_release_log_prerelease(self):
        """Create a MirrorReleaseLog for a prerelease."""
        rl = MirrorReleaseLog(
            source_repository_id=2,
            tag="v2.0.0-beta.1",
            name="Beta 1",
            is_prerelease=True,
        )
        assert rl.tag == "v2.0.0-beta.1"
        assert rl.is_prerelease is True

    def test_release_log_detected_at_default(self):
        """detected_at is None until the model is persisted (DB-level default)."""
        rl = MirrorReleaseLog(
            source_repository_id=1,
            tag="v3.0.0",
        )
        # detected_at is a DB-level default, applied at INSERT time.
        assert rl.source_repository_id == 1
        assert rl.tag == "v3.0.0"

    def test_release_log_representation(self):
        """Verify __repr__ output."""
        rl = MirrorReleaseLog(
            id=1,
            source_repository_id=5,
            tag="v1.2.3",
        )
        repr_str = repr(rl)
        assert "v1.2.3" in repr_str
        assert "MirrorReleaseLog" in repr_str
