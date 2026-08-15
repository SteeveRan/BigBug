"""
@file test_provider_schema.py
@description Unit tests for Provider Pydantic schemas (stage 3): config deny-list,
             unknown-key rejection, subtype JSON-Schema selection and no-secrets Out.
@dependencies backend/app/schemas/provider.py, backend/app/services/providers/registry.py
"""

import pytest
from pydantic import ValidationError

from app.models.resource_provider import (
    ProviderCategory,
    ProviderDirection,
    ProviderDomain,
    ProviderSubtype,
)
from app.schemas.provider import ProviderCreate, ProviderOut, ProviderUpdate


def _create(**overrides):
    data = {
        "domain": ProviderDomain.git,
        "subtype": ProviderSubtype.github,
        "category": ProviderCategory.public,
        "direction": ProviderDirection.external,
        "name": "github-public",
        "label": "GitHub",
        **overrides,
    }
    return ProviderCreate(**data)


class TestProviderCreate:
    def test_valid_github(self):
        p = _create(config={"api_url": "https://api.github.com"})
        assert p.name == "github-public"

    def test_unknown_config_key_rejected(self):
        with pytest.raises(ValidationError):
            _create(config={"bogus_key": 1})

    def test_secret_key_rejected(self):
        with pytest.raises(ValidationError):
            _create(config={"token": "secret-value"})

    def test_secret_suffix_key_rejected(self):
        with pytest.raises(ValidationError):
            _create(config={"api_token": "secret-value"})

    def test_domain_mismatch_rejected(self):
        with pytest.raises(ValidationError):
            _create(domain=ProviderDomain.docker)

    def test_requires_base_url_for_generic_git(self):
        with pytest.raises(ValidationError):
            ProviderCreate(
                domain=ProviderDomain.git,
                subtype=ProviderSubtype.generic_git,
                category=ProviderCategory.private,
                direction=ProviderDirection.external,
                name="generic",
                label="Generic",
            )

    def test_base_url_satisfies_generic_git(self):
        p = ProviderCreate(
            domain=ProviderDomain.git,
            subtype=ProviderSubtype.generic_git,
            category=ProviderCategory.private,
            direction=ProviderDirection.external,
            name="generic",
            label="Generic",
            base_url="https://git.example.com",
        )
        assert p.base_url == "https://git.example.com"


class TestProviderUpdate:
    def test_config_deny_list_on_update(self):
        with pytest.raises(ValidationError):
            ProviderUpdate(config={"password": "x"})


class TestProviderOut:
    def test_has_credential_true(self):
        out = ProviderOut(
            id=1,
            domain=ProviderDomain.git,
            subtype=ProviderSubtype.gitlab,
            category=ProviderCategory.private,
            direction=ProviderDirection.external,
            name="gitlab",
            label="GitLab",
            config={},
            credential_id=5,
            owner_user_id=2,
            is_active=True,
            is_default=False,
            is_protected=False,
            verify_ssl=True,
            priority=0,
            status_flag=0,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        assert out.has_credential is True

    def test_has_credential_false(self):
        out = ProviderOut(
            id=2,
            domain=ProviderDomain.docker,
            subtype=ProviderSubtype.docker_hub,
            category=ProviderCategory.public,
            direction=ProviderDirection.external,
            name="dockerhub",
            label="Docker Hub",
            config={},
            credential_id=None,
            is_active=True,
            is_default=False,
            is_protected=False,
            verify_ssl=True,
            priority=0,
            status_flag=0,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        assert out.has_credential is False
