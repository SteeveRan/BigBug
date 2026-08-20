"""add_gitlab_projects

Revision ID: 7f3a2c1b4d5e
Revises: a1b2c3d4e5f6
Create Date: 2026-08-20 00:41:00.000000+00:00

Creates the ``gitlab_projects`` table (with project_type and visibility
enums), the ``role_scope_gitlab_projects`` scope table, and the associated
indexes/constraints defined in ``plans/gitlab-project-management-spec.md`` §3.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "7f3a2c1b4d5e"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    gitlab_project_type_enum = sa.Enum(
        "components", "pipelines", name="gitlab_project_type_enum"
    )
    gitlab_project_visibility_enum = sa.Enum(
        "owner", "team", "public", name="gitlab_project_visibility_enum"
    )
    # NOTE: do not call .create() here — op.create_table() auto-emits CREATE TYPE
    # for named sa.Enum columns (same pattern as initial_schema.py). The explicit
    # .create() caused a DuplicateObjectError on upgrade.

    op.create_table(
        "gitlab_projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("path", sa.String(length=255), nullable=False),
        sa.Column("namespace_path", sa.String(length=500), nullable=False),
        sa.Column("full_path", sa.String(length=512), nullable=False),
        sa.Column(
            "project_type",
            gitlab_project_type_enum,
            nullable=False,
        ),
        sa.Column(
            "visibility",
            gitlab_project_visibility_enum,
            nullable=False,
        ),
        sa.Column("provider_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=64), nullable=True),
        sa.Column("web_url", sa.String(length=500), nullable=True),
        sa.Column("default_branch", sa.String(length=255), nullable=False),
        sa.Column("gitlab_visibility", sa.String(length=32), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("status_flag", sa.Integer(), nullable=False),
        sa.Column("status_text", sa.String(length=500), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "visibility != 'team' OR team_id IS NOT NULL",
            name="ck_gitlab_projects_team_visibility",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"], ["resource_providers.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_gitlab_projects_id"), "gitlab_projects", ["id"], unique=False
    )
    op.create_index(
        "ix_gitlab_projects_type",
        "gitlab_projects",
        ["project_type"],
        unique=False,
    )
    op.create_index(
        "ix_gitlab_projects_owner",
        "gitlab_projects",
        ["owner_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_gitlab_projects_team", "gitlab_projects", ["team_id"], unique=False
    )
    op.create_index(
        op.f("ix_gitlab_projects_provider_id"),
        "gitlab_projects",
        ["provider_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_gitlab_projects_external_id"),
        "gitlab_projects",
        ["external_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_gitlab_projects_is_deleted"),
        "gitlab_projects",
        ["is_deleted"],
        unique=False,
    )
    op.create_index(
        "uq_gitlab_projects_provider_path",
        "gitlab_projects",
        ["provider_id", "full_path"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
        sqlite_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "role_scope_gitlab_projects",
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("gitlab_project_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["gitlab_project_id"], ["gitlab_projects.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "gitlab_project_id"),
    )


def downgrade() -> None:
    op.drop_table("role_scope_gitlab_projects")
    op.drop_index(
        "uq_gitlab_projects_provider_path",
        table_name="gitlab_projects",
        postgresql_where=sa.text("is_deleted = false"),
        sqlite_where=sa.text("is_deleted = false"),
    )
    op.drop_index(
        op.f("ix_gitlab_projects_is_deleted"), table_name="gitlab_projects"
    )
    op.drop_index(
        op.f("ix_gitlab_projects_external_id"), table_name="gitlab_projects"
    )
    op.drop_index(
        op.f("ix_gitlab_projects_provider_id"), table_name="gitlab_projects"
    )
    op.drop_index("ix_gitlab_projects_team", table_name="gitlab_projects")
    op.drop_index("ix_gitlab_projects_owner", table_name="gitlab_projects")
    op.drop_index("ix_gitlab_projects_type", table_name="gitlab_projects")
    op.drop_index(op.f("ix_gitlab_projects_id"), table_name="gitlab_projects")
    op.drop_table("gitlab_projects")

    sa.Enum(name="gitlab_project_type_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="gitlab_project_visibility_enum").drop(
        op.get_bind(), checkfirst=True
    )
