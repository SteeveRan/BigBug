"""
@file test_mirror_log_model.py
@description Unit tests for MirrorLog model — verifies creation with all log_type
             enum values, pipeline_run relationship, and default field values.
@dependencies backend/app/models/mirror_log.py
"""

from app.models.mirror_log import MirrorLog, MirrorLogType


class TestMirrorLogModel:
    """Tests for the MirrorLog SQLAlchemy model."""

    def test_mirror_log_creation_sync(self):
        """Create a MirrorLog with log_type=sync."""
        ml = MirrorLog(
            mirror_id=1,
            log_type=MirrorLogType.sync,
            source_commit_sha="abc123",
            target_commit_sha="def456",
            commits_behind=0,
            status_flag=0,
            status_text="OK",
        )
        assert ml.mirror_id == 1
        assert ml.log_type == MirrorLogType.sync
        assert ml.status_flag == 0
        assert ml.status_text == "OK"
        assert ml.source_commit_sha == "abc123"
        assert ml.target_commit_sha == "def456"
        assert ml.commits_behind == 0

    def test_mirror_log_creation_freshness(self):
        """Create a MirrorLog with log_type=freshness."""
        ml = MirrorLog(
            mirror_id=2,
            log_type=MirrorLogType.freshness,
            commits_behind=5,
            target_extra_commits=2,
            status_flag=2,
            status_text="Diverged",
        )
        assert ml.log_type == MirrorLogType.freshness
        assert ml.commits_behind == 5
        assert ml.target_extra_commits == 2

    def test_mirror_log_creation_import(self):
        """Create a MirrorLog with log_type=import."""
        ml = MirrorLog(
            mirror_id=3,
            log_type=MirrorLogType.import_,
            status_flag=0,
            status_text="Imported successfully",
        )
        assert ml.log_type == MirrorLogType.import_

    def test_mirror_log_creation_integrity(self):
        """Create a MirrorLog with log_type=integrity."""
        ml = MirrorLog(
            mirror_id=4,
            log_type=MirrorLogType.integrity,
            status_flag=0,
            status_text="Integrity check passed",
        )
        assert ml.log_type == MirrorLogType.integrity

    def test_log_type_enum_values(self):
        """Verify all MirrorLogType enum values."""
        assert MirrorLogType.sync.value == "sync"
        assert MirrorLogType.freshness.value == "freshness"
        assert MirrorLogType.import_.value == "import"
        assert MirrorLogType.integrity.value == "integrity"

    def test_mirror_log_with_pipeline_run(self):
        """MirrorLog can reference a PipelineRun (pipeline_run_id nullable)."""
        ml = MirrorLog(
            mirror_id=1,
            log_type=MirrorLogType.sync,
            pipeline_run_id=42,
            gitlab_pipeline_id="12345",
            gitlab_pipeline_url="https://gitlab.example.com/pipelines/12345",
        )
        assert ml.pipeline_run_id == 42
        assert ml.gitlab_pipeline_id == "12345"
        assert ml.gitlab_pipeline_url == "https://gitlab.example.com/pipelines/12345"

    def test_mirror_log_no_pipeline_run(self):
        """MirrorLog with no pipeline_run (pipeline_run_id is nullable)."""
        ml = MirrorLog(
            mirror_id=1,
            log_type=MirrorLogType.freshness,
        )
        assert ml.pipeline_run_id is None

    def test_mirror_log_with_details(self):
        """MirrorLog can store arbitrary JSON details."""
        ml = MirrorLog(
            mirror_id=1,
            log_type=MirrorLogType.sync,
            details={"branch": "main", "force_push": False, "retries": 2},
            status_flag=4,
        )
        assert ml.details == {"branch": "main", "force_push": False, "retries": 2}

    def test_mirror_log_with_triggered_by(self):
        """MirrorLog tracks who/what triggered the operation."""
        ml = MirrorLog(
            mirror_id=1,
            log_type=MirrorLogType.sync,
            triggered_by="scheduler",
        )
        assert ml.triggered_by == "scheduler"

    def test_mirror_log_defaults(self):
        """Verify MirrorLog can be created with explicit status_flag and details."""
        ml = MirrorLog(
            mirror_id=1,
            log_type=MirrorLogType.sync,
            status_flag=4,
            details={},
        )
        assert ml.status_flag == 4
        assert ml.details == {}

    def test_mirror_log_representation(self):
        """Verify __repr__ output."""
        ml = MirrorLog(
            id=1,
            mirror_id=5,
            log_type=MirrorLogType.sync,
        )
        repr_str = repr(ml)
        assert "MirrorLog" in repr_str
