"""add_integration_instance_fields

Revision ID: a1b2c3d4e5f6
Revises: b0714dde902c
Create Date: 2026-06-07 01:05:00.000000+00:00

Adds missing fields to integration instance tables:
- gitlab_instances: verify_ssl, is_default, default_group_id, last_checked_at
- harbor_instances: verify_ssl, is_default, default_project, last_checked_at
- github_instances: is_default, last_checked_at
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "b0714dde902c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── gitlab_instances ──────────────────────────────────────────────
    op.add_column(
        "gitlab_instances",
        sa.Column("verify_ssl", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "gitlab_instances",
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "gitlab_instances",
        sa.Column("default_group_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "gitlab_instances",
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── harbor_instances ──────────────────────────────────────────────
    op.add_column(
        "harbor_instances",
        sa.Column("verify_ssl", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "harbor_instances",
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "harbor_instances",
        sa.Column("default_project", sa.String(255), nullable=True),
    )
    op.add_column(
        "harbor_instances",
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── github_instances ──────────────────────────────────────────────
    op.add_column(
        "github_instances",
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "github_instances",
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    # ── gitlab_instances ──────────────────────────────────────────────
    op.drop_column("gitlab_instances", "last_checked_at")
    op.drop_column("gitlab_instances", "default_group_id")
    op.drop_column("gitlab_instances", "is_default")
    op.drop_column("gitlab_instances", "verify_ssl")

    # ── harbor_instances ──────────────────────────────────────────────
    op.drop_column("harbor_instances", "last_checked_at")
    op.drop_column("harbor_instances", "default_project")
    op.drop_column("harbor_instances", "is_default")
    op.drop_column("harbor_instances", "verify_ssl")

    # ── github_instances ──────────────────────────────────────────────
    op.drop_column("github_instances", "last_checked_at")
    op.drop_column("github_instances", "is_default")
