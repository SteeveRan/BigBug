"""
@file test_source_group_schema.py
@description Unit tests for SourceGroup Pydantic schemas.
@dependencies app.schemas.source_group
"""

import pytest
from pydantic import ValidationError

from app.schemas.source_group import (
    SourceGroupCreate,
    SourceGroupUpdate,
    SourceGroupListOut,
    SourceGroupDetailOut,
)


class TestSourceGroupCreate:
    """Validation of SourceGroupCreate schema."""

    def test_create_minimal(self):
        """Create with required fields only."""
        data = SourceGroupCreate(
            source_provider_id=1,
            name="my-org",
        )
        assert data.source_provider_id == 1
        assert data.name == "my-org"
        assert data.full_path is None
        assert data.web_url is None
        assert data.description is None

    def test_create_all_fields(self):
        """Create with all optional fields."""
        data = SourceGroupCreate(
            source_provider_id=5,
            name="My Organization",
            full_path="parent/child",
            web_url="https://github.com/orgs/my-org",
            description="A test organization",
        )
        assert data.full_path == "parent/child"
        assert data.web_url == "https://github.com/orgs/my-org"
        assert data.description == "A test organization"

    def test_create_requires_source_provider_id(self):
        """source_provider_id is required."""
        with pytest.raises(ValidationError):
            SourceGroupCreate(name="no-provider")


class TestSourceGroupUpdate:
    """Validation of SourceGroupUpdate — all fields optional."""

    def test_update_empty(self):
        """All fields are optional."""
        data = SourceGroupUpdate()
        assert data.name is None
        assert data.full_path is None

    def test_update_partial(self):
        """Only update name."""
        data = SourceGroupUpdate(name="updated-org")
        assert data.name == "updated-org"
        assert data.full_path is None


class TestSourceGroupListOut:
    """Validation of SourceGroupListOut schema."""

    def test_list_out_has_expected_fields(self):
        """Verify all expected fields are present."""
        fields = set(SourceGroupListOut.model_fields.keys())
        expected = {
            "id", "source_provider_id", "name", "full_path", "web_url",
            "total_repos", "mirrored_repos", "last_synced_at", "created_at",
        }
        assert fields == expected

    def test_list_out_from_attributes_config(self):
        """model_config enables from_attributes."""
        assert SourceGroupListOut.model_config.get("from_attributes") is True


class TestSourceGroupDetailOut:
    """Validation of SourceGroupDetailOut schema."""

    def test_detail_out_has_nested_relations(self):
        """Detail has source_provider and source_repositories nested."""
        fields = set(SourceGroupDetailOut.model_fields.keys())
        assert "source_provider" in fields
        assert "source_repositories" in fields
        assert "description" in fields
        assert "external_id" in fields
        assert "updated_at" in fields
        assert "is_deleted" in fields

    def test_detail_out_source_repositories_default(self):
        """source_repositories defaults to empty list."""
        assert SourceGroupDetailOut.model_fields["source_repositories"].default == []

    def test_detail_out_from_attributes_config(self):
        """model_config enables from_attributes."""
        assert SourceGroupDetailOut.model_config.get("from_attributes") is True
