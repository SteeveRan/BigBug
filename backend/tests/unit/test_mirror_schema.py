"""
@file test_mirror_schema.py
@description Unit tests for Mirror Pydantic schemas.
@dependencies app.schemas.mirror
"""

import pytest
from pydantic import ValidationError

from app.schemas.mirror import (
    MirrorCreate,
    MirrorBulkCreate,
    MirrorUpdate,
    MirrorListOut,
    MirrorDetailOut,
    MirrorDuplicateCheck,
    MirrorDuplicateCheckOut,
)


class TestMirrorCreate:
    """Validation of MirrorCreate schema."""

    def test_create_minimal(self):
        """Create with required fields only."""
        data = MirrorCreate(
            source_repository_id=1,
            target_namespace="my-namespace",
            target_project_name="my-project",
        )
        assert data.source_repository_id == 1
        assert data.target_namespace == "my-namespace"
        assert data.target_project_name == "my-project"
        assert data.sync_group_id is None

    def test_create_with_sync_group(self):
        """Create linked to a sync group."""
        data = MirrorCreate(
            source_repository_id=42,
            sync_group_id=7,
            target_namespace="org",
            target_project_name="repo",
        )
        assert data.sync_group_id == 7

    def test_create_requires_target_fields(self):
        """target_namespace and target_project_name are required."""
        with pytest.raises(ValidationError):
            MirrorCreate(source_repository_id=1)


class TestMirrorBulkCreate:
    """Validation of MirrorBulkCreate schema."""

    def test_bulk_create_minimal(self):
        """Bulk create with list of mirrors."""
        data = MirrorBulkCreate(
            mirrors=[
                MirrorCreate(
                    source_repository_id=1,
                    target_namespace="ns1",
                    target_project_name="proj1",
                ),
                MirrorCreate(
                    source_repository_id=2,
                    target_namespace="ns2",
                    target_project_name="proj2",
                ),
            ],
        )
        assert len(data.mirrors) == 2
        assert data.default_sync_group_id is None
        assert data.default_target_namespace is None

    def test_bulk_create_with_defaults(self):
        """Bulk create with shared defaults."""
        data = MirrorBulkCreate(
            mirrors=[
                MirrorCreate(
                    source_repository_id=1,
                    target_namespace="ns1",
                    target_project_name="proj1",
                ),
            ],
            default_sync_group_id=5,
            default_target_namespace="default-ns",
        )
        assert data.default_sync_group_id == 5
        assert data.default_target_namespace == "default-ns"


class TestMirrorUpdate:
    """Validation of MirrorUpdate — all fields optional."""

    def test_update_empty(self):
        """All fields are optional."""
        data = MirrorUpdate()
        assert data.sync_group_id is None
        assert data.target_namespace is None

    def test_update_partial(self):
        """Only update target_namespace."""
        data = MirrorUpdate(target_namespace="new-ns")
        assert data.target_namespace == "new-ns"
        assert data.target_project_name is None


class TestMirrorListOut:
    """Validation of MirrorListOut schema."""

    def test_list_out_has_expected_fields(self):
        """Verify all expected list fields plus source_repository nested."""
        fields = set(MirrorListOut.model_fields.keys())
        expected = {
            "id", "source_repository_id", "sync_group_id", "target_namespace",
            "target_project_name", "target_project_id", "target_web_url",
            "status_flag", "status_text", "last_sync_at", "last_sync_status",
            "last_freshness_check_at", "last_freshness_status", "is_imported",
            "created_at", "source_repository",
        }
        assert fields == expected

    def test_list_out_from_attributes_config(self):
        """model_config enables from_attributes."""
        assert MirrorListOut.model_config.get("from_attributes") is True


class TestMirrorDetailOut:
    """Validation of MirrorDetailOut schema."""

    def test_detail_out_has_nested_relations(self):
        """Detail has source_repository, sync_group, mirror_logs."""
        fields = set(MirrorDetailOut.model_fields.keys())
        assert "source_repository" in fields
        assert "sync_group" in fields
        assert "mirror_logs" in fields
        assert "last_known_commit_sha" in fields
        assert "last_known_commit_date" in fields
        assert "last_known_commit_author" in fields
        assert "target_diverged_commits" in fields
        assert "updated_at" in fields

    def test_detail_out_mirror_logs_default(self):
        """mirror_logs defaults to empty list."""
        assert MirrorDetailOut.model_fields["mirror_logs"].default == []

    def test_detail_out_from_attributes_config(self):
        """model_config enables from_attributes."""
        assert MirrorDetailOut.model_config.get("from_attributes") is True


class TestMirrorDuplicateCheck:
    """Validation of MirrorDuplicateCheck and MirrorDuplicateCheckOut."""

    def test_duplicate_check_request(self):
        """Request has source_repository_id and target_project_name."""
        data = MirrorDuplicateCheck(
            source_repository_id=1,
            target_project_name="my-project",
        )
        assert data.source_repository_id == 1
        assert data.target_project_name == "my-project"

    def test_duplicate_check_response(self):
        """Response has exists boolean."""
        data = MirrorDuplicateCheckOut(exists=True)
        assert data.exists is True

    def test_duplicate_check_response_false(self):
        """Response exists can be False."""
        data = MirrorDuplicateCheckOut(exists=False)
        assert data.exists is False
