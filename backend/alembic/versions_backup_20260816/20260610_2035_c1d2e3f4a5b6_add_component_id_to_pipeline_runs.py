"""add_component_id_to_pipeline_runs

Revision ID: c1d2e3f4a5b6
Revises: 81d92eaba280
Create Date: 2026-06-10 20:35:00.000000+00:00

Adds an optional ``component_id`` foreign key to ``pipeline_runs``
so that a run can be linked back to the ``gitlab_components`` table.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "81d92eaba280"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pipeline_runs",
        sa.Column("component_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_pipeline_runs_component_id"),
        "pipeline_runs",
        ["component_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_pipeline_runs_component_id",
        "pipeline_runs",
        "gitlab_components",
        ["component_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_pipeline_runs_component_id",
        "pipeline_runs",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_pipeline_runs_component_id"),
        table_name="pipeline_runs",
    )
    op.drop_column("pipeline_runs", "component_id")
