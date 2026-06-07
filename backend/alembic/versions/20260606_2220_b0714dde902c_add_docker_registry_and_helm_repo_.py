"""add_docker_registry_and_helm_repo_instances

Revision ID: b0714dde902c
Revises: a66daaecc2fa
Create Date: 2026-06-06 22:20:16.318694+00:00

Creates two tables for managed Docker Registry and Helm Repository
instances, plus seeds ``docker_registry:manage`` and
``helm_repository:manage`` permissions assigned to the admin role.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b0714dde902c"
down_revision: Union[str, None] = "a66daaecc2fa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── New permissions for this feature ─────────────────────────────────────
PERMISSIONS = [
    {
        "name": "docker_registry:manage",
        "description": "Управление инстансами Docker Registry",
    },
    {
        "name": "helm_repository:manage",
        "description": "Управление инстансами Helm Repository",
    },
]


def _seed_permissions() -> None:
    """Insert ``docker_registry:manage`` and ``helm_repository:manage``
    and assign them to the admin role."""
    conn = op.get_bind()

    permissions_table = sa.table(
        "permissions",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
    )
    roles_table = sa.table(
        "roles",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
    )
    role_permissions_table = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Integer),
        sa.column("permission_id", sa.Integer),
    )

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


def _unseed_permissions() -> None:
    """Remove the two permissions from role_permissions and permissions."""
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

    for perm_data in PERMISSIONS:
        perm_result = conn.execute(
            sa.select(permissions_table.c.id).where(
                permissions_table.c.name == perm_data["name"]
            )
        ).first()
        if perm_result is None:
            continue

        # Remove role assignments first
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
    # ── docker_registry_instances ─────────────────────────────────────────
    op.create_table(
        "docker_registry_instances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("password", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("verify_ssl", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
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
        op.f("ix_docker_registry_instances_id"),
        "docker_registry_instances",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_docker_registry_instances_name"),
        "docker_registry_instances",
        ["name"],
        unique=True,
    )

    # ── helm_repository_instances ─────────────────────────────────────────
    op.create_table(
        "helm_repository_instances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("password", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("verify_ssl", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
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
        op.f("ix_helm_repository_instances_id"),
        "helm_repository_instances",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_helm_repository_instances_name"),
        "helm_repository_instances",
        ["name"],
        unique=True,
    )

    # ── Seed permissions ─────────────────────────────────────────────────
    _seed_permissions()


def downgrade() -> None:
    # ── Remove permissions ─────────────────────────────────────────────
    _unseed_permissions()

    # ── Drop tables ───────────────────────────────────────────────────
    op.drop_index(
        op.f("ix_helm_repository_instances_name"),
        table_name="helm_repository_instances",
    )
    op.drop_index(
        op.f("ix_helm_repository_instances_id"),
        table_name="helm_repository_instances",
    )
    op.drop_table("helm_repository_instances")

    op.drop_index(
        op.f("ix_docker_registry_instances_name"),
        table_name="docker_registry_instances",
    )
    op.drop_index(
        op.f("ix_docker_registry_instances_id"),
        table_name="docker_registry_instances",
    )
    op.drop_table("docker_registry_instances")
