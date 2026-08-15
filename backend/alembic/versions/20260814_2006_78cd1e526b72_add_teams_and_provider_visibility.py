"""add_teams_and_provider_visibility

Revision ID: 78cd1e526b72
Revises: 42348703bf96
Create Date: 2026-08-14 20:06:05.330576+00:00

Phase 0T (backend): teams model + provider sharing.

Creates the ``teams`` and ``team_members`` tables (12.1) and adds the
``visibility`` / ``team_id`` columns to ``resource_providers`` (12.1.3).
Existing provider rows are backfilled by category (12.6.2):

- ``system``  → ``owner``
- ``public``  → ``public``
- ``private`` → ``owner``

team sharing never existed before this phase, so no history is invented.

Downgrade drops the columns and tables. **WARNING:** this loses team-sharing
state — intended for development environments only (12.6.3).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '78cd1e526b72'
down_revision: str | None = '42348703bf96'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_visibility_enum() -> None:
    op.execute(
        text(
            "DO $$ BEGIN"
            " CREATE TYPE provider_visibility_enum AS ENUM ('owner', 'team', 'public');"
            " EXCEPTION WHEN duplicate_object THEN NULL;"
            " END $$"
        )
    )


def _create_team_role_enum() -> None:
    op.execute(
        text(
            "DO $$ BEGIN"
            " CREATE TYPE team_role_enum AS ENUM ('lead', 'member');"
            " EXCEPTION WHEN duplicate_object THEN NULL;"
            " END $$"
        )
    )


def upgrade() -> None:
    _create_visibility_enum()
    _create_team_role_enum()

    # ═══════════════════════════════════════════════════════════════════════
    # 1. teams
    # ═══════════════════════════════════════════════════════════════════════
    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "owner_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_teams_id"), "teams", ["id"], unique=False)
    op.create_index(
        "uq_teams_name",
        "teams",
        ["name"],
        unique=True,
        postgresql_where=text("is_deleted = false"),
    )
    op.create_index(op.f("ix_teams_owner"), "teams", ["owner_user_id"], unique=False)

    # ═══════════════════════════════════════════════════════════════════════
    # 2. team_members
    # ═══════════════════════════════════════════════════════════════════════
    op.create_table(
        "team_members",
        sa.Column(
            "team_id",
            sa.Integer(),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("team_id", "user_id"),
    )
    op.execute(
        text(
            "ALTER TABLE team_members ALTER COLUMN role "
            "TYPE team_role_enum USING role::team_role_enum"
        )
    )
    op.create_index(op.f("ix_team_members_user"), "team_members", ["user_id"], unique=False)

    # ═══════════════════════════════════════════════════════════════════════
    # 3. resource_providers.visibility / team_id
    # ═══════════════════════════════════════════════════════════════════════
    op.add_column(
        "resource_providers",
        sa.Column("visibility", sa.String(50), nullable=False),
    )
    op.add_column(
        "resource_providers",
        sa.Column(
            "team_id",
            sa.Integer(),
            sa.ForeignKey("teams.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    # Backfill visibility by category (12.6.2) BEFORE converting to enum, so the
    # textual CASE values do not need an explicit enum cast. team_id stays NULL.
    op.execute(
        text(
            "UPDATE resource_providers SET visibility = CASE"
            " WHEN category = 'public' THEN 'public'"
            " ELSE 'owner'"
            " END"
        )
    )

    op.execute(
        text(
            "ALTER TABLE resource_providers ALTER COLUMN visibility "
            "TYPE provider_visibility_enum USING visibility::provider_visibility_enum"
        )
    )

    op.create_check_constraint(
        "ck_resource_providers_team_visibility",
        "resource_providers",
        "visibility != 'team' OR (team_id IS NOT NULL AND category = 'private')",
    )
    op.create_check_constraint(
        "ck_resource_providers_team_owner",
        "resource_providers",
        "visibility != 'team' OR owner_user_id IS NOT NULL",
    )
    op.create_index(
        op.f("ix_resource_providers_team"),
        "resource_providers",
        ["team_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_resource_providers_team"), table_name="resource_providers")
    op.drop_constraint(
        "ck_resource_providers_team_owner", "resource_providers", type_="check"
    )
    op.drop_constraint(
        "ck_resource_providers_team_visibility", "resource_providers", type_="check"
    )
    op.drop_column("resource_providers", "team_id")
    op.drop_column("resource_providers", "visibility")

    op.drop_index(op.f("ix_team_members_user"), table_name="team_members")
    op.drop_table("team_members")

    op.drop_index(op.f("ix_teams_owner"), table_name="teams")
    op.drop_index("uq_teams_name", table_name="teams")
    op.drop_index(op.f("ix_teams_id"), table_name="teams")
    op.drop_table("teams")

    op.execute(text("DROP TYPE IF EXISTS team_role_enum"))
    op.execute(text("DROP TYPE IF EXISTS provider_visibility_enum"))
