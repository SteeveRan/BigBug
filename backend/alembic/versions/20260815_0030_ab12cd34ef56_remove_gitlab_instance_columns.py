"""remove legacy gitlab_instance columns (phase 7A)

Revision ID: ab12cd34ef56
Revises: b8d4e5f6a7c9
Create Date: 2026-08-15 00:30:00.000000+00:00

Phase 7A of the unified Providers V3 refactoring (plans/features/providers-unified.md):

* ``gitlab_components`` gains a ``provider_id`` FK (ON DELETE SET NULL) to
  ``resource_providers`` and backfills it from the legacy ``gitlab_instance_id``
  via the deterministic ``legacy-gitlab-{name}`` provider slug created by phase 3
  (00932f2a02d5);
* the legacy ``gitlab_instance_id`` columns are dropped from
  ``gitlab_components``, ``pipelines`` and ``pipeline_runs``.

The legacy ``gitlab_instances`` table itself is intentionally NOT dropped here —
that is phase 7F, together with the remaining ``app/api/integrations/*`` and
``app/services/integrations.py`` consumers.

Downgrade restores the three legacy columns and backfills them from the
``provider_id`` reverse mapping (``resource_providers.name`` →
``legacy-gitlab-{gitlab_instances.name}``), so the phase-3 read-through path
keeps working.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ab12cd34ef56"
down_revision: str | None = "b8d4e5f6a7c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# PostgreSQL default names for the legacy inline foreign keys (they were created
# without an explicit ``name=`` in the original migrations).
_LEGACY_FKS = {
    "gitlab_components": "gitlab_components_gitlab_instance_id_fkey",
    "pipelines": "pipelines_gitlab_instance_id_fkey",
    "pipeline_runs": "pipeline_runs_gitlab_instance_id_fkey",
}


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. gitlab_components: add provider_id and backfill ─────────────────
    op.add_column(
        "gitlab_components", sa.Column("provider_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_gitlab_components_provider_id",
        "gitlab_components",
        "resource_providers",
        ["provider_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_gitlab_components_provider_id"), "gitlab_components", ["provider_id"]
    )

    conn.execute(
        sa.text(
            """
            UPDATE gitlab_components gc
            SET provider_id = rp.id
            FROM gitlab_instances gi
            JOIN resource_providers rp
              ON rp.name = 'legacy-gitlab-' || gi.name
            WHERE gc.gitlab_instance_id = gi.id
              AND gc.provider_id IS NULL
            """
        )
    )

    # provider_id is NOT NULL on the model; the legacy FK guaranteed every
    # component had a gitlab_instances row, so the backfill above is complete.
    op.alter_column(
        "gitlab_components",
        "provider_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    # ── 2. Drop legacy gitlab_instance_id columns ──────────────────────────
    for table in ("gitlab_components", "pipelines", "pipeline_runs"):
        op.drop_constraint(_LEGACY_FKS[table], table, type_="foreignkey")
        op.drop_column(table, "gitlab_instance_id")


def downgrade() -> None:
    conn = op.get_bind()

    # ── 1. Restore legacy columns (nullable first for backfill) ────────────
    op.add_column(
        "gitlab_components", sa.Column("gitlab_instance_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "pipelines", sa.Column("gitlab_instance_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "pipeline_runs", sa.Column("gitlab_instance_id", sa.Integer(), nullable=True)
    )

    # ── 2. Backfill from provider_id via the phase-3 slug ─────────────────
    for table in ("gitlab_components", "pipelines"):
        conn.execute(
            sa.text(
                f"""
                UPDATE {table} t
                SET gitlab_instance_id = gi.id
                FROM resource_providers rp
                JOIN gitlab_instances gi
                  ON rp.name = 'legacy-gitlab-' || gi.name
                WHERE t.provider_id = rp.id
                  AND t.gitlab_instance_id IS NULL
                """
            )
        )

    conn.execute(
        sa.text(
            """
            UPDATE pipeline_runs pr
            SET gitlab_instance_id = gi.id
            FROM resource_providers rp
            JOIN gitlab_instances gi
              ON rp.name = 'legacy-gitlab-' || gi.name
            WHERE pr.provider_id = rp.id
              AND pr.gitlab_instance_id IS NULL
            """
        )
    )

    # ── 3. Restore foreign keys and NOT NULL where historically required ──
    op.create_foreign_key(
        _LEGACY_FKS["gitlab_components"],
        "gitlab_components",
        "gitlab_instances",
        ["gitlab_instance_id"],
        ["id"],
    )
    op.alter_column(
        "gitlab_components",
        "gitlab_instance_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.create_foreign_key(
        _LEGACY_FKS["pipelines"],
        "pipelines",
        "gitlab_instances",
        ["gitlab_instance_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # pipeline_runs.gitlab_instance_id was made nullable by a4c1e9f0b7d3, so
    # restore it in that (post-phase-4) nullable state rather than NOT NULL.
    op.create_foreign_key(
        _LEGACY_FKS["pipeline_runs"],
        "pipeline_runs",
        "gitlab_instances",
        ["gitlab_instance_id"],
        ["id"],
    )

    # ── 4. Drop gitlab_components.provider_id ──────────────────────────────
    op.drop_index(op.f("ix_gitlab_components_provider_id"), table_name="gitlab_components")
    op.drop_constraint(
        "fk_gitlab_components_provider_id", "gitlab_components", type_="foreignkey"
    )
    op.drop_column("gitlab_components", "provider_id")
