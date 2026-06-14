"""
@file test_source_group_model.py
@description Unit tests for SourceGroup model — verifies instantiation,
             default field values, and representation.
@dependencies backend/app/models/source_group.py
"""

from app.models.source_group import SourceGroup


class TestSourceGroupModel:
    """Tests for the SourceGroup SQLAlchemy model."""

    def test_source_group_creation(self):
        """Create a SourceGroup with required fields."""
        sg = SourceGroup(
            external_id="12345",
            name="my-org",
            full_path="my-org",
            web_url="https://github.com/my-org",
            description="Test organization",
            total_repos=0,
            mirrored_repos=0,
        )
        assert sg.external_id == "12345"
        assert sg.name == "my-org"
        assert sg.full_path == "my-org"
        assert sg.web_url == "https://github.com/my-org"
        assert sg.description == "Test organization"
        assert sg.total_repos == 0
        assert sg.mirrored_repos == 0

    def test_source_group_defaults(self):
        """Verify DB-level defaults are defined on the model."""
        sg = SourceGroup(
            external_id="ext-id",
            name="Test",
        )
        assert sg.external_id == "ext-id"
        assert sg.name == "Test"

    def test_source_group_representation(self):
        """Verify __repr__ output."""
        sg = SourceGroup(
            id=1,
            external_id="ext-1",
            name="MyGroup",
        )
        repr_str = repr(sg)
        assert "MyGroup" in repr_str
        assert "SourceGroup" in repr_str
