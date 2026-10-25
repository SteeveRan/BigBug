"""sync_runs table — unified run tracking (heartbeat, failed_permanent, stuck)

Revision ID: afdc5da827aa
Revises: c0d2e4a6b810
Create Date: 2026-10-25 00:00:00.000000+00:00

One row per tracked task execution (issue #112, ADR-0039 Phase 4): the
operational index the console reads; log tables stay as detailed records.
"stuck" is computed (status=running AND heartbeat older than the window),
not stored — hence the partial index on active statuses only.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "afdc5da827aa"
down_revision: Union[str, None] = "c0d2e4a6b810"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sync_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_name", sa.String(length=200), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sync_runs_id"), "sync_runs", ["id"], unique=False)
    op.create_index(
        op.f("ix_sync_runs_task_entity"),
        "sync_runs",
        ["task_name", "entity_type", "entity_id"],
        unique=False,
    )
    op.create_index(
        "ix_sync_runs_active",
        "sync_runs",
        ["status"],
        unique=False,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
        sqlite_where=sa.text("status IN ('queued', 'running')"),
    )


def downgrade() -> None:
    op.drop_index("ix_sync_runs_active", table_name="sync_runs")
    op.drop_index(op.f("ix_sync_runs_task_entity"), table_name="sync_runs")
    op.drop_index(op.f("ix_sync_runs_id"), table_name="sync_runs")
    op.drop_table("sync_runs")
