"""
@file test_source_provider_schema.py
@description Unit tests for SourceProvider Pydantic schemas.
@dependencies app.schemas.source_provider
"""

import pytest
from pydantic import ValidationError

from app.models.source_provider import ProviderType
from app.schemas.source_provider import SourceProviderCreate, SourceProviderOut


class TestSourceProviderCreate:
    """Validation of SourceProviderCreate schema."""

    def test_create_minimal(self):
        """Create with required fields only."""
        data = SourceProviderCreate(
            provider_type=ProviderType.github,
            label="github.com (primary)",
        )
        assert data.provider_type == ProviderType.github
        assert data.label == "github.com (primary)"
        assert data.credential_id is None

    def test_create_with_credential(self):
        """Create linked to a credential."""
        data = SourceProviderCreate(
            credential_id=42,
            provider_type=ProviderType.gitlab,
            label="self-hosted gitlab",
        )
        assert data.credential_id == 42
        assert data.provider_type == ProviderType.gitlab

    def test_create_validates_provider_type(self):
        """provider_type must be a valid ProviderType enum value."""
        with pytest.raises(ValidationError):
            SourceProviderCreate(
                provider_type="invalid_provider",
                label="test",
            )

    def test_create_with_is_anon(self):
        """Create an anonymous provider — credential_id is not required."""
        data = SourceProviderCreate(
            provider_type=ProviderType.github,
            label="github.com (anonymous)",
            is_anon=True,
        )
        assert data.is_anon is True
        assert data.credential_id is None

    def test_create_is_anon_default_false(self):
        """is_anon defaults to False when not provided."""
        data = SourceProviderCreate(
            provider_type=ProviderType.github,
            label="github.com (primary)",
        )
        assert data.is_anon is False


class TestSourceProviderOut:
    """Validation of SourceProviderOut schema."""

    def test_out_has_expected_fields(self):
        """Verify all expected fields are present."""
        fields = set(SourceProviderOut.model_fields.keys())
        expected = {
            "id",
            "credential_id",
            "provider_type",
            "label",
            "is_anon",
            "is_builtin",
            "is_deleted",
            "deleted_at",
            "created_at",
            "updated_at",
            "credential",
        }
        assert fields == expected

    def test_out_credential_optional(self):
        """credential nested object is Optional."""
        assert SourceProviderOut.model_fields["credential"].default is None

    def test_out_from_attributes_config(self):
        """model_config enables from_attributes."""
        assert SourceProviderOut.model_config.get("from_attributes") is True
