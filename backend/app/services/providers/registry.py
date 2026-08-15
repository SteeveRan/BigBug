"""
@file registry.py
@description Registry of supported provider subtypes for the unified Providers V3.
             Each entry is a :class:`ProviderTypeSpec` describing the domain,
             capabilities, allowed categories/directions/credential types and the
             per-subtype JSON Schema for the ``config`` field.
@dependencies app.models.resource_provider, app.models.credential
@relatedFiles ../schemas/provider.py, ./service.py, ./clients/
"""

from dataclasses import dataclass, field
from typing import Any

from app.models.credential import CredentialType
from app.models.resource_provider import (
    ProviderCapability,
    ProviderCategory,
    ProviderDirection,
    ProviderDomain,
    ProviderSubtype,
)


@dataclass(frozen=True)
class ProviderTypeSpec:
    """Metadata for one provider subtype."""

    subtype: ProviderSubtype
    domain: ProviderDomain
    label: str
    capabilities: frozenset[ProviderCapability]
    allowed_categories: frozenset[ProviderCategory]
    allowed_directions: frozenset[ProviderDirection]
    allowed_credential_types: frozenset[CredentialType]
    config_schema: dict[str, Any]
    oci_compliant: bool = False
    requires_base_url: bool = False
    restricted_capabilities: dict[str, frozenset[tuple[str, str]]] = field(default_factory=dict)

    @property
    def config_fields(self) -> tuple[str, ...]:
        return tuple(self.config_schema.get("properties", {}).keys())

    def allowed_capabilities(
        self, category: ProviderCategory, direction: ProviderDirection
    ) -> frozenset[str]:
        """Return capability names allowed for a (category, direction) combo.

        A capability listed in :attr:`restricted_capabilities` is dropped unless
        the (category, direction) pair is in its allow-set. This encodes rules
        such as ``trigger_pipeline`` being restricted to system/internal GitLab.
        """
        caps = {cap.value for cap in self.capabilities}
        for cap_value, allowed_combos in self.restricted_capabilities.items():
            if (category.value, direction.value) not in allowed_combos:
                caps.discard(cap_value)
        return frozenset(caps)

    def to_dict(self) -> dict[str, Any]:
        """JSON-serialisable representation for ``GET /api/providers/types``."""
        return {
            "subtype": self.subtype.value,
            "domain": self.domain.value,
            "label": self.label,
            "capabilities": sorted({cap.value for cap in self.capabilities}),
            "allowed_categories": sorted(c.value for c in self.allowed_categories),
            "allowed_directions": sorted(d.value for d in self.allowed_directions),
            "allowed_credential_types": sorted(c.value for c in self.allowed_credential_types),
            "config_schema": self.config_schema,
            "oci_compliant": self.oci_compliant,
            "requires_base_url": self.requires_base_url,
        }


# Capability values reference (single source of truth).
_C = ProviderCapability
_CAT = ProviderCategory
_DIR = ProviderDirection
_CRED = CredentialType

# Capabilities restricted to specific (category, direction) combinations.
# ``trigger_pipeline`` is reserved for the platform's own GitLab (system/internal).
CAPABILITY_RESTRICTIONS: dict[str, frozenset[tuple[str, str]]] = {
    "trigger_pipeline": frozenset({("system", "internal")}),
}


def _schema(properties: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }


def _arch_filter() -> dict[str, Any]:
    return {"type": "array", "items": {"type": "string"}, "default": []}


_PROVIDER_TYPES: dict[ProviderSubtype, ProviderTypeSpec] = {
    # ── Git ────────────────────────────────────────────────────────────────
    ProviderSubtype.github: ProviderTypeSpec(
        subtype=ProviderSubtype.github,
        domain=ProviderDomain.git,
        label="GitHub",
        capabilities=frozenset(
            {_C.test_connection, _C.list_groups, _C.list_repositories, _C.get_commit}
        ),
        allowed_categories=frozenset({_CAT.public, _CAT.private}),
        allowed_directions=frozenset({_DIR.external}),
        allowed_credential_types=frozenset({_CRED.github_token}),
        config_schema=_schema(
            {
                "api_url": {"type": "string", "default": "https://api.github.com"},
                "org_blacklist": {"type": "array", "items": {"type": "string"}, "default": []},
            }
        ),
    ),
    ProviderSubtype.gitlab: ProviderTypeSpec(
        subtype=ProviderSubtype.gitlab,
        domain=ProviderDomain.git,
        label="GitLab",
        capabilities=frozenset(
            {
                _C.test_connection,
                _C.list_groups,
                _C.list_repositories,
                _C.get_commit,
                _C.trigger_pipeline,
            }
        ),
        allowed_categories=frozenset({_CAT.system, _CAT.public, _CAT.private}),
        allowed_directions=frozenset({_DIR.external, _DIR.internal}),
        allowed_credential_types=frozenset({_CRED.gitlab_token}),
        config_schema=_schema(
            {
                "api_version": {"type": "string", "enum": ["v4"], "default": "v4"},
                "default_group_id": {"type": ["integer", "string"]},
                "group_visibility": {
                    "type": "string",
                    "enum": ["private", "internal", "public"],
                },
                "mirror_visibility": {
                    "type": "string",
                    "enum": ["private", "internal", "public"],
                },
                "default_branch": {"type": "string"},
            }
        ),
        restricted_capabilities=CAPABILITY_RESTRICTIONS,
    ),
    ProviderSubtype.generic_git: ProviderTypeSpec(
        subtype=ProviderSubtype.generic_git,
        domain=ProviderDomain.git,
        label="Generic Git",
        capabilities=frozenset({_C.test_connection, _C.list_repositories, _C.get_commit}),
        allowed_categories=frozenset({_CAT.private}),
        allowed_directions=frozenset({_DIR.external}),
        allowed_credential_types=frozenset({_CRED.https_basic, _CRED.ssh_key}),
        config_schema=_schema(
            {
                "clone_protocol": {"type": "string", "enum": ["https", "ssh"], "default": "https"},
                "discovery_mode": {"type": "string", "enum": ["none", "manual"], "default": "none"},
            }
        ),
        requires_base_url=True,
    ),
    # ── Docker / OCI ───────────────────────────────────────────────────────
    ProviderSubtype.docker_hub: ProviderTypeSpec(
        subtype=ProviderSubtype.docker_hub,
        domain=ProviderDomain.docker,
        label="Docker Hub",
        capabilities=frozenset({_C.test_connection, _C.list_repositories}),
        allowed_categories=frozenset({_CAT.public, _CAT.private}),
        allowed_directions=frozenset({_DIR.external}),
        allowed_credential_types=frozenset({_CRED.https_basic}),
        config_schema=_schema({"namespace": {"type": "string"}, "arch_filter": _arch_filter()}),
        oci_compliant=True,
    ),
    ProviderSubtype.quay: ProviderTypeSpec(
        subtype=ProviderSubtype.quay,
        domain=ProviderDomain.docker,
        label="Quay",
        capabilities=frozenset({_C.test_connection, _C.list_repositories}),
        allowed_categories=frozenset({_CAT.public, _CAT.private}),
        allowed_directions=frozenset({_DIR.external}),
        allowed_credential_types=frozenset({_CRED.https_basic}),
        config_schema=_schema({"org": {"type": "string"}, "arch_filter": _arch_filter()}),
        oci_compliant=True,
    ),
    ProviderSubtype.gcr: ProviderTypeSpec(
        subtype=ProviderSubtype.gcr,
        domain=ProviderDomain.docker,
        label="Google Container Registry",
        capabilities=frozenset({_C.test_connection, _C.list_repositories}),
        allowed_categories=frozenset({_CAT.private}),
        allowed_directions=frozenset({_DIR.external}),
        allowed_credential_types=frozenset({_CRED.https_basic}),
        config_schema=_schema({"region": {"type": "string"}, "arch_filter": _arch_filter()}),
        oci_compliant=True,
        requires_base_url=True,
    ),
    ProviderSubtype.ecr: ProviderTypeSpec(
        subtype=ProviderSubtype.ecr,
        domain=ProviderDomain.docker,
        label="Amazon ECR",
        capabilities=frozenset({_C.test_connection, _C.list_repositories}),
        allowed_categories=frozenset({_CAT.private}),
        allowed_directions=frozenset({_DIR.external}),
        allowed_credential_types=frozenset({_CRED.https_basic}),
        config_schema=_schema({"region": {"type": "string"}, "arch_filter": _arch_filter()}),
        oci_compliant=True,
        requires_base_url=True,
    ),
    ProviderSubtype.acr: ProviderTypeSpec(
        subtype=ProviderSubtype.acr,
        domain=ProviderDomain.docker,
        label="Azure Container Registry",
        capabilities=frozenset({_C.test_connection, _C.list_repositories}),
        allowed_categories=frozenset({_CAT.private}),
        allowed_directions=frozenset({_DIR.external}),
        allowed_credential_types=frozenset({_CRED.https_basic}),
        config_schema=_schema({"subscription": {"type": "string"}, "arch_filter": _arch_filter()}),
        oci_compliant=True,
        requires_base_url=True,
    ),
    ProviderSubtype.ghcr: ProviderTypeSpec(
        subtype=ProviderSubtype.ghcr,
        domain=ProviderDomain.docker,
        label="GitHub Container Registry",
        capabilities=frozenset({_C.test_connection, _C.list_repositories}),
        allowed_categories=frozenset({_CAT.public, _CAT.private}),
        allowed_directions=frozenset({_DIR.external}),
        allowed_credential_types=frozenset({_CRED.github_token}),
        config_schema=_schema({"org": {"type": "string"}, "arch_filter": _arch_filter()}),
        oci_compliant=True,
    ),
    ProviderSubtype.harbor: ProviderTypeSpec(
        subtype=ProviderSubtype.harbor,
        domain=ProviderDomain.docker,
        label="Harbor",
        capabilities=frozenset({_C.test_connection, _C.list_projects, _C.list_repositories}),
        allowed_categories=frozenset({_CAT.system, _CAT.private}),
        allowed_directions=frozenset({_DIR.external, _DIR.internal}),
        allowed_credential_types=frozenset({_CRED.https_basic}),
        config_schema=_schema(
            {
                "default_project": {"type": "string"},
                "robot_prefix": {"type": "string"},
                "projects_allowlist": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                },
            }
        ),
        oci_compliant=True,
        requires_base_url=True,
    ),
    ProviderSubtype.generic_registry: ProviderTypeSpec(
        subtype=ProviderSubtype.generic_registry,
        domain=ProviderDomain.docker,
        label="Generic Registry (OCI)",
        capabilities=frozenset({_C.test_connection, _C.list_repositories}),
        allowed_categories=frozenset({_CAT.private}),
        allowed_directions=frozenset({_DIR.external, _DIR.internal}),
        allowed_credential_types=frozenset({_CRED.https_basic}),
        config_schema=_schema(
            {
                "api_style": {"type": "string", "enum": ["registry_v2", "harbor_v2"]},
                "auth_flow": {"type": "string", "enum": ["basic", "none"]},
            }
        ),
        oci_compliant=True,
        requires_base_url=True,
    ),
    # ── Helm ───────────────────────────────────────────────────────────────
    ProviderSubtype.helm_repo: ProviderTypeSpec(
        subtype=ProviderSubtype.helm_repo,
        domain=ProviderDomain.helm,
        label="Helm Repository",
        capabilities=frozenset({_C.test_connection, _C.list_charts}),
        allowed_categories=frozenset({_CAT.public, _CAT.private}),
        allowed_directions=frozenset({_DIR.external}),
        allowed_credential_types=frozenset({_CRED.https_basic}),
        config_schema=_schema(
            {
                "index_path": {"type": "string", "default": "/index.yaml"},
                "chart_allowlist": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                },
            }
        ),
        requires_base_url=True,
    ),
}

PROVIDER_TYPES: dict[ProviderSubtype, ProviderTypeSpec] = _PROVIDER_TYPES


def get_spec(subtype: ProviderSubtype | str) -> ProviderTypeSpec:
    """Return the spec for a subtype, raising ``KeyError`` for unknown values."""
    if isinstance(subtype, str):
        subtype = ProviderSubtype(subtype)
    return PROVIDER_TYPES[subtype]


def all_types() -> list[dict[str, Any]]:
    """Serialised registry metadata, stable-sorted by subtype name."""
    return [spec.to_dict() for _, spec in sorted(PROVIDER_TYPES.items())]
