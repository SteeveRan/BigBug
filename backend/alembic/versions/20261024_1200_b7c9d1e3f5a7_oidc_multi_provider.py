"""oidc_multi_provider

Revision ID: b7c9d1e3f5a7
Revises: a9f8e7d6c5b4
Create Date: 2026-10-24 12:00:00.000000+00:00

Replaces the singleton `oidc_config` with an `oidc_providers` collection
(ADR-0037, issue #98): one row per OIDC provider, the legacy singleton row's
values migrate as is (no issuer_url enrichment per ADR-0036), the table is
then dropped.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b7c9d1e3f5a7"
down_revision: Union[str, None] = "a9f8e7d6c5b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "oidc_providers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("issuer_url", sa.String(length=512), nullable=False),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("client_secret", sa.Text(), nullable=True),
        sa.Column("frontend_client_id", sa.String(length=255), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("public_url", sa.String(length=512), nullable=True),
        sa.Column("role_mapping", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_oidc_providers_id"), "oidc_providers", ["id"], unique=False)

    # Migrate the legacy singleton row as is (no issuer_url enrichment per
    # ADR-0036: a value without /realms/ simply stays "not configured").
    conn = op.get_bind()
    legacy = conn.execute(
        sa.text(
            "SELECT issuer_url, client_id, client_secret, frontend_client_id, "
            "enabled, public_url, role_mapping::text AS role_mapping "
            "FROM oidc_config LIMIT 1"
        )
    ).mappings().first()
    if legacy is not None:
        conn.execute(
            sa.text(
                "INSERT INTO oidc_providers "
                "(name, issuer_url, client_id, client_secret, frontend_client_id, "
                "enabled, public_url, role_mapping, sort_order, created_at, updated_at) "
                "VALUES (:name, :issuer_url, :client_id, :client_secret, "
                ":frontend_client_id, :enabled, :public_url, "
                "CAST(:role_mapping AS json), 0, now(), now())"
            ),
            {
                "name": "Keycloak",
                "issuer_url": legacy["issuer_url"],
                "client_id": legacy["client_id"],
                "client_secret": legacy["client_secret"],
                "frontend_client_id": legacy["frontend_client_id"],
                "enabled": legacy["enabled"],
                "public_url": legacy["public_url"],
                "role_mapping": legacy["role_mapping"],
            },
        )
    op.drop_table("oidc_config")


def downgrade() -> None:
    op.create_table(
        "oidc_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("issuer_url", sa.String(length=512), nullable=False),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("client_secret", sa.Text(), nullable=True),
        sa.Column("frontend_client_id", sa.String(length=255), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("public_url", sa.String(length=512), nullable=True),
        sa.Column("role_mapping", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_oidc_config_id"), "oidc_config", ["id"], unique=False)

    conn = op.get_bind()
    first = conn.execute(
        sa.text(
            "SELECT issuer_url, client_id, client_secret, frontend_client_id, "
            "enabled, public_url, role_mapping::text AS role_mapping "
            "FROM oidc_providers ORDER BY sort_order, id LIMIT 1"
        )
    ).mappings().first()
    if first is not None:
        conn.execute(
            sa.text(
                "INSERT INTO oidc_config "
                "(issuer_url, client_id, client_secret, frontend_client_id, "
                "enabled, public_url, role_mapping, created_at, updated_at) "
                "VALUES (:issuer_url, :client_id, :client_secret, "
                ":frontend_client_id, :enabled, :public_url, "
                "CAST(:role_mapping AS json), now(), now())"
            ),
            dict(first),
        )
    op.drop_table("oidc_providers")
