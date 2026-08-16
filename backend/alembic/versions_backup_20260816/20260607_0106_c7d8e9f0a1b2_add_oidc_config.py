"""add_oidc_config

Revision ID: c7d8e9f0a1b2
Revises: a1b2c3d4e5f6
Create Date: 2026-06-07 01:06:00.000000+00:00

Creates the ``oidc_config`` singleton table. No default rows are
inserted — the OIDC service falls back to environment variables
when no DB row exists, keeping SSO disabled by default.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "oidc_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("issuer_url", sa.String(512), nullable=False, server_default=""),
        sa.Column("client_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("client_secret", sa.Text(), nullable=True),
        sa.Column(
            "frontend_client_id",
            sa.String(255),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("public_url", sa.String(512), nullable=True),
        sa.Column(
            "role_mapping",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_oidc_config_id"), "oidc_config", ["id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_oidc_config_id"), table_name="oidc_config")
    op.drop_table("oidc_config")
