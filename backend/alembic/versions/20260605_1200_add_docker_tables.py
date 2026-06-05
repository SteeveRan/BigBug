"""add Docker image source tables

Revision ID: add_docker_tables
Revises: 39774f94ac35
Create Date: 2026-06-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_docker_tables'
down_revision: Union[str, None] = '39774f94ac35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'docker_image_sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('registry_url', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('gitlab_project_id', sa.String(255), nullable=True),
        sa.Column('gitlab_project_url', sa.String(500), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status_flag', sa.Integer(), nullable=False, server_default='4'),
        sa.Column('status_text', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_index(op.f('ix_docker_image_sources_id'), 'docker_image_sources', ['id'])
    op.create_index(op.f('ix_docker_image_sources_name'), 'docker_image_sources', ['name'])

    op.create_table(
        'docker_image_tags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('image_name', sa.String(500), nullable=False),
        sa.Column('tag', sa.String(255), nullable=False),
        sa.Column('digest', sa.String(255), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=True),
        sa.Column('architectures', sa.Text(), nullable=True),
        sa.Column('status_flag', sa.Integer(), nullable=False, server_default='4'),
        sa.Column('status_text', sa.String(500), nullable=True),
        sa.Column('is_synced', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ['source_id'], ['docker_image_sources.id'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_docker_image_tags_id'), 'docker_image_tags', ['id'])
    op.create_index(op.f('ix_docker_image_tags_source_id'), 'docker_image_tags', ['source_id'])
    op.create_index(op.f('ix_docker_image_tags_image_name'), 'docker_image_tags', ['image_name'])

    op.create_table(
        'docker_sync_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('pipeline_id', sa.String(255), nullable=True),
        sa.Column('pipeline_url', sa.String(500), nullable=True),
        sa.Column('status_flag', sa.Integer(), nullable=False, server_default='4'),
        sa.Column('status_text', sa.String(500), nullable=True),
        sa.Column('log_output', sa.Text(), nullable=True),
        sa.Column('triggered_by', sa.String(100), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ['source_id'], ['docker_image_sources.id'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_docker_sync_logs_id'), 'docker_sync_logs', ['id'])
    op.create_index(op.f('ix_docker_sync_logs_source_id'), 'docker_sync_logs', ['source_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_docker_sync_logs_source_id'), table_name='docker_sync_logs')
    op.drop_index(op.f('ix_docker_sync_logs_id'), table_name='docker_sync_logs')
    op.drop_table('docker_sync_logs')
    op.drop_index(op.f('ix_docker_image_tags_image_name'), table_name='docker_image_tags')
    op.drop_index(op.f('ix_docker_image_tags_source_id'), table_name='docker_image_tags')
    op.drop_index(op.f('ix_docker_image_tags_id'), table_name='docker_image_tags')
    op.drop_table('docker_image_tags')
    op.drop_index(op.f('ix_docker_image_sources_name'), table_name='docker_image_sources')
    op.drop_index(op.f('ix_docker_image_sources_id'), table_name='docker_image_sources')
    op.drop_table('docker_image_sources')
