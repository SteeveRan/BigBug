"""add_rbac_permissions

Revision ID: bde12d699ca4
Revises: add_docker_tables
Create Date: 2026-06-06 19:32:58.397950+00:00

"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bde12d699ca4'
down_revision: Union[str, None] = 'add_docker_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Permission definitions ───────────────────────────────────────────────
PERMISSIONS = [
    # Mirrors (GitHub → GitLab)
    {"name": "mirrors:read", "description": "Просмотр mirrors"},
    {"name": "mirrors:write", "description": "Создание/изменение mirrors"},
    {"name": "mirrors:delete", "description": "Удаление mirrors"},
    {"name": "mirrors:sync", "description": "Запуск синхронизации"},
    # Projects (GitHub орги/проекты)
    {"name": "projects:read", "description": "Просмотр проектов"},
    {"name": "projects:write", "description": "Создание/изменение проектов"},
    {"name": "projects:delete", "description": "Удаление проектов"},
    # Helm Charts
    {"name": "helm:read", "description": "Просмотр Helm charts"},
    {"name": "helm:write", "description": "Создание/изменение sources"},
    {"name": "helm:delete", "description": "Удаление sources"},
    {"name": "helm:sync", "description": "Запуск синхронизации"},
    {"name": "helm:index", "description": "Индексация index.yaml"},
    # Docker Images
    {"name": "docker:read", "description": "Просмотр Docker images"},
    {"name": "docker:write", "description": "Создание/изменение sources"},
    {"name": "docker:delete", "description": "Удаление sources"},
    {"name": "docker:sync", "description": "Запуск синхронизации"},
    {"name": "docker:index", "description": "Индексация через Registry API"},
    # Gold Images (базовые OS/runtime)
    {"name": "gold_images:read", "description": "Просмотр Gold Images"},
    {"name": "gold_images:write", "description": "Создание/изменение"},
    {"name": "gold_images:delete", "description": "Удаление"},
    {"name": "gold_images:build", "description": "Запуск сборки"},
    # App Images (приложения)
    {"name": "app_images:read", "description": "Просмотр App Images"},
    {"name": "app_images:write", "description": "Создание/изменение"},
    {"name": "app_images:delete", "description": "Удаление"},
    {"name": "app_images:build", "description": "Запуск сборки"},
    # Admin (управление пользователями/ролями)
    {"name": "users:read", "description": "Просмотр пользователей"},
    {"name": "users:write", "description": "Создание/изменение пользователей"},
    {"name": "users:delete", "description": "Удаление пользователей"},
    {"name": "roles:read", "description": "Просмотр ролей"},
    {"name": "roles:write", "description": "Создание/изменение ролей"},
    {"name": "roles:delete", "description": "Удаление ролей"},
    # System
    {"name": "system:config", "description": "Изменение конфигурации системы"},
]

# ── Default role → permission assignments ────────────────────────────────

# Admin: all permissions
ADMIN_PERMISSIONS = [p["name"] for p in PERMISSIONS]

# Operator: read + actions, no delete, no admin
OPERATOR_PERMISSIONS = [
    "mirrors:read", "mirrors:write", "mirrors:sync",
    "projects:read", "projects:write",
    "helm:read", "helm:write", "helm:sync", "helm:index",
    "docker:read", "docker:write", "docker:sync", "docker:index",
    "gold_images:read", "gold_images:write", "gold_images:build",
    "app_images:read", "app_images:write", "app_images:build",
]

# Viewer: read-only
VIEWER_PERMISSIONS = [
    "mirrors:read",
    "projects:read",
    "helm:read",
    "docker:read",
    "gold_images:read",
    "app_images:read",
]


DEFAULT_ROLES = [
    {"name": "admin", "description": "Administrator"},
    {"name": "operator", "description": "Operator"},
    {"name": "viewer", "description": "Viewer"},
]


def _seed_default_roles() -> None:
    """Idempotently insert default admin/operator/viewer roles."""
    conn = op.get_bind()
    roles_table = sa.table(
        "roles",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("is_custom", sa.Boolean),
        sa.column("created_at", sa.DateTime),
    )

    # Fetch existing role names so we don't try to re-insert them.
    existing_result = conn.execute(
        sa.select(roles_table.c.name).where(
            roles_table.c.name.in_([r["name"] for r in DEFAULT_ROLES])
        )
    )
    existing_names: set[str] = {row.name for row in existing_result}

    new_roles = [
        {
            "name": r["name"],
            "description": r["description"],
            "is_custom": False,
            "created_at": datetime.utcnow(),
        }
        for r in DEFAULT_ROLES
        if r["name"] not in existing_names
    ]
    if new_roles:
        op.bulk_insert(roles_table, new_roles)


def _seed_permissions() -> None:
    """Insert all permission definitions and role assignments."""
    conn = op.get_bind()

    # ── Insert permissions (idempotent) ──────────────────────────────────
    permissions_table = sa.table(
        "permissions",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
    )

    # Filter out permissions that already exist in the DB
    perm_names_to_insert = [p["name"] for p in PERMISSIONS]
    existing_result = conn.execute(
        sa.select(permissions_table.c.name).where(
            permissions_table.c.name.in_(perm_names_to_insert)
        )
    )
    existing_names: set[str] = {row.name for row in existing_result}

    to_insert = [p for p in PERMISSIONS if p["name"] not in existing_names]
    if to_insert:
        op.bulk_insert(permissions_table, to_insert)

    # Build permission name → id map
    perm_result = conn.execute(
        sa.select(permissions_table.c.id, permissions_table.c.name)
    )
    perm_map: dict[str, int] = {row.name: row.id for row in perm_result}

    # ── Look up existing roles ───────────────────────────────────────────
    roles_table = sa.table(
        "roles", sa.column("id", sa.Integer), sa.column("name", sa.String)
    )
    role_result = conn.execute(
        sa.select(roles_table.c.id, roles_table.c.name)
    )
    role_map: dict[str, int] = {row.name: row.id for row in role_result}

    # ── Build role_permission assignments ────────────────────────────────
    role_permissions_table = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Integer),
        sa.column("permission_id", sa.Integer),
    )

    assignments: list[dict[str, int]] = []

    def _add_assignments(role_name: str, perm_names: list[str]) -> None:
        role_id = role_map.get(role_name)
        if role_id is None:
            return  # role not yet seeded; skip gracefully
        for pname in perm_names:
            pid = perm_map.get(pname)
            if pid is not None:
                assignments.append({"role_id": role_id, "permission_id": pid})

    _add_assignments("admin", ADMIN_PERMISSIONS)
    _add_assignments("operator", OPERATOR_PERMISSIONS)
    _add_assignments("viewer", VIEWER_PERMISSIONS)

    # Filter out assignments that already exist (idempotent)
    if assignments:
        existing_rp = conn.execute(
            sa.select(
                role_permissions_table.c.role_id,
                role_permissions_table.c.permission_id,
            )
        )
        existing_rp_set = {(row.role_id, row.permission_id) for row in existing_rp}
        to_assign = [
            a for a in assignments
            if (a["role_id"], a["permission_id"]) not in existing_rp_set
        ]
        if to_assign:
            op.bulk_insert(role_permissions_table, to_assign)


def _unseed_permissions() -> None:
    """Remove all rows from role_permissions and permissions."""
    op.execute("DELETE FROM role_permissions")
    op.execute("DELETE FROM permissions")


def upgrade() -> None:
    # ### CREATE permissions table ###
    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_permissions_id"), "permissions", ["id"], unique=False)
    op.create_index(
        op.f("ix_permissions_name"), "permissions", ["name"], unique=True
    )

    # ### CREATE role_permissions table ###
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["permission_id"], ["permissions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
    )

    # ### ALTER roles table: add is_custom ###
    op.add_column(
        "roles",
        sa.Column(
            "is_custom",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # ### ALTER roles table: add created_by_user_id ###
    op.add_column(
        "roles",
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_roles_created_by_user_id_users",
        "roles",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ### SEED default roles + permissions + default role assignments ###
    _seed_default_roles()
    _seed_permissions()


def downgrade() -> None:
    # ### UNSEED permissions ###
    _unseed_permissions()

    # ### DROP FK + columns from roles ###
    op.drop_constraint(
        "fk_roles_created_by_user_id_users", "roles", type_="foreignkey"
    )
    op.drop_column("roles", "created_by_user_id")
    op.drop_column("roles", "is_custom")

    # ### DROP role_permissions table ###
    op.drop_table("role_permissions")

    # ### DROP indexes and permissions table ###
    op.drop_index(op.f("ix_permissions_name"), table_name="permissions")
    op.drop_index(op.f("ix_permissions_id"), table_name="permissions")
    op.drop_table("permissions")
