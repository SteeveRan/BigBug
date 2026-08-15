"""
@file test_resource_provider_model.py
@description Unit tests for the unified ResourceProvider model and enums (stage 1).
@dependencies backend/app/models/resource_provider.py
"""

from app.models.resource_provider import (
    ProviderCapability,
    ProviderCategory,
    ProviderDirection,
    ProviderDomain,
    ProviderSubtype,
    ResourceProvider,
)


class TestResourceProviderEnums:
    def test_domain_values(self):
        assert {d.value for d in ProviderDomain} == {"git", "docker", "helm"}

    def test_subtype_values(self):
        assert {s.value for s in ProviderSubtype} == {
            "github",
            "gitlab",
            "generic_git",
            "docker_hub",
            "quay",
            "gcr",
            "ecr",
            "acr",
            "ghcr",
            "harbor",
            "generic_registry",
            "helm_repo",
        }

    def test_category_values(self):
        assert {c.value for c in ProviderCategory} == {"system", "public", "private"}

    def test_direction_values(self):
        assert {d.value for d in ProviderDirection} == {"external", "internal"}

    def test_capability_values(self):
        assert ProviderCapability.list_repositories.value == "list_repositories"
        assert ProviderCapability.trigger_pipeline.value == "trigger_pipeline"
        assert ProviderCapability.test_connection.value == "test_connection"


class TestResourceProviderModel:
    def test_creation_minimal(self):
        p = ResourceProvider(
            domain=ProviderDomain.git,
            subtype=ProviderSubtype.github,
            category=ProviderCategory.public,
            direction=ProviderDirection.external,
            name="github-public",
            label="GitHub",
        )
        assert p.domain == ProviderDomain.git
        assert p.name == "github-public"

    def test_config_default_is_python_default(self):
        # config default is applied at INSERT time; the model carries the value
        # set explicitly. Verify an explicit empty dict round-trips.
        p = ResourceProvider(config={})
        assert p.config == {}

    def test_private_with_owner(self):
        p = ResourceProvider(
            domain=ProviderDomain.git,
            subtype=ProviderSubtype.gitlab,
            category=ProviderCategory.private,
            direction=ProviderDirection.external,
            name="gitlab-self",
            label="GitLab",
            owner_user_id=7,
        )
        assert p.owner_user_id == 7

    def test_repr(self):
        p = ResourceProvider(
            domain=ProviderDomain.docker,
            subtype=ProviderSubtype.docker_hub,
            category=ProviderCategory.public,
            direction=ProviderDirection.external,
            name="dockerhub",
            label="Docker Hub",
        )
        assert "dockerhub" in repr(p)
        assert "docker_hub" in repr(p)
