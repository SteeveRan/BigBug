"""link_components_pipelines_to_gitlab_projects

Revision ID: 6e8b9c0d1a2f
Revises: 7f3a2c1b4d5e
Create Date: 2026-08-20 00:42:00.000000+00:00

Adds a nullable ``gitlab_project_id`` FK (SET NULL) to ``gitlab_components``
and ``pipelines`` with the corresponding indexes. No backfill is required:
existing components/pipelines remain NULL (legacy mode).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "6e8b9c0d1a2f"
down_revision: Union[str, None] = "7f3a2c1b4d5e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "gitlab_components",
        sa.Column("gitlab_project_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_gitlab_components_gitlab_project_id",
        "gitlab_components",
        "gitlab_projects",
        ["gitlab_project_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_gitlab_components_gitlab_project_id"),
        "gitlab_components",
        ["gitlab_project_id"],
        unique=False,
    )

    op.add_column(
        "pipelines",
        sa.Column("gitlab_project_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_pipelines_gitlab_project_id",
        "pipelines",
        "gitlab_projects",
        ["gitlab_project_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_pipelines_gitlab_project_id"),
        "pipelines",
        ["gitlab_project_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_pipelines_gitlab_project_id"), table_name="pipelines"
    )
    op.drop_constraint(
        "fk_pipelines_gitlab_project_id", "pipelines", type_="foreignkey"
    )
    op.drop_column("pipelines", "gitlab_project_id")

    op.drop_index(
        op.f("ix_gitlab_components_gitlab_project_id"),
        table_name="gitlab_components",
    )
    op.drop_constraint(
        "fk_gitlab_components_gitlab_project_id",
        "gitlab_components",
        type_="foreignkey",
    )
    op.drop_column("gitlab_components", "gitlab_project_id")
