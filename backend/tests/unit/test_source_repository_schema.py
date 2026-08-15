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
            "provider_id",
            "source_group_id",
            "name",
            "full_name",
            "web_url",
            "description",
            "language",
            "stars_count",
            "forks_count",
            "is_private",
            "default_branch",
            "is_archived",
            "is_fork",
            "discovery_status",
            "latest_release_tag",
            "latest_release_date",
            "latest_prerelease_tag",
            "latest_prerelease_date",
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
        """Detail has provider_id, source_group, mirrors and Wave 1 metadata fields."""
        fields = set(SourceRepositoryDetailOut.model_fields.keys())
        assert "provider_id" in fields
        assert "source_group" in fields
        assert "mirrors" in fields
        assert "description" in fields
        assert "license_spdx" in fields
        assert "clone_url_https" in fields
        assert "clone_url_ssh" in fields
        assert "readme_html" in fields
        assert "is_disabled" in fields
        assert "updated_at" in fields
        # Wave 1 additions — status tracking
        assert "status_flag" in fields
        assert "status_text" in fields
        # Wave 1 additions — last commit metadata
        assert "last_commit_sha" in fields
        assert "last_commit_date" in fields
        assert "last_commit_author" in fields
        assert "last_commit_message" in fields

    def test_detail_out_mirrors_default(self):
        """mirrors defaults to empty list."""
        assert SourceRepositoryDetailOut.model_fields["mirrors"].default == []

    def test_detail_out_from_attributes_config(self):
        """model_config enables from_attributes."""
        assert SourceRepositoryDetailOut.model_config.get("from_attributes") is True


class TestSourceRepositoryReleaseOut:
    """Validation of SourceRepositoryReleaseOut schema (Wave 1 — aliased fields)."""

    def test_release_out_has_expected_fields(self):
        """Verify release fields (model_fields keys are Python field names, not aliases)."""
        fields = set(SourceRepositoryReleaseOut.model_fields.keys())
        expected = {
            "id",
            "release_tag",
            "release_name",
            "release_body",
            "html_url",
            "published_at",
            "is_prerelease",
            "detected_at",
        }
        assert fields == expected

    def test_release_out_is_prerelease_default(self):
        """is_prerelease defaults to False."""
        assert SourceRepositoryReleaseOut.model_fields["is_prerelease"].default is False

    def test_release_out_uses_aliases(self):
        """release_tag/release_name/release_body/html_url work through alias (Wave 1)."""
        obj = SourceRepositoryReleaseOut(
            id=42,
            release_tag="v1.0.0",
            release_name="First Release",
            release_body="Initial release notes",
            html_url="https://github.com/org/repo/releases/tag/v1.0.0",
            published_at="2026-06-15T01:00:00Z",
            is_prerelease=False,
        )
        # by_alias=True: keys are the alias names (tag, name, description, url)
        public = obj.model_dump(by_alias=True)
        assert public["id"] == 42
        assert public["tag"] == "v1.0.0"
        assert public["name"] == "First Release"
        assert public["description"] == "Initial release notes"
        assert public["url"] == "https://github.com/org/repo/releases/tag/v1.0.0"

        # by_alias=False: keys are the Python field names (release_tag, release_name, ...)
        internal = obj.model_dump(by_alias=False)
        assert internal["id"] == 42
        assert internal["release_tag"] == "v1.0.0"
        assert internal["release_name"] == "First Release"
        assert internal["release_body"] == "Initial release notes"
        assert internal["html_url"] == "https://github.com/org/repo/releases/tag/v1.0.0"


class TestSourceRepositoryReadmeOut:
    """Validation of SourceRepositoryReadmeOut schema."""

    def test_readme_out_has_expected_fields(self):
        """Verify readme fields."""
        fields = set(SourceRepositoryReadmeOut.model_fields.keys())
        assert fields == {"readme_html", "readme_fetched_at"}
