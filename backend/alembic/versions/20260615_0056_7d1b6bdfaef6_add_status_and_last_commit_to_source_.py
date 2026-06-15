"""add_status_and_last_commit_to_source_repositories

Revision ID: 7d1b6bdfaef6
Revises: fca3d02d18b4
Create Date: 2026-06-15 00:56:28.642761+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7d1b6bdfaef6'
down_revision: Union[str, None] = 'fca3d02d18b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add status_flag, status_text, last_commit_sha, last_commit_date,
    last_commit_author, last_commit_message to source_repositories."""
    op.add_column(
        "source_repositories",
        sa.Column("status_flag", sa.Integer(), nullable=False, server_default="4"),
    )
    op.add_column(
        "source_repositories",
        sa.Column("status_text", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "source_repositories",
        sa.Column("last_commit_sha", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "source_repositories",
        sa.Column("last_commit_date", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "source_repositories",
        sa.Column("last_commit_author", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "source_repositories",
        sa.Column("last_commit_message", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Remove the status and last_commit columns from source_repositories."""
    op.drop_column("source_repositories", "last_commit_message")
    op.drop_column("source_repositories", "last_commit_author")
    op.drop_column("source_repositories", "last_commit_date")
    op.drop_column("source_repositories", "last_commit_sha")
    op.drop_column("source_repositories", "status_text")
    op.drop_column("source_repositories", "status_flag")
