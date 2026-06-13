"""
@file test_sync_group_model.py
@description Unit tests for SyncGroup model — verifies creation, pipeline link,
             schedule config, and defaults.
@dependencies backend/app/models/sync_group.py
"""

from app.models.pipeline import Pipeline
from app.models.sync_group import SyncGroup


class TestSyncGroupModel:
    """Tests for the SyncGroup SQLAlchemy model."""

    def test_sync_group_creation_basic(self):
        """Create a SyncGroup with required fields."""
        sg = SyncGroup(
            name="default-sync-group",
            description="Default sync group for all mirrors",
            is_default=True,
            sync_enabled=True,
            sync_concurrency=5,
            freshness_enabled=True,
            freshness_concurrency=5,
        )
        assert sg.name == "default-sync-group"
        assert sg.description == "Default sync group for all mirrors"
        assert sg.is_default is True
        assert sg.sync_enabled is True
        assert sg.sync_concurrency == 5
        assert sg.freshness_enabled is True
        assert sg.freshness_concurrency == 5

    def test_sync_group_with_schedule(self):
        """Create a SyncGroup with custom cron schedules."""
        sg = SyncGroup(
            name="frequent-sync",
            sync_cron="*/30 * * * *",
            sync_concurrency=10,
            freshness_cron="0 */6 * * *",
            freshness_concurrency=3,
        )
        assert sg.sync_cron == "*/30 * * * *"
        assert sg.sync_concurrency == 10
        assert sg.freshness_cron == "0 */6 * * *"
        assert sg.freshness_concurrency == 3

    def test_sync_group_with_pipeline(self):
        """Verify relationship — SyncGroup can reference a Pipeline."""
        pl = Pipeline(
            name="sync-pipeline",
            ref="main",
            default_variables={},
        )
        sg = SyncGroup(
            name="pipeline-group",
            pipeline_id=1,
        )
        sg.pipeline = pl
        assert sg.pipeline is pl
        assert sg.pipeline.name == "sync-pipeline"

    def test_sync_group_no_pipeline(self):
        """SyncGroup with no pipeline (pipeline_id is nullable)."""
        sg = SyncGroup(
            name="no-pipeline-group",
        )
        assert sg.pipeline_id is None

    def test_sync_group_defaults(self):
        """Verify SyncGroup with explicit default values."""
        sg = SyncGroup(
            name="test-group",
            is_default=False,
            sync_enabled=True,
            sync_concurrency=5,
            freshness_enabled=True,
            freshness_concurrency=5,
        )
        assert sg.is_default is False
        assert sg.sync_enabled is True
        assert sg.sync_concurrency == 5
        assert sg.freshness_enabled is True
        assert sg.freshness_concurrency == 5

    def test_sync_group_representation(self):
        """Verify __repr__ output."""
        sg = SyncGroup(
            id=1,
            name="MyGroup",
            is_default=True,
        )
        repr_str = repr(sg)
        assert "MyGroup" in repr_str
        assert "SyncGroup" in repr_str
