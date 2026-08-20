"""
@file gitlab_project.py
@description GitlabProject model — a GitLab project managed by BigBug. A project
             is either a ``components`` project (hosts GitLab CI/CD components)
             or a ``pipelines`` project (hosts generated ``.gitlab-ci.yml`` and
             pipeline runs). Ownership/visibility mirror the ResourceProvider
             pattern (owner/team/public + soft delete + status flags 0-4).
@dependencies app.database.Base, ./resource_provider.py, ./user.py, ./team.py
@relatedFiles ./gitlab_component.py, ./pipeline.py, ./role_scope.py
"""

import enum
from datetime import UTC, datetime

from sqlalchemy import (
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


class GitlabProjectType(enum.StrEnum):
    components = "components"
    pipelines = "pipelines"


class ProjectVisibility(enum.StrEnum):
    owner = "owner"
    team = "team"
    public = "public"


class GitlabProject(Base):
    __tablename__ = "gitlab_projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)  # display name in GitLab
    path = Column(String(255), nullable=False)  # project slug
    namespace_path = Column(String(500), nullable=False)  # group/namespace
    full_path = Column(String(512), nullable=False)  # "namespace/path", unique per provider

    project_type = Column(
        SAEnum(GitlabProjectType, name="gitlab_project_type_enum"),
        nullable=False,
    )
    visibility = Column(
        SAEnum(ProjectVisibility, name="gitlab_project_visibility_enum"),
        nullable=False,
        default=ProjectVisibility.owner,
    )

    # Git provider of the owner: subtype=gitlab, category ∈ {system, private}
    provider_id = Column(
        Integer,
        ForeignKey("resource_providers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    external_id = Column(String(64), nullable=True, index=True)  # GitLab numeric id
    web_url = Column(String(500), nullable=True)
    default_branch = Column(String(255), nullable=False, default="main")
    gitlab_visibility = Column(String(32), nullable=True)  # private/internal/public

    description = Column(Text, nullable=True)
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

    # 0=OK, 1=Failed, 2=Warning, 3=In Progress, 4=Pending
    status_flag = Column(Integer, nullable=False, default=0)
    status_text = Column(String(500), nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)

    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    provider = relationship("ResourceProvider", foreign_keys=[provider_id])
    owner = relationship("User", foreign_keys=[owner_user_id])
    team = relationship("Team", foreign_keys=[team_id])
    components = relationship("GitLabComponent", back_populates="gitlab_project")
    pipelines = relationship("Pipeline", back_populates="gitlab_project")
    role_scopes = relationship(
        "RoleScopeGitlabProject", back_populates="project", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # one full_path per GitLab instance (provider); same path allowed on
        # different instances/accounts of one GitLab host — unique (provider, full_path)
        Index(
            "uq_gitlab_projects_provider_path",
            "provider_id",
            "full_path",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = false"),
        ),
        Index("ix_gitlab_projects_type", "project_type"),
        Index("ix_gitlab_projects_owner", "owner_user_id"),
        Index("ix_gitlab_projects_team", "team_id"),
        CheckConstraint(
            "visibility != 'team' OR team_id IS NOT NULL",
            name="ck_gitlab_projects_team_visibility",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<GitlabProject(id={self.id}, full_path='{self.full_path}', "
            f"project_type='{self.project_type.value if self.project_type else None}')>"
        )
