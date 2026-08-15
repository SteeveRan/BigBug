"""
@file resource_provider.py
@description ResourceProvider model — unified provider of resources (git, docker, helm)
             used by the platform. Replaces the legacy per-domain instance tables
             (source_providers, gitlab_instances, github_instances, harbor_instances,
             docker_registry_instances, helm_repository_instances) in Providers V3.
@dependencies app.database.Base, ./credential.py, ./user.py, ./role_scope.py
@relatedFiles ./role_scope.py, ../schemas/provider.py, ../services/providers/registry.py
"""

import enum
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import relationship

from app.database import Base


class ProviderDomain(enum.StrEnum):
    git = "git"
    docker = "docker"
    helm = "helm"


class ProviderSubtype(enum.StrEnum):
    github = "github"
    gitlab = "gitlab"
    generic_git = "generic_git"
    docker_hub = "docker_hub"
    quay = "quay"
    gcr = "gcr"
    ecr = "ecr"
    acr = "acr"
    ghcr = "ghcr"
    harbor = "harbor"
    generic_registry = "generic_registry"
    helm_repo = "helm_repo"


class ProviderCategory(enum.StrEnum):
    system = "system"
    public = "public"
    private = "private"


class ProviderVisibility(enum.StrEnum):
    owner = "owner"
    team = "team"
    public = "public"


class ProviderDirection(enum.StrEnum):
    external = "external"
    internal = "internal"


class ProviderCapability(enum.StrEnum):
    list_groups = "list_groups"
    list_repositories = "list_repositories"
    get_commit = "get_commit"
    trigger_pipeline = "trigger_pipeline"
    list_projects = "list_projects"
    # Docker "repositories/tags" is the same underlying action as git "repositories";
    # the alias documents domain-specific naming without a new canonical value.
    list_repositories_docker = "list_repositories"
    list_charts = "list_charts"
    test_connection = "test_connection"


class ResourceProvider(Base):
    __tablename__ = "resource_providers"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(
        SAEnum(ProviderDomain, name="provider_domain_enum"),
        nullable=False,
    )
    subtype = Column(
        SAEnum(ProviderSubtype, name="provider_subtype_enum"),
        nullable=False,
    )
    category = Column(
        SAEnum(ProviderCategory, name="provider_category_enum"),
        nullable=False,
    )
    visibility = Column(
        SAEnum(ProviderVisibility, name="provider_visibility_enum"),
        nullable=False,
        default=ProviderVisibility.owner,
    )
    direction = Column(
        SAEnum(ProviderDirection, name="provider_direction_enum"),
        nullable=False,
    )
    name = Column(String(255), nullable=False)
    label = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    base_url = Column(String(500), nullable=True)
    config = Column(JSON, default=dict, nullable=False)
    credential_id = Column(
        Integer,
        ForeignKey("credentials.id", ondelete="SET NULL"),
        nullable=True,
    )
    owner_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    team_id = Column(
        Integer,
        ForeignKey("teams.id", ondelete="SET NULL"),
        nullable=True,
    )

    is_active = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    is_protected = Column(Boolean, default=False, nullable=False)
    verify_ssl = Column(Boolean, default=True, nullable=False)
    priority = Column(Integer, default=0, nullable=False)

    # 0=OK, 1=Failed, 2=Warning, 3=In Progress, 4=Pending
    status_flag = Column(Integer, nullable=False, default=0)
    status_text = Column(String(500), nullable=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)

    # Soft delete
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    credential = relationship("Credential", foreign_keys=[credential_id])
    owner = relationship("User", foreign_keys=[owner_user_id])
    team = relationship("Team", foreign_keys=[team_id])
    role_scopes = relationship(
        "RoleScopeProvider", back_populates="provider", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "category != 'private' OR owner_user_id IS NOT NULL",
            name="ck_resource_providers_private_owner",
        ),
        CheckConstraint(
            "visibility != 'team' OR (team_id IS NOT NULL AND category = 'private')",
            name="ck_resource_providers_team_visibility",
        ),
        CheckConstraint(
            "visibility != 'team' OR owner_user_id IS NOT NULL",
            name="ck_resource_providers_team_owner",
        ),
        Index(
            "uq_resource_providers_name",
            "name",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = false"),
        ),
        Index(
            "uq_default_per_scope",
            "domain",
            "subtype",
            "category",
            "direction",
            unique=True,
            postgresql_where=text("is_default = true AND is_deleted = false"),
            sqlite_where=text("is_default = true AND is_deleted = false"),
        ),
        Index("ix_resource_providers_domain_subtype", "domain", "subtype"),
        Index("ix_resource_providers_category", "category"),
        Index("ix_resource_providers_owner", "owner_user_id"),
        Index("ix_resource_providers_team", "team_id"),
    )

    @property
    def team_name(self) -> str | None:
        """Name of the sharing team, when the relationship has been loaded."""
        return self.team.name if self.team is not None else None

    def __repr__(self) -> str:
        return (
            f"<ResourceProvider(id={self.id}, name='{self.name}', "
            f"domain='{self.domain.value if self.domain else None}', "
            f"subtype='{self.subtype.value if self.subtype else None}')>"
        )
