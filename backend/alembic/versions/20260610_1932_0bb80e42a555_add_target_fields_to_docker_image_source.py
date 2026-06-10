"""add_target_fields_to_docker_image_source

Revision ID: 0bb80e42a555
Revises: 745f271b2faf
Create Date: 2026-06-10 19:32:44.313316+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0bb80e42a555'
down_revision: Union[str, None] = '745f271b2faf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "docker_image_sources",
        sa.Column("target_registry_url", sa.String(500), nullable=True),
    )
    op.add_column(
        "docker_image_sources",
        sa.Column("target_project", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("docker_image_sources", "target_project")
    op.drop_column("docker_image_sources", "target_registry_url")
