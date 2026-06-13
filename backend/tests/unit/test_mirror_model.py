"""
@file test_mirror_model.py
@description Unit tests for Mirror model — verifies creation, properties
             (pipeline, target_gitlab_instance), and relationships.
@dependencies backend/app/models/mirror.py
"""

from app.models.mirror import Mirror
from app.models.pipeline import Pipeline
from app.models.sync_group import SyncGroup


class TestMirrorModel:
    """Tests for the Mirror SQLAlchemy model."""

    def test_mirror_creation_basic(self):
        """Create a Mirror with required fields."""
        m = Mirror(
            source_repository_id=1,
            target_namespace="my-group",
            target_project_name="my-mirror",
            status_flag=4,
            is_imported=False,
            is_deleted=False,
            target_diverged_commits=0,
        )
        assert m.source_repository_id == 1
        assert m.target_namespace == "my-group"
        assert m.target_project_name == "my-mirror"
        assert m.status_flag == 4  # Pending
        assert m.is_imported is False
        assert m.target_diverged_commits == 0

    def test_mirror_with_all_fields(self):
        """Create a Mirror with all fields populated."""
        m = Mirror(
            source_repository_id=2,
            sync_group_id=3,
            target_namespace="org/mirrors",
            target_project_name="backend-mirror",
            target_project_id="42",
            target_web_url="https://gitlab.example.com/org/mirrors/backend-mirror",
            status_flag=0,
            status_text="OK",
            last_known_commit_sha="abc123def456",
            last_known_commit_author="Developer",
            last_sync_status="success",
            is_imported=True,
        )
        assert m.sync_group_id == 3
        assert m.target_project_id == "42"
        assert m.target_web_url == "https://gitlab.example.com/org/mirrors/backend-mirror"
        assert m.status_flag == 0
        assert m.status_text == "OK"
        assert m.last_known_commit_sha == "abc123def456"
        assert m.last_known_commit_author == "Developer"
        assert m.is_imported is True

    def test_mirror_pipeline_property_no_sync_group(self):
        """Mirror.pipeline returns None when no sync_group is assigned."""
        m = Mirror(
            source_repository_id=1,
            target_namespace="ns",
            target_project_name="proj",
        )
        assert m.pipeline is None

    def test_mirror_pipeline_property_no_pipeline_on_sync_group(self):
        """Mirror.pipeline returns None when sync_group has no pipeline."""
        sg = SyncGroup(name="no-pipe-group")
        m = Mirror(
            source_repository_id=1,
            target_namespace="ns",
            target_project_name="proj",
        )
        m.sync_group = sg
        assert m.pipeline is None

    def test_mirror_pipeline_property_with_pipeline(self):
        """Mirror.pipeline returns the pipeline via sync_group."""
        pl = Pipeline(name="mirror-pipe", ref="main", default_variables={})
        sg = SyncGroup(name="pipe-group")
        sg.pipeline = pl
        m = Mirror(
            source_repository_id=1,
            target_namespace="ns",
            target_project_name="proj",
        )
        m.sync_group = sg
        assert m.pipeline is pl
        assert m.pipeline.name == "mirror-pipe"

    def test_mirror_target_gitlab_instance_no_pipeline(self):
        """target_gitlab_instance returns None when no pipeline chain exists."""
        m = Mirror(
            source_repository_id=1,
            target_namespace="ns",
            target_project_name="proj",
        )
        assert m.target_gitlab_instance is None

    def test_mirror_defaults(self):
        """Verify Mirror with explicit values for defaulted fields."""
        m = Mirror(
            source_repository_id=1,
            target_namespace="ns",
            target_project_name="proj",
            status_flag=4,
            is_imported=False,
            is_deleted=False,
            target_diverged_commits=0,
        )
        assert m.status_flag == 4
        assert m.is_imported is False
        assert m.target_diverged_commits == 0
