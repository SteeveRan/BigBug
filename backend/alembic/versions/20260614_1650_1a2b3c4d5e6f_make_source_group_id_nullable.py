"""make_source_group_id_nullable

Revision ID: 1a2b3c4d5e6f
Revises: 3446791956ce
Create Date: 2026-06-14 16:50:00.000000+00:00

Allow source_repositories.source_group_id to be NULL for Generic Git providers
that have no organisational structure.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1a2b3c4d5e6f'
down_revision: Union[str, None] = '3446791956ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('source_repositories', 'source_group_id',
                    existing_type=sa.Integer(),
                    nullable=True)


def downgrade() -> None:
    op.alter_column('source_repositories', 'source_group_id',
                    existing_type=sa.Integer(),
                    nullable=False)
