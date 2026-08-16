"""fix_audit_log_datetime_timezone

Revision ID: e0f73c859e8e
Revises: c1d2e3f4a5b6
Create Date: 2026-06-10 22:42:01.016271+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e0f73c859e8e'
down_revision: Union[str, None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update audit_logs.created_at to use timezone-aware datetime
    op.alter_column('audit_logs', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               existing_nullable=True,
               schema=None)
    
    # Update pipeline_runs.created_at, started_at, finished_at to use timezone-aware datetime
    op.alter_column('pipeline_runs', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               existing_nullable=True,
               schema=None)
    op.alter_column('pipeline_runs', 'started_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               existing_nullable=True,
               schema=None)
    op.alter_column('pipeline_runs', 'finished_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               existing_nullable=True,
               schema=None)


def downgrade() -> None:
    # Revert audit_logs.created_at to use timezone-naive datetime
    op.alter_column('audit_logs', 'created_at',
               existing_type=sa.DateTime(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True,
               schema=None)
    
    # Revert pipeline_runs.created_at, started_at, finished_at to use timezone-naive datetime
    op.alter_column('pipeline_runs', 'created_at',
               existing_type=sa.DateTime(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True,
               schema=None)
    op.alter_column('pipeline_runs', 'started_at',
               existing_type=sa.DateTime(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True,
               schema=None)
    op.alter_column('pipeline_runs', 'finished_at',
               existing_type=sa.DateTime(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True,
               schema=None)
