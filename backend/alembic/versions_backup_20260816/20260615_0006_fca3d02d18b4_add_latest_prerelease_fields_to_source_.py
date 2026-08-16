"""add_latest_prerelease_fields_to_source_repositories

Revision ID: fca3d02d18b4
Revises: e5f6a7b8c9d0
Create Date: 2026-06-15 00:06:21.539499+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "fca3d02d18b4"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "source_repositories",
        sa.Column("latest_prerelease_tag", sa.String(255), nullable=True),
    )
    op.add_column(
        "source_repositories",
        sa.Column("latest_prerelease_name", sa.String(255), nullable=True),
    )
    op.add_column(
        "source_repositories",
        sa.Column("latest_prerelease_date", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "source_repositories",
        sa.Column("latest_prerelease_url", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("source_repositories", "latest_prerelease_url")
    op.drop_column("source_repositories", "latest_prerelease_date")
    op.drop_column("source_repositories", "latest_prerelease_name")
    op.drop_column("source_repositories", "latest_prerelease_tag")
