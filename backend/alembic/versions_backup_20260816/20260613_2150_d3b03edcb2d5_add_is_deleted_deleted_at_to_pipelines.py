"""add_is_deleted_deleted_at_to_pipelines

Revision ID: d3b03edcb2d5
Revises: b214fda62040
Create Date: 2026-06-13 21:50:02.972814+00:00

Adds ``is_deleted`` and ``deleted_at`` columns to the ``pipelines`` table
to support soft-delete functionality (consistent with Mirror, SyncGroup,
SourceGroup, and SourceRepository which already have these columns).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d3b03edcb2d5"
down_revision: Union[str, None] = "b214fda62040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pipelines",
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
    )
    op.add_column(
        "pipelines",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_pipelines_is_deleted", "pipelines", ["is_deleted"])


def downgrade() -> None:
    op.drop_index("ix_pipelines_is_deleted", table_name="pipelines")
    op.drop_column("pipelines", "deleted_at")
    op.drop_column("pipelines", "is_deleted")
