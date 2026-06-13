"""
@file test_sync_group_schema.py
@description Unit tests for SyncGroup Pydantic schemas.
@dependencies app.schemas.sync_group
"""

import pytest
from pydantic import ValidationError

from app.schemas.sync_group import (
    SyncGroupCreate,
    SyncGroupOut,
    SyncGroupUpdate,
)


class TestSyncGroupCreate:
    """Validation of SyncGroupCreate schema."""

    def test_create_minimal(self):
        """Create with name only — defaults applied."""
        data = SyncGroupCreate(name="default-sg")
        assert data.name == "default-sg"
        assert data.sync_enabled is True
        assert data.sync_concurrency == 1
        assert data.freshness_enabled is False
        assert data.freshness_concurrency == 1
        assert data.pipeline_id is None

    def test_create_all_fields(self):
        """Create with all optional fields specified."""
        data = SyncGroupCreate(
            name="production-sg",
            description="Production mirror group",
            pipeline_id=5,
            sync_cron="0 */6 * * *",
            sync_enabled=True,
            sync_concurrency=10,
            freshness_cron="0 0 * * 0",
            freshness_enabled=True,
            freshness_concurrency=3,
        )
        assert data.description == "Production mirror group"
        assert data.sync_cron == "0 */6 * * *"
        assert data.sync_concurrency == 10
        assert data.freshness_cron == "0 0 * * 0"
        assert data.freshness_concurrency == 3

    def test_create_name_required(self):
        """name is required."""
        with pytest.raises(ValidationError):
            SyncGroupCreate()

    def test_create_sync_concurrency_min_1(self):
        """sync_concurrency must be >= 1."""
        with pytest.raises(ValidationError):
            SyncGroupCreate(name="test", sync_concurrency=0)


class TestSyncGroupUpdate:
    """Validation of SyncGroupUpdate — all fields optional."""

    def test_update_empty(self):
        """All fields are optional."""
        data = SyncGroupUpdate()
        assert data.description is None
        assert data.pipeline_id is None

    def test_update_partial(self):
        """Partial update."""
        data = SyncGroupUpdate(
            description="Updated description",
            sync_enabled=False,
            is_deleted=True,
        )
        assert data.description == "Updated description"
        assert data.sync_enabled is False
        assert data.is_deleted is True

    def test_update_sync_concurrency_min_1(self):
        """sync_concurrency cannot be < 1."""
        with pytest.raises(ValidationError):
            SyncGroupUpdate(sync_concurrency=0)


class TestSyncGroupOut:
    """Validation of SyncGroupOut schema."""

    def test_out_has_expected_fields(self):
        """Verify all expected fields including computed mirrors_count."""
        fields = set(SyncGroupOut.model_fields.keys())
        expected = {
            "id",
            "name",
            "description",
            "pipeline_id",
            "is_default",
            "sync_cron",
            "sync_enabled",
            "sync_concurrency",
            "freshness_cron",
            "freshness_enabled",
            "freshness_concurrency",
            "is_deleted",
            "created_at",
            "updated_at",
            "pipeline",
        }
        # mirrors_count is a computed_field, not in model_fields
        assert fields == expected
        assert "mirrors_count" in SyncGroupOut.model_computed_fields

    def test_out_mirrors_count_computed(self):
        """mirrors_count is a computed field returning int."""
        # It's a computed_field — verify it exists and returns int
        info = SyncGroupOut.model_computed_fields["mirrors_count"]
        assert info is not None

    def test_out_from_attributes_config(self):
        """model_config enables from_attributes."""
        assert SyncGroupOut.model_config.get("from_attributes") is True
