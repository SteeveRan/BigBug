"""add_audit_logs

Revision ID: afa361eb7c0d
Revises: d1e2f3a4b5c6
Create Date: 2026-06-07 11:32:53.207236+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'afa361eb7c0d'
down_revision: Union[str, None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'user_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('action', sa.String(), nullable=False, index=True),
        sa.Column('resource_type', sa.String(), nullable=False, index=True),
        sa.Column('resource_id', sa.Integer(), nullable=True),
        sa.Column('resource_name', sa.String(), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, index=True),
    )


def downgrade() -> None:
    op.drop_table('audit_logs')
