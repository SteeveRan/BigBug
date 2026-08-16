"""remove source_repositories.source_provider_id (phase 7E)

Revision ID: d4e5f6a7b8c9
Revises: c9d0e1f2a3b4
Create Date: 2026-08-15 01:30:00.000000+00:00

Phase 7E of the unified Providers V3 refactoring (plans/features/providers-unified.md):

* the ``source_repositories.source_provider_id`` FK column is dropped; the
  unified ``provider_id`` column already added by phase 4 (00932f2a02d5) is the
  replacement and now the only git-provider reference.

The data mapping was performed earlier (phase 3/4), so no data backfill is
needed here. The legacy ``source_providers`` table, the V2 provider classes and
``app/schemas/source_provider.py`` are intentionally NOT dropped — that is
phase 7F.

Downgrade is structure-only: it restores the nullable column + FK + index so
the phase-4 read-through path keeps working; no data is backfilled.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c9d0e1f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# PostgreSQL default names for the legacy inline foreign key (created without an
# explicit ``name=`` in the original migration).
_LEGACY_FK = "source_repositories_source_provider_id_fkey"
_LEGACY_INDEX = "ix_source_repositories_source_provider_id"


def upgrade() -> None:
    op.drop_index(_LEGACY_INDEX, table_name="source_repositories")
    op.drop_constraint(_LEGACY_FK, "source_repositories", type_="foreignkey")
    op.drop_column("source_repositories", "source_provider_id")


def downgrade() -> None:
    op.add_column(
        "source_repositories",
        sa.Column("source_provider_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        _LEGACY_FK,
        "source_repositories",
        "source_providers",
        ["source_provider_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        _LEGACY_INDEX,
        "source_repositories",
        ["source_provider_id"],
    )
