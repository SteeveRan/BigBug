"""add_registry_type_and_source_link

Revision ID: f1a2b3c4d5e6
Revises: e0f73c859e8e
Create Date: 2026-06-13 01:00:00

Add registry_type, registry_provider, and priority columns to
docker_registry_instances. Add registry_instance_id FK to docker_image_sources
so image sources can link to their configured source registry instance.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e0f73c859e8e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ────────────────── docker_registry_instances ──────────────────
    op.add_column(
        "docker_registry_instances",
        sa.Column(
            "registry_type",
            sa.String(20),
            nullable=False,
            server_default="external",
            comment="Classification: internal (company registries) or external (third-party)",
        ),
    )
    op.add_column(
        "docker_registry_instances",
        sa.Column(
            "registry_provider",
            sa.String(20),
            nullable=False,
            server_default="generic",
            comment="Known registry provider for auto-detection and matching",
        ),
    )
    op.add_column(
        "docker_registry_instances",
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Higher priority = preferred for auto-selection when multiple registries match",
        ),
    )

    # ────────────────── docker_image_sources ──────────────────
    op.add_column(
        "docker_image_sources",
        sa.Column(
            "registry_instance_id",
            sa.Integer(),
            sa.ForeignKey("docker_registry_instances.id", ondelete="SET NULL"),
            nullable=True,
            comment="Configured registry instance used as source for this image",
        ),
    )
    op.create_index(
        op.f("ix_docker_image_sources_registry_instance_id"),
        "docker_image_sources",
        ["registry_instance_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_docker_image_sources_registry_instance_id"),
        table_name="docker_image_sources",
    )
    op.drop_column("docker_image_sources", "registry_instance_id")
    op.drop_column("docker_registry_instances", "priority")
    op.drop_column("docker_registry_instances", "registry_provider")
    op.drop_column("docker_registry_instances", "registry_type")
