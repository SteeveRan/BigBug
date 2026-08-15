"""remove docker_image_sources.registry_instance_id (phase 7C)

Revision ID: c9d0e1f2a3b4
Revises: ab12cd34ef56
Create Date: 2026-08-15 01:00:00.000000+00:00

Phase 7C of the unified Providers V3 refactoring (plans/features/providers-unified.md):

* the ``docker_image_sources.registry_instance_id`` FK column is dropped; the
  unified ``provider_id`` / ``target_provider_id`` columns already added by
  phase 3/4 are the replacement.

The data mapping was performed earlier (phase 3, 00932f2a02d5), so no data
backfill is needed here. The legacy ``docker_registry_instances`` table and
``app/services/integrations.py`` consumers are intentionally NOT dropped —
that is phase 7F.

Downgrade is structure-only: it restores the nullable column + FK + index so
the phase-3 read-through path keeps working; no data is backfilled.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9d0e1f2a3b4"
down_revision: str | None = "ab12cd34ef56"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# PostgreSQL default names for the legacy inline foreign key (created without an
# explicit ``name=`` in 20260612_2200_f1a2b3c4d5e6).
_LEGACY_FK = "docker_image_sources_registry_instance_id_fkey"
_LEGACY_INDEX = "ix_docker_image_sources_registry_instance_id"


def upgrade() -> None:
    op.drop_index(_LEGACY_INDEX, table_name="docker_image_sources")
    op.drop_constraint(_LEGACY_FK, "docker_image_sources", type_="foreignkey")
    op.drop_column("docker_image_sources", "registry_instance_id")


def downgrade() -> None:
    op.add_column(
        "docker_image_sources",
        sa.Column("registry_instance_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        _LEGACY_FK,
        "docker_image_sources",
        "docker_registry_instances",
        ["registry_instance_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        _LEGACY_INDEX,
        "docker_image_sources",
        ["registry_instance_id"],
    )
