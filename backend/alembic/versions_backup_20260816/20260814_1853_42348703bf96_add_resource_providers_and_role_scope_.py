"""add_resource_providers_and_role_scope_providers

Revision ID: 42348703bf96
Revises: 7d1b6bdfaef6
Create Date: 2026-08-14 18:53:20.365098+00:00

Phase 1 of the unified Providers V3 refactoring. Creates:

- ``resource_providers`` — the unified provider table (git/docker/helm),
  replacing the legacy per-domain instance tables over subsequent phases.
- ``role_scope_providers`` — link table for role → provider scoping (6.3).
- ``gitlab_components`` timezone fix: ``created_at``/``updated_at`` lacked
  ``timezone=True`` (11.2.3 convention bug) — corrected as a side migration.

[Р3] ``visibility``/``team_id`` columns and team-sharing invariants are
deliberately deferred to Phase 0T and are NOT part of this revision.

Enum columns follow the proven pattern from ``20260613_1307``: enum types are
created idempotently via ``DO $$``, columns are created as ``String`` and then
altered to the enum type (avoids a duplicate ``CREATE TYPE`` emitted by
SQLAlchemy's native enum handling during ``create_table``).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "42348703bf96"
down_revision: Union[str, None] = "7d1b6bdfaef6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ENUM_TYPES = [
    ("provider_domain_enum", "'git', 'docker', 'helm'"),
    (
        "provider_subtype_enum",
        "'github', 'gitlab', 'generic_git', 'docker_hub', 'quay', 'gcr', "
        "'ecr', 'acr', 'ghcr', 'harbor', 'generic_registry', 'helm_repo'",
    ),
    ("provider_category_enum", "'system', 'public', 'private'"),
    ("provider_direction_enum", "'external', 'internal'"),
]


def _create_enum_types() -> None:
    for name, values in _ENUM_TYPES:
        op.execute(
            text(
                f"DO $$ BEGIN"
                f" CREATE TYPE {name} AS ENUM ({values});"
                f" EXCEPTION WHEN duplicate_object THEN NULL;"
                f" END $$"
            )
        )


def _alter_to_enum(table: str, column: str, enum_name: str) -> None:
    op.execute(
        text(
            f"ALTER TABLE {table} ALTER COLUMN {column} "
            f"TYPE {enum_name} USING {column}::{enum_name}"
        )
    )


def upgrade() -> None:
    _create_enum_types()

    # ═══════════════════════════════════════════════════════════════════════
    # 1. resource_providers
    # ═══════════════════════════════════════════════════════════════════════
    op.create_table(
        "resource_providers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("domain", sa.String(50), nullable=False),
        sa.Column("subtype", sa.String(50), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("direction", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("base_url", sa.String(500), nullable=True),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "credential_id",
            sa.Integer(),
            sa.ForeignKey("credentials.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "owner_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_protected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("verify_ssl", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status_flag", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status_text", sa.String(500), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "category != 'private' OR owner_user_id IS NOT NULL",
            name="ck_resource_providers_private_owner",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    _alter_to_enum("resource_providers", "domain", "provider_domain_enum")
    _alter_to_enum("resource_providers", "subtype", "provider_subtype_enum")
    _alter_to_enum("resource_providers", "category", "provider_category_enum")
    _alter_to_enum("resource_providers", "direction", "provider_direction_enum")

    op.create_index(op.f("ix_resource_providers_id"), "resource_providers", ["id"], unique=False)
    op.create_index(
        op.f("ix_resource_providers_domain_subtype"),
        "resource_providers",
        ["domain", "subtype"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resource_providers_category"),
        "resource_providers",
        ["category"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resource_providers_owner"),
        "resource_providers",
        ["owner_user_id"],
        unique=False,
    )
    op.create_index(
        "uq_resource_providers_name",
        "resource_providers",
        ["name"],
        unique=True,
        postgresql_where=text("is_deleted = false"),
    )
    op.create_index(
        "uq_default_per_scope",
        "resource_providers",
        ["domain", "subtype", "category", "direction"],
        unique=True,
        postgresql_where=text("is_default = true AND is_deleted = false"),
    )

    # ═══════════════════════════════════════════════════════════════════════
    # 2. role_scope_providers
    # ═══════════════════════════════════════════════════════════════════════
    op.create_table(
        "role_scope_providers",
        sa.Column(
            "role_id",
            sa.Integer(),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "provider_id",
            sa.Integer(),
            sa.ForeignKey("resource_providers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("role_id", "provider_id"),
    )

    # ═══════════════════════════════════════════════════════════════════════
    # 3. gitlab_components timezone fix (11.2.3)
    # ═══════════════════════════════════════════════════════════════════════
    op.alter_column(
        "gitlab_components",
        "created_at",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "gitlab_components",
        "updated_at",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        postgresql_using="updated_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    op.alter_column(
        "gitlab_components",
        "updated_at",
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        postgresql_using="updated_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "gitlab_components",
        "created_at",
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )

    op.drop_table("role_scope_providers")

    op.drop_index("uq_default_per_scope", table_name="resource_providers")
    op.drop_index("uq_resource_providers_name", table_name="resource_providers")
    op.drop_index(op.f("ix_resource_providers_owner"), table_name="resource_providers")
    op.drop_index(op.f("ix_resource_providers_category"), table_name="resource_providers")
    op.drop_index(op.f("ix_resource_providers_domain_subtype"), table_name="resource_providers")
    op.drop_index(op.f("ix_resource_providers_id"), table_name="resource_providers")
    op.drop_table("resource_providers")

    for name, _ in reversed(_ENUM_TYPES):
        op.execute(text(f"DROP TYPE IF EXISTS {name}"))
