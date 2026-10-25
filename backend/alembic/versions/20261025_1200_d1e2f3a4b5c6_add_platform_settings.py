"""platform_settings table + maintenance_mode seed row (issue #114)

Revision ID: d1e2f3a4b5c6
Revises: afdc5da827aa
Create Date: 2026-10-25 12:00:00.000000+00:00

Generic key/value table — first consumer is the maintenance_mode flag that
stops scheduler enqueue passes. value is sa.JSON (SQLite-test compatible).
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "afdc5da827aa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "platform_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_platform_settings_key"),
    )
    op.create_index(op.f("ix_platform_settings_id"), "platform_settings", ["id"], unique=False)
    op.execute(
        "INSERT INTO platform_settings (key, value, updated_at) "
        "VALUES ('maintenance_mode', 'false', CURRENT_TIMESTAMP)"
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_platform_settings_id"), table_name="platform_settings")
    op.drop_table("platform_settings")
