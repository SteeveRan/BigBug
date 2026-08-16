"""add_repository_metadata_fields

Revision ID: dc0ef2cfb148
Revises: a7b8c9d0e1f2
Create Date: 2026-06-14 21:20:27.499456+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dc0ef2cfb148'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Добавляем поля с метаданными репозитория
    op.add_column(
        'source_repositories',
        sa.Column('language', sa.String(100), nullable=True),
    )
    op.add_column(
        'source_repositories',
        sa.Column('stars_count', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'source_repositories',
        sa.Column('forks_count', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'source_repositories',
        sa.Column('is_private', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade() -> None:
    op.drop_column('source_repositories', 'is_private')
    op.drop_column('source_repositories', 'forks_count')
    op.drop_column('source_repositories', 'stars_count')
    op.drop_column('source_repositories', 'language')
