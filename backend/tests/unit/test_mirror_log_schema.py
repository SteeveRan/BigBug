"""
@file test_mirror_log_schema.py
@description Unit tests for MirrorLog Pydantic schemas.
@dependencies app.schemas.mirror_log
"""

import pytest
from pydantic import ValidationError

from app.models.mirror_log import MirrorLogType
from app.schemas.mirror_log import MirrorLogCreate, MirrorLogOut


class TestMirrorLogCreate:
    """Validation of MirrorLogCreate schema."""

    def test_create_minimal(self):
        """Create with required fields only."""
        data = MirrorLogCreate(
            mirror_id=1,
            log_type=MirrorLogType.sync,
        )
        assert data.mirror_id == 1
        assert data.log_type == MirrorLogType.sync
        assert data.status_flag == 3  # default: In Progress
        assert data.pipeline_run_id is None

    def test_create_with_pipeline_run(self):
        """Create linked to a pipeline run."""
        data = MirrorLogCreate(
            mirror_id=42,
            log_type=MirrorLogType.freshness,
            pipeline_run_id=99,
            status_flag=0,
            status_text="OK",
            triggered_by="scheduler",
        )
        assert data.pipeline_run_id == 99
        assert data.status_flag == 0
        assert data.status_text == "OK"
        assert data.triggered_by == "scheduler"

    def test_create_all_log_types(self):
        """All MirrorLogType values are accepted."""
        for lt in MirrorLogType:
            data = MirrorLogCreate(mirror_id=1, log_type=lt)
            assert data.log_type == lt

    def test_create_requires_mirror_id(self):
        """mirror_id is required."""
        with pytest.raises(ValidationError):
            MirrorLogCreate(log_type=MirrorLogType.sync)

    def test_create_requires_log_type(self):
        """log_type is required."""
        with pytest.raises(ValidationError):
            MirrorLogCreate(mirror_id=1)

    def test_create_invalid_log_type(self):
        """Invalid log_type raises ValidationError."""
        with pytest.raises(ValidationError):
            MirrorLogCreate(mirror_id=1, log_type="invalid_type")


class TestMirrorLogOut:
    """Validation of MirrorLogOut schema."""

    def test_out_has_expected_fields(self):
        """Verify all expected fields including nested relations."""
        fields = set(MirrorLogOut.model_fields.keys())
        expected = {
            "id",
            "mirror_id",
            "log_type",
            "pipeline_run_id",
            "gitlab_pipeline_id",
            "gitlab_pipeline_url",
            "status_flag",
            "status_text",
            "source_commit_sha",
            "source_commit_date",
            "target_commit_sha",
            "commits_behind",
            "target_extra_commits",
            "started_at",
            "finished_at",
            "duration_ms",
            "triggered_by",
            "details",
            "created_at",
            "mirror",
            "pipeline_run",
        }
        assert fields == expected

    def test_out_nested_mirror_optional(self):
        """mirror nested object is Optional."""
        assert MirrorLogOut.model_fields["mirror"].default is None

    def test_out_nested_pipeline_run_optional(self):
        """pipeline_run nested object is Optional."""
        assert MirrorLogOut.model_fields["pipeline_run"].default is None

    def test_out_from_attributes_config(self):
        """model_config enables from_attributes."""
        assert MirrorLogOut.model_config.get("from_attributes") is True
