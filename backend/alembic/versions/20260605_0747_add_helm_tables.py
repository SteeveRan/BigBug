"""add helm chart source, version and sync_log tables

Revision ID: 20260605_add_helm
Revises: 39774f94ac35
Create Date: 2026-06-05 07:47:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260605_add_helm'
down_revision: Union[str, None] = '39774f94ac35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('helm_chart_sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('repo_url', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('gitlab_project_id', sa.String(length=255), nullable=True),
        sa.Column('gitlab_project_url', sa.String(length=500), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status_flag', sa.Integer(), nullable=False),
        sa.Column('status_text', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_helm_chart_sources_id'), 'helm_chart_sources', ['id'], unique=False)
    op.create_index(op.f('ix_helm_chart_sources_name'), 'helm_chart_sources', ['name'], unique=True)

    op.create_table('helm_chart_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('chart_name', sa.String(length=255), nullable=False),
        sa.Column('version', sa.String(length=100), nullable=False),
        sa.Column('app_version', sa.String(length=100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('digest', sa.String(length=255), nullable=True),
        sa.Column('urls', sa.Text(), nullable=True),
        sa.Column('chart_url', sa.String(length=500), nullable=True),
        sa.Column('gitlab_project_id', sa.String(length=255), nullable=True),
        sa.Column('status_flag', sa.Integer(), nullable=False),
        sa.Column('status_text', sa.String(length=500), nullable=True),
        sa.Column('is_synced', sa.Boolean(), nullable=False),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['source_id'], ['helm_chart_sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_helm_chart_versions_chart_name'), 'helm_chart_versions', ['chart_name'], unique=False)
    op.create_index(op.f('ix_helm_chart_versions_id'), 'helm_chart_versions', ['id'], unique=False)
    op.create_index(op.f('ix_helm_chart_versions_source_id'), 'helm_chart_versions', ['source_id'], unique=False)

    op.create_table('helm_sync_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('pipeline_id', sa.String(length=255), nullable=True),
        sa.Column('pipeline_url', sa.String(length=500), nullable=True),
        sa.Column('status_flag', sa.Integer(), nullable=False),
        sa.Column('status_text', sa.String(length=500), nullable=True),
        sa.Column('log_output', sa.Text(), nullable=True),
        sa.Column('triggered_by', sa.String(length=100), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['source_id'], ['helm_chart_sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_helm_sync_logs_id'), 'helm_sync_logs', ['id'], unique=False)
    op.create_index(op.f('ix_helm_sync_logs_source_id'), 'helm_sync_logs', ['source_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_helm_sync_logs_source_id'), table_name='helm_sync_logs')
    op.drop_index(op.f('ix_helm_sync_logs_id'), table_name='helm_sync_logs')
    op.drop_table('helm_sync_logs')
    op.drop_index(op.f('ix_helm_chart_versions_source_id'), table_name='helm_chart_versions')
    op.drop_index(op.f('ix_helm_chart_versions_id'), table_name='helm_chart_versions')
    op.drop_index(op.f('ix_helm_chart_versions_chart_name'), table_name='helm_chart_versions')
    op.drop_table('helm_chart_versions')
    op.drop_index(op.f('ix_helm_chart_sources_name'), table_name='helm_chart_sources')
    op.drop_index(op.f('ix_helm_chart_sources_id'), table_name='helm_chart_sources')
    op.drop_table('helm_chart_sources')
