"""add_oidc_config

Revision ID: c7d8e9f0a1b2
Revises: a1b2c3d4e5f6
Create Date: 2026-06-07 01:06:00.000000+00:00

Creates the ``oidc_config`` singleton table and seeds a default row
from the current Keycloak environment variables, so the existing
settings-based OIDC configuration survives the migration.
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


def _seed_default_config() -> None:
    """Insert a single default row populated from the current settings."""
    # Deferred import so the module-level settings singleton is fully
    # initialised by the time Alembic calls upgrade().
    from app.config import settings  # noqa: PLC0415

    conn = op.get_bind()

    # Check if a row already exists (idempotent re-run safety).
    oidc_config_table = sa.table(
        "oidc_config",
        sa.column("id", sa.Integer),
    )
    existing = conn.execute(
        sa.select(oidc_config_table.c.id).limit(1)
    ).first()
    if existing is not None:
        return  # Already seeded

    # Build the default row from environment variables.  client_secret is
    # stored *unencrypted* here — the OIDCConfigService encrypts it
    # on first read or the admin can update it via the API afterwards.
    default_row = {
        "issuer_url": getattr(settings, "keycloak_url", "http://localhost:8180"),
        "client_id": getattr(settings, "keycloak_client_id", ""),
        "client_secret": getattr(settings, "keycloak_client_secret", ""),
        "frontend_client_id": getattr(
            settings, "keycloak_frontend_client_id", ""
        ),
        "enabled": bool(
            getattr(settings, "keycloak_frontend_client_id", "")
            and getattr(settings, "keycloak_public_url", "")
        ),
        "public_url": getattr(settings, "keycloak_public_url", None),
        "role_mapping": {
            "admin": "admin",
            "operator": "operator",
            "viewer": "viewer",
        },
    }

    op.bulk_insert(
        sa.table(
            "oidc_config",
            sa.column("issuer_url", sa.String),
            sa.column("client_id", sa.String),
            sa.column("client_secret", sa.Text),
            sa.column("frontend_client_id", sa.String),
            sa.column("enabled", sa.Boolean),
            sa.column("public_url", sa.String),
            sa.column("role_mapping", postgresql.JSON),
        ),
        [default_row],
    )


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

    _seed_default_config()


def downgrade() -> None:
    op.drop_index(op.f("ix_oidc_config_id"), table_name="oidc_config")
    op.drop_table("oidc_config")
