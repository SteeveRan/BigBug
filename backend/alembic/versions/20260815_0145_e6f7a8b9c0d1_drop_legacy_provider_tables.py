"""drop legacy provider instance tables (phase 7F)

Revision ID: e6f7a8b9c0d1
Revises: d4e5f6a7b8c9
Create Date: 2026-08-15 01:45:00.000000+00:00

Phase 7F of the unified Providers V3 refactoring (plans/features/providers-unified.md):

Drops the six legacy provider tables that were fully absorbed by
``resource_providers`` (data migrated in phase 3, 00932f2a02d5) and whose
consumers were re-pointed at ``resource_providers`` in phases 7A–7E:

* ``source_providers``           → domain=git, direction=external
* ``gitlab_instances``           → subtype=gitlab, category=system/internal
* ``github_instances``           → subtype=github, category=private/external
* ``harbor_instances``           → subtype=harbor, category=system/internal
* ``docker_registry_instances``  → subtype=*/direction per RegistryType
* ``helm_repository_instances``  → subtype=helm_repo

``github_orgs`` / ``github_projects`` / ``github_releases`` are NOT dropped —
they are the live Builds/AppImages subsystem (contradicting plan 1.6 which the
customer explicitly overrode).

Downgrade is structure-only: it recreates the six tables' columns and core
indexes so the phase-3 read-through path can be reconstructed, but no data is
backfilled (legacy data was already migrated and is not recoverable here).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e6f7a8b9c0d1"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "source_providers",
    "gitlab_instances",
    "github_instances",
    "harbor_instances",
    "docker_registry_instances",
    "helm_repository_instances",
)


def upgrade() -> None:
    # Drop in reverse dependency order (source_providers has an outbound FK to
    # credentials, the instance tables are leaves). No other table still holds
    # an inbound FK to these after phases 7A/7C/7E.
    for table in reversed(_TABLES):
        op.drop_table(table)


def downgrade() -> None:
    # Structure-only recreation. Only the columns needed by the (now removed)
    # consumers are restored; data is not backfilled.
    op.create_table(
        "gitlab_instances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.String(512), nullable=False),
        sa.Column("token", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("verify_ssl", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("default_group_id", sa.Integer(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status_flag", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status_text", sa.String(255), nullable=False, server_default="OK"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_gitlab_instances_id", "gitlab_instances", ["id"])
    op.create_index("ix_gitlab_instances_name", "gitlab_instances", ["name"], unique=True)

    op.create_table(
        "github_instances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("token", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status_flag", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status_text", sa.String(255), nullable=False, server_default="OK"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_github_instances_id", "github_instances", ["id"])
    op.create_index("ix_github_instances_name", "github_instances", ["name"], unique=True)

    op.create_table(
        "harbor_instances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.String(512), nullable=False),
        sa.Column("username", sa.String(255), nullable=False),
        sa.Column("password", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("verify_ssl", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("default_project", sa.String(255), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status_flag", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status_text", sa.String(255), nullable=False, server_default="OK"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_harbor_instances_id", "harbor_instances", ["id"])
    op.create_index("ix_harbor_instances_name", "harbor_instances", ["name"], unique=True)

    op.create_table(
        "docker_registry_instances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("password", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("verify_ssl", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status_flag", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status_text", sa.String(255), nullable=False, server_default="OK"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_docker_registry_instances_id", "docker_registry_instances", ["id"])
    op.create_index(
        "ix_docker_registry_instances_name", "docker_registry_instances", ["name"], unique=True
    )

    op.create_table(
        "helm_repository_instances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("password", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("verify_ssl", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status_flag", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status_text", sa.String(255), nullable=False, server_default="OK"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_helm_repository_instances_id", "helm_repository_instances", ["id"])
    op.create_index(
        "ix_helm_repository_instances_name", "helm_repository_instances", ["name"], unique=True
    )

    op.create_table(
        "source_providers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "credential_id",
            sa.Integer(),
            sa.ForeignKey("credentials.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "provider_type",
            sa.Enum("github", "gitlab", "generic", name="provider_type_enum"),
            nullable=False,
        ),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("is_anon", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_source_providers_id", "source_providers", ["id"])
