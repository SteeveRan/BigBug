"""extend_sync_schedule_for_universal_usage

Revision ID: 81d92eaba280
Revises: 0bb80e42a555
Create Date: 2026-06-10 19:34:54.902133+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '81d92eaba280'
down_revision: Union[str, None] = '0bb80e42a555'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add sync_type column with default for existing records
    op.add_column(
        "sync_schedules",
        sa.Column(
            "sync_type",
            sa.String(20),
            nullable=False,
            server_default="git_mirror",
        ),
    )

    # 2. Rename mirror_id → git_mirror_id and make nullable
    #    Also rename the auto-generated index
    op.execute(
        "ALTER INDEX ix_sync_schedules_mirror_id RENAME TO ix_sync_schedules_git_mirror_id"
    )
    op.alter_column(
        "sync_schedules",
        "mirror_id",
        new_column_name="git_mirror_id",
        existing_type=sa.Integer(),
        nullable=True,
    )

    # 3. Add docker_image_source_id and helm_chart_source_id
    op.add_column(
        "sync_schedules",
        sa.Column("docker_image_source_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "sync_schedules",
        sa.Column("helm_chart_source_id", sa.Integer(), nullable=True),
    )

    # 4. Create indexes
    op.create_index(
        "ix_sync_schedules_docker_image_source_id",
        "sync_schedules",
        ["docker_image_source_id"],
    )
    op.create_index(
        "ix_sync_schedules_helm_chart_source_id",
        "sync_schedules",
        ["helm_chart_source_id"],
    )
    op.create_index(
        "ix_sync_schedules_sync_type",
        "sync_schedules",
        ["sync_type"],
    )

    # 5. Add FK constraints
    op.create_foreign_key(
        "fk_sync_schedules_docker_image_source_id",
        "sync_schedules",
        "docker_image_sources",
        ["docker_image_source_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_sync_schedules_helm_chart_source_id",
        "sync_schedules",
        "helm_chart_sources",
        ["helm_chart_source_id"],
        ["id"],
        ondelete="CASCADE",
    )
    # Re-create FK for git_mirror_id (already existed for mirror_id)
    # The rename keeps the existing FK constraint; we just need to ensure it exists.
    # Alembic typically preserves the FK during rename. We can add if needed,
    # but since the column was renamed and the old FK referenced gitlab_mirrors.id,
    # it should still be in place.

    # 6. Add CHECK constraint (only one FK set at a time)
    op.create_check_constraint(
        "chk_sync_schedule_only_one_fk",
        "sync_schedules",
        (
            "(git_mirror_id IS NOT NULL AND docker_image_source_id IS NULL "
            "AND helm_chart_source_id IS NULL) OR "
            "(git_mirror_id IS NULL AND docker_image_source_id IS NOT NULL "
            "AND helm_chart_source_id IS NULL) OR "
            "(git_mirror_id IS NULL AND docker_image_source_id IS NULL "
            "AND helm_chart_source_id IS NOT NULL)"
        ),
    )


def downgrade() -> None:
    # 1. Drop CHECK constraint
    op.drop_constraint(
        "chk_sync_schedule_only_one_fk",
        "sync_schedules",
        type_="check",
    )

    # 2. Drop FK constraints
    op.drop_constraint(
        "fk_sync_schedules_helm_chart_source_id",
        "sync_schedules",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_sync_schedules_docker_image_source_id",
        "sync_schedules",
        type_="foreignkey",
    )

    # 3. Drop new columns
    op.drop_index("ix_sync_schedules_helm_chart_source_id", table_name="sync_schedules")
    op.drop_column("sync_schedules", "helm_chart_source_id")
    op.drop_index("ix_sync_schedules_docker_image_source_id", table_name="sync_schedules")
    op.drop_column("sync_schedules", "docker_image_source_id")

    # 4. Rename git_mirror_id → mirror_id and make non-nullable
    op.alter_column(
        "sync_schedules",
        "git_mirror_id",
        new_column_name="mirror_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.execute(
        "ALTER INDEX ix_sync_schedules_git_mirror_id RENAME TO ix_sync_schedules_mirror_id"
    )

    # 5. Drop sync_type column and index
    op.drop_index("ix_sync_schedules_sync_type", table_name="sync_schedules")
    op.drop_column("sync_schedules", "sync_type")
