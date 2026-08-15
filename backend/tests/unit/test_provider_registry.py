"""
@file test_provider_registry.py
@description Unit tests for the provider subtype registry (stage 4): every subtype
             has a full spec; capability matrix; allowed categories; oci_compliant.
@dependencies backend/app/services/providers/registry.py
"""

from app.models.resource_provider import (
    ProviderCapability,
    ProviderCategory,
    ProviderDirection,
    ProviderSubtype,
)
from app.services.providers.registry import PROVIDER_TYPES, get_spec


class TestRegistryCoverage:
    def test_every_subtype_has_spec(self):
        assert set(PROVIDER_TYPES) == set(ProviderSubtype)

    def test_specs_have_config_schema(self):
        for spec in PROVIDER_TYPES.values():
            assert spec.config_schema.get("type") == "object"
            assert "properties" in spec.config_schema

    def test_allowed_categories_nonempty(self):
        for spec in PROVIDER_TYPES.values():
            assert spec.allowed_categories

    def test_allowed_directions_nonempty(self):
        for spec in PROVIDER_TYPES.values():
            assert spec.allowed_directions


class TestCapabilityMatrix:
    def test_trigger_pipeline_only_gitlab_system_internal(self):
        gitlab = get_spec(ProviderSubtype.gitlab)
        allowed = gitlab.allowed_capabilities(ProviderCategory.system, ProviderDirection.internal)
        assert "trigger_pipeline" in allowed

        forbidden = gitlab.allowed_capabilities(
            ProviderCategory.private, ProviderDirection.external
        )
        assert "trigger_pipeline" not in forbidden

    def test_no_other_subtype_has_trigger_pipeline(self):
        for subtype, spec in PROVIDER_TYPES.items():
            if subtype == ProviderSubtype.gitlab:
                continue
            allowed = spec.allowed_capabilities(ProviderCategory.system, ProviderDirection.internal)
            assert "trigger_pipeline" not in allowed

    def test_harbor_has_list_projects(self):
        harbor = get_spec(ProviderSubtype.harbor)
        assert ProviderCapability.list_projects in harbor.capabilities


class TestOciCompliant:
    def test_all_docker_subtypes_oci_compliant(self):
        docker_subtypes = {
            ProviderSubtype.docker_hub,
            ProviderSubtype.quay,
            ProviderSubtype.gcr,
            ProviderSubtype.ecr,
            ProviderSubtype.acr,
            ProviderSubtype.ghcr,
            ProviderSubtype.harbor,
            ProviderSubtype.generic_registry,
        }
        for subtype in docker_subtypes:
            assert get_spec(subtype).oci_compliant is True

    def test_git_and_helm_not_oci(self):
        assert get_spec(ProviderSubtype.github).oci_compliant is False
        assert get_spec(ProviderSubtype.helm_repo).oci_compliant is False
