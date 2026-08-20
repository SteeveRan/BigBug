"""add_helm_mirror_fields

Revision ID: a9f8e7d6c5b4
Revises: 5d4c3b2a1e0f
Create Date: 2026-08-20 00:45:00.000000+00:00

Adds ``target_repo_url`` to ``helm_chart_sources`` and ``chart_name`` /
``chart_version`` to ``helm_sync_logs`` so the Helm mirror action can record
the exact chart version being mirrored and the webhook can mark it as synced.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a9f8e7d6c5b4"
down_revision: Union[str, None] = "5d4c3b2a1e0f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "helm_chart_sources",
        sa.Column("target_repo_url", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "helm_sync_logs",
        sa.Column("chart_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "helm_sync_logs",
        sa.Column("chart_version", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("helm_sync_logs", "chart_version")
    op.drop_column("helm_sync_logs", "chart_name")
    op.drop_column("helm_chart_sources", "target_repo_url")
