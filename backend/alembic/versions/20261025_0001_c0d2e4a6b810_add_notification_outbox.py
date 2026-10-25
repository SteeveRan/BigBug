"""notification_outbox table (transactional outbox, ADR-0039 Phase 3)

Revision ID: c0d2e4a6b810
Revises: fb1eef4e684f
Create Date: 2026-10-25 00:00:00.000000+00:00

Adds ``notification_outbox``: rows are written in the SAME transaction as the
sync commit; ``send_pending_outbox_task`` marks them sent. The unique
``dedup_key`` makes crash-restarts and task redelivery produce no duplicates.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c0d2e4a6b810"
down_revision: Union[str, None] = "fb1eef4e684f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_outbox",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dedup_key", sa.String(length=500), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_notification_outbox_id"), "notification_outbox", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_notification_outbox_dedup_key"),
        "notification_outbox",
        ["dedup_key"],
        unique=True,
    )
    op.create_index(
        op.f("ix_notification_outbox_sent_at"), "notification_outbox", ["sent_at"], unique=False
    )
    op.create_index(
        "ix_notification_outbox_unsent",
        "notification_outbox",
        ["created_at"],
        unique=False,
        postgresql_where=sa.text("sent_at IS NULL"),
        sqlite_where=sa.text("sent_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_notification_outbox_unsent", table_name="notification_outbox")
    op.drop_index(op.f("ix_notification_outbox_sent_at"), table_name="notification_outbox")
    op.drop_index(op.f("ix_notification_outbox_dedup_key"), table_name="notification_outbox")
    op.drop_index(op.f("ix_notification_outbox_id"), table_name="notification_outbox")
    op.drop_table("notification_outbox")
