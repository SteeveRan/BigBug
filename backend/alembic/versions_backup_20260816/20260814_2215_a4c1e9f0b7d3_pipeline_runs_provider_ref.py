"""pipeline runs reference resource_providers

Revision ID: a4c1e9f0b7d3
Revises: 00932f2a02d5
Create Date: 2026-08-14 22:15:00.000000+00:00

Phase 4 of the unified Providers V3 refactoring (plans/features/providers-unified.md):

* ``pipeline_runs.gitlab_instance_id`` becomes nullable — runs triggered via
  a ``resource_providers`` row (the system/internal GitLab) no longer require
  a legacy ``gitlab_instances`` row;
* additive ``pipeline_runs.provider_id`` FK (ON DELETE SET NULL) mirrors the
  consumer relink columns introduced by phase 3.

The legacy column and its historical values are kept for phase 7 cleanup.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4c1e9f0b7d3"
down_revision: str | None = "00932f2a02d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("pipeline_runs", sa.Column("provider_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_pipeline_runs_provider_id",
        "pipeline_runs",
        "resource_providers",
        ["provider_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_pipeline_runs_provider_id"), "pipeline_runs", ["provider_id"])
    op.alter_column(
        "pipeline_runs",
        "gitlab_instance_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "pipeline_runs",
        "gitlab_instance_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.drop_index(op.f("ix_pipeline_runs_provider_id"), table_name="pipeline_runs")
    op.drop_constraint("fk_pipeline_runs_provider_id", "pipeline_runs", type_="foreignkey")
    op.drop_column("pipeline_runs", "provider_id")
