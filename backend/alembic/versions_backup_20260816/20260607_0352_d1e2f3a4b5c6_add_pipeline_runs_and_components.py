"""add_pipeline_runs_and_components

Revision ID: d1e2f3a4b5c6
Revises: c7d8e9f0a1b2
Create Date: 2026-06-07 03:52:00.000000+00:00

Creates ``pipeline_runs`` and ``gitlab_components`` tables.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _seed_pipeline_permissions() -> None:
    """Insert ``pipelines:read`` and ``pipelines:manage`` permissions
    and assign them to the admin role if they don't exist yet."""

    permissions_table = sa.table(
        "permissions",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
    )
    role_permissions_table = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Integer),
        sa.column("permission_id", sa.Integer),
    )
    roles_table = sa.table(
        "roles",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
    )

    PERMISSIONS = [
        {"name": "pipelines:read", "description": "View pipeline runs and components"},
        {"name": "pipelines:manage", "description": "Trigger, cancel, retry pipelines and manage components"},
    ]

    conn = op.get_bind()

    # Look up admin role once
    admin_result = conn.execute(
        sa.select(roles_table.c.id).where(roles_table.c.name == "admin")
    )
    admin = admin_result.first()
    if admin is None:
        return  # no admin role yet

    for perm_data in PERMISSIONS:
        # ── Insert the permission (idempotent) ─────────────────────
        existing = conn.execute(
            sa.select(permissions_table.c.id).where(
                permissions_table.c.name == perm_data["name"]
            )
        ).first()

        if existing is None:
            op.bulk_insert(permissions_table, [perm_data])

        # ── Look up permission id ──────────────────────────────────
        perm_result = conn.execute(
            sa.select(permissions_table.c.id, permissions_table.c.name).where(
                permissions_table.c.name == perm_data["name"]
            )
        )
        perm = perm_result.first()
        if perm is None:
            continue

        # ── Assign permission to admin role (idempotent) ───────────
        existing_assignment = conn.execute(
            sa.select(role_permissions_table).where(
                (role_permissions_table.c.role_id == admin.id)
                & (role_permissions_table.c.permission_id == perm.id)
            )
        ).first()
        if existing_assignment is None:
            op.bulk_insert(
                role_permissions_table,
                [{"role_id": admin.id, "permission_id": perm.id}],
            )


def _unseed_pipeline_permissions() -> None:
    """Remove the two pipeline permissions from role_permissions and permissions."""
    conn = op.get_bind()

    permissions_table = sa.table(
        "permissions",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
    )
    role_permissions_table = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Integer),
        sa.column("permission_id", sa.Integer),
    )

    for perm_name in ("pipelines:manage", "pipelines:read"):
        perm_result = conn.execute(
            sa.select(permissions_table.c.id).where(
                permissions_table.c.name == perm_name
            )
        )
        perm = perm_result.first()
        if perm is None:
            continue

        conn.execute(
            sa.delete(role_permissions_table).where(
                role_permissions_table.c.permission_id == perm.id
            )
        )
        conn.execute(
            sa.delete(permissions_table).where(
                permissions_table.c.id == perm.id
            )
        )


def upgrade() -> None:
    # ── pipeline_runs ─────────────────────────────────────────────────
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "gitlab_instance_id",
            sa.Integer(),
            sa.ForeignKey("gitlab_instances.id"),
            nullable=False,
        ),
        sa.Column("gitlab_project_id", sa.Integer(), nullable=False),
        sa.Column("gitlab_pipeline_id", sa.Integer(), nullable=True),
        sa.Column(
            "triggered_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "trigger_type",
            sa.String(),
            nullable=False,
            server_default="manual",
        ),
        sa.Column("ref", sa.String(), nullable=False),
        sa.Column(
            "variables",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "status_flag",
            sa.Integer(),
            nullable=False,
            server_default="4",
        ),
        sa.Column(
            "status_text",
            sa.String(255),
            nullable=False,
            server_default="Pending",
        ),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("web_url", sa.String(1024), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_pipeline_runs_id"), "pipeline_runs", ["id"], unique=False
    )

    # ── gitlab_components ─────────────────────────────────────────────
    op.create_table(
        "gitlab_components",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1024), nullable=True),
        sa.Column(
            "gitlab_instance_id",
            sa.Integer(),
            sa.ForeignKey("gitlab_instances.id"),
            nullable=False,
        ),
        sa.Column("project_path", sa.String(512), nullable=False),
        sa.Column("component_path", sa.String(512), nullable=False),
        sa.Column("version", sa.String(64), nullable=True),
        sa.Column(
            "inputs_schema",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_gitlab_components_id"),
        "gitlab_components",
        ["id"],
        unique=False,
    )

    # ── Seed permissions ────────────────────────────────────────────
    _seed_pipeline_permissions()


def downgrade() -> None:
    _unseed_pipeline_permissions()

    op.drop_index(
        op.f("ix_gitlab_components_id"), table_name="gitlab_components"
    )
    op.drop_table("gitlab_components")
    op.drop_index(op.f("ix_pipeline_runs_id"), table_name="pipeline_runs")
    op.drop_table("pipeline_runs")
