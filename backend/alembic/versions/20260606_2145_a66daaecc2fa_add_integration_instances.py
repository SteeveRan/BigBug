"""add_integration_instances

Revision ID: a66daaecc2fa
Revises: bde12d699ca4
Create Date: 2026-06-06 21:45:48.884092+00:00

Creates three tables for multi-instance integration support
(gitlab_instances, harbor_instances, github_instances) and seeds
the ``integrations:manage`` permission assigned to the admin role.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a66daaecc2fa"
down_revision: Union[str, None] = "bde12d699ca4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── New permission for this feature ─────────────────────────────────────
INTEGRATIONS_PERMISSION = {
    "name": "integrations:manage",
    "description": "Управление инстансами интеграций (GitLab, Harbor, GitHub)",
}


def _seed_permission() -> None:
    """Insert ``integrations:manage`` and assign it to the admin role."""
    conn = op.get_bind()

    # ── Insert the permission ─────────────────────────────────────────
    permissions_table = sa.table(
        "permissions",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
    )

    # Check if permission already exists (idempotent)
    existing = conn.execute(
        sa.select(permissions_table.c.id).where(
            permissions_table.c.name == INTEGRATIONS_PERMISSION["name"]
        )
    ).first()

    if existing is None:
        op.bulk_insert(permissions_table, [INTEGRATIONS_PERMISSION])

    # ── Look up permission id ─────────────────────────────────────────
    perm_result = conn.execute(
        sa.select(permissions_table.c.id, permissions_table.c.name).where(
            permissions_table.c.name == INTEGRATIONS_PERMISSION["name"]
        )
    )
    perm = perm_result.first()
    if perm is None:
        return  # should not happen

    # ── Look up admin role id ─────────────────────────────────────────
    roles_table = sa.table(
        "roles",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
    )
    admin_result = conn.execute(
        sa.select(roles_table.c.id).where(roles_table.c.name == "admin")
    )
    admin = admin_result.first()
    if admin is None:
        return  # no admin role yet

    # ── Assign permission to admin role ───────────────────────────────
    role_permissions_table = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Integer),
        sa.column("permission_id", sa.Integer),
    )
    # Check if already assigned
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


def _unseed_permission() -> None:
    """Remove ``integrations:manage`` from role_permissions and permissions."""
    conn = op.get_bind()

    permissions_table = sa.table(
        "permissions",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
    )
    perm_result = conn.execute(
        sa.select(permissions_table.c.id).where(
            permissions_table.c.name == INTEGRATIONS_PERMISSION["name"]
        )
    ).first()
    if perm_result is None:
        return

    # Remove role assignments first
    role_permissions_table = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Integer),
        sa.column("permission_id", sa.Integer),
    )
    op.execute(
        role_permissions_table.delete().where(
            role_permissions_table.c.permission_id == perm_result.id
        )
    )
    # Remove the permission itself
    op.execute(
        permissions_table.delete().where(
            permissions_table.c.id == perm_result.id
        )
    )


def upgrade() -> None:
    # ── gitlab_instances ──────────────────────────────────────────────
    op.create_table(
        "gitlab_instances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.String(512), nullable=False),
        sa.Column("token", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status_flag", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status_text", sa.String(255), nullable=False, server_default="OK"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_gitlab_instances_id"), "gitlab_instances", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_gitlab_instances_name"),
        "gitlab_instances",
        ["name"],
        unique=True,
    )

    # ── harbor_instances ──────────────────────────────────────────────
    op.create_table(
        "harbor_instances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.String(512), nullable=False),
        sa.Column("username", sa.String(255), nullable=False),
        sa.Column("password", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status_flag", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status_text", sa.String(255), nullable=False, server_default="OK"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_harbor_instances_id"), "harbor_instances", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_harbor_instances_name"),
        "harbor_instances",
        ["name"],
        unique=True,
    )

    # ── github_instances ──────────────────────────────────────────────
    op.create_table(
        "github_instances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("token", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status_flag", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status_text", sa.String(255), nullable=False, server_default="OK"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_github_instances_id"), "github_instances", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_github_instances_name"),
        "github_instances",
        ["name"],
        unique=True,
    )

    # ── Seed integrations:manage permission ────────────────────────
    _seed_permission()


def downgrade() -> None:
    # ── Remove integrations:manage permission ──────────────────────
    _unseed_permission()

    # ── Drop tables ───────────────────────────────────────────────────
    op.drop_index(op.f("ix_github_instances_name"), table_name="github_instances")
    op.drop_index(op.f("ix_github_instances_id"), table_name="github_instances")
    op.drop_table("github_instances")

    op.drop_index(op.f("ix_harbor_instances_name"), table_name="harbor_instances")
    op.drop_index(op.f("ix_harbor_instances_id"), table_name="harbor_instances")
    op.drop_table("harbor_instances")

    op.drop_index(op.f("ix_gitlab_instances_name"), table_name="gitlab_instances")
    op.drop_index(op.f("ix_gitlab_instances_id"), table_name="gitlab_instances")
    op.drop_table("gitlab_instances")
