"""
@file test_source_repository_schema.py
@description Unit tests for SourceRepository Pydantic schemas.
@dependencies app.schemas.source_repository
"""

from app.schemas.source_repository import (
    SourceRepositoryDetailOut,
    SourceRepositoryListOut,
    SourceRepositoryReadmeOut,
    SourceRepositoryReleaseOut,
)


class TestSourceRepositoryListOut:
    """Validation of SourceRepositoryListOut schema."""

    def test_list_out_has_expected_fields(self):
        """Verify all expected list fields are present."""
        fields = set(SourceRepositoryListOut.model_fields.keys())
        expected = {
            "id",
            "source_group_id",
            "name",
            "full_name",
            "web_url",
            "default_branch",
            "is_archived",
            "is_fork",
            "discovery_status",
            "latest_release_tag",
            "latest_release_date",
            "source_pushed_at",
            "last_seen_at",
            "is_deleted",
            "created_at",
        }
        assert fields == expected

    def test_list_out_from_attributes_config(self):
        """model_config enables from_attributes."""
        assert SourceRepositoryListOut.model_config.get("from_attributes") is True


class TestSourceRepositoryDetailOut:
    """Validation of SourceRepositoryDetailOut schema."""

    def test_detail_out_has_nested_relations(self):
        """Detail has source_group and mirrors nested."""
        fields = set(SourceRepositoryDetailOut.model_fields.keys())
        assert "source_group" in fields
        assert "mirrors" in fields
        assert "description" in fields
        assert "license_spdx" in fields
        assert "clone_url_https" in fields
        assert "clone_url_ssh" in fields
        assert "readme_html" in fields
        assert "is_disabled" in fields
        assert "updated_at" in fields

    def test_detail_out_mirrors_default(self):
        """mirrors defaults to empty list."""
        assert SourceRepositoryDetailOut.model_fields["mirrors"].default == []

    def test_detail_out_from_attributes_config(self):
        """model_config enables from_attributes."""
        assert SourceRepositoryDetailOut.model_config.get("from_attributes") is True


class TestSourceRepositoryReleaseOut:
    """Validation of SourceRepositoryReleaseOut schema."""

    def test_release_out_has_expected_fields(self):
        """Verify release fields."""
        fields = set(SourceRepositoryReleaseOut.model_fields.keys())
        expected = {
            "tag",
            "name",
            "description",
            "url",
            "published_at",
            "is_prerelease",
            "detected_at",
        }
        assert fields == expected

    def test_release_out_is_prerelease_default(self):
        """is_prerelease defaults to False."""
        assert SourceRepositoryReleaseOut.model_fields["is_prerelease"].default is False


class TestSourceRepositoryReadmeOut:
    """Validation of SourceRepositoryReadmeOut schema."""

    def test_readme_out_has_expected_fields(self):
        """Verify readme fields."""
        fields = set(SourceRepositoryReadmeOut.model_fields.keys())
        assert fields == {"readme_html", "readme_fetched_at"}
