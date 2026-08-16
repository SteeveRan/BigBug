"""seed initial roles, permissions and role_permissions

Revision ID: a1b2c3d4e5f6
Revises: 37590bb4a2ec
Create Date: 2026-08-16 12:00:00.000000+00:00

Consolidates the RBAC seed that was previously spread across seven Alembic
revisions (bde12d699ca4, 745f271b2faf, b214fda62040, ce50f1e2d6af,
cafe1234abcd, 3446791956ce, 0cce18c6c867) and the Python lists in
``docker/seed_admin.py``.

Source of truth: ``plans/architecture/permissions.md`` (61 permissions) and
the role assignment matrix in its "Распределение по ролям" section, which
matches ``ADMIN_PERMISSIONS`` / ``OPERATOR_PERMISSIONS`` /
``VIEWER_PERMISSIONS`` in ``backend/docker/seed_admin.py``.

The migration is idempotent: it inserts only rows whose ``name`` is not
already present and skips role→permission links that already exist. The
downgrade removes the seeded rows in FK-safe order
(role_permissions → permissions → roles).

Legacy permissions (``integrations:*``, ``docker_registry:manage``,
``helm_repository:manage``, ``pipelines:manage``, ``credentials:use``) are
intentionally NOT re-inserted: they were deleted in Providers V3 phase 5.
Providers are seeded by ``scripts/seed_providers.py`` and the admin user by
``docker/seed_admin.py`` — neither is duplicated here.
"""

from datetime import UTC, datetime
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "37590bb4a2ec"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Permission definitions (canonical set, 61 permissions) ─────────────────

PERMISSIONS: list[dict[str, str]] = [
    # Mirrors (GitHub → GitLab)
    {"name": "mirrors:read", "description": "Просмотр mirrors"},
    {"name": "mirrors:write", "description": "Создание/изменение mirrors"},
    {"name": "mirrors:delete", "description": "Удаление mirrors"},
    {"name": "mirrors:sync", "description": "Запуск синхронизации"},
    {"name": "mirrors:import", "description": "Import repositories as mirrors"},
    {"name": "mirrors:integrity_check", "description": "Run mirror integrity checks"},
    {"name": "mirrors:manage_orphaned", "description": "Manage orphaned mirrors"},
    # Projects (GitHub орги/проекты)
    {"name": "projects:read", "description": "Просмотр проектов"},
    {"name": "projects:write", "description": "Создание/изменение проектов"},
    {"name": "projects:delete", "description": "Удаление проектов"},
    # Source Groups
    {"name": "source_groups:read", "description": "View source providers, groups, and repositories"},
    {"name": "source_groups:write", "description": "Create and update source groups"},
    {"name": "source_groups:refresh", "description": "Trigger source group repository refresh"},
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
    # Pipelines
    {"name": "pipelines:read", "description": "Просмотр запусков, компонентов и конфигураций"},
    {"name": "pipelines:write", "description": "Создание и запуск пайплайнов"},
    {"name": "pipelines:delete", "description": "Отмена и удаление пайплайнов"},
    # Sync Groups
    {"name": "sync_groups:read", "description": "View sync groups and their mirrors"},
    {"name": "sync_groups:write", "description": "Create and update sync groups"},
    {"name": "sync_groups:delete", "description": "Delete sync groups"},
    # Credentials
    {"name": "credentials:read", "description": "View credentials configuration"},
    {"name": "credentials:write", "description": "Создание/изменение/удаление/тест учётных данных"},
    # Reports
    {"name": "reports:read", "description": "View mirroring reports (duplicates, storage, status, syncs)"},
    # Users
    {"name": "users:read", "description": "Просмотр пользователей"},
    {"name": "users:write", "description": "Создание/изменение пользователей"},
    {"name": "users:delete", "description": "Удаление пользователей"},
    # Roles
    {"name": "roles:read", "description": "Просмотр ролей"},
    {"name": "roles:write", "description": "Создание/изменение ролей"},
    {"name": "roles:delete", "description": "Удаление ролей"},
    # System
    {"name": "system:config", "description": "Изменение конфигурации системы"},
    # OIDC
    {"name": "oidc:read", "description": "Просмотр OIDC/OAuth2 конфигурации"},
    {"name": "oidc:write", "description": "Управление OIDC/OAuth2 конфигурацией"},
    # Audit
    {"name": "audit:read", "description": "Просмотр аудит лога"},
    # Admin Panel
    {"name": "admin:panel:access", "description": "Access the Admin Panel (separate administration interface)"},
    # Providers (V3)
    {"name": "providers:read", "description": "Просмотр providers (public+system, private свои)"},
    {"name": "providers:write", "description": "Создание/изменение providers (public+свои private)"},
    {"name": "providers:delete", "description": "Удаление providers (public+свои private)"},
    {"name": "providers:use", "description": "Доменные действия с providers"},
    {"name": "providers:read_all", "description": "Просмотр всех private providers"},
    {"name": "providers_system:write", "description": "Управление system-категорией providers"},
    {"name": "providers:share", "description": "Share/unshare providers команде"},
    # Teams
    {"name": "teams:read", "description": "Просмотр команд"},
    {"name": "teams:write", "description": "Создание/изменение/удаление команд"},
    {"name": "teams:manage_members", "description": "Управление участниками команд"},
]

DEFAULT_ROLES: list[dict[str, str]] = [
    {"name": "admin", "description": "Administrator"},
    {"name": "operator", "description": "Operator"},
    {"name": "viewer", "description": "Viewer"},
]

# ── Role → permission assignments (source: permissions.md) ─────────────────

ADMIN_PERMISSIONS: list[str] = [p["name"] for p in PERMISSIONS]

OPERATOR_PERMISSIONS: list[str] = [
    "mirrors:read", "mirrors:write", "mirrors:sync", "mirrors:import", "mirrors:integrity_check",
    "projects:read", "projects:write",
    "helm:read", "helm:write", "helm:sync", "helm:index",
    "docker:read", "docker:write", "docker:sync", "docker:index",
    "gold_images:read", "gold_images:write", "gold_images:build",
    "app_images:read", "app_images:write", "app_images:build",
    "pipelines:read", "pipelines:write",
    "audit:read",
    "source_groups:read", "source_groups:write", "source_groups:refresh",
    "sync_groups:read", "sync_groups:write",
    "providers:read", "providers:write", "providers:use", "providers:share",
    "teams:read",
]

VIEWER_PERMISSIONS: list[str] = [
    "mirrors:read",
    "projects:read",
    "helm:read",
    "docker:read",
    "gold_images:read",
    "app_images:read",
    "pipelines:read",
    "users:read",
    "roles:read",
    "oidc:read",
    "audit:read",
    "source_groups:read",
    "sync_groups:read",
    "providers:read",
    "teams:read",
]


def _seed_roles(conn) -> dict[str, int]:
    """Idempotently insert default admin/operator/viewer roles."""
    roles_table = sa.table(
        "roles",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("is_custom", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )

    existing = conn.execute(
        sa.select(roles_table.c.name).where(
            roles_table.c.name.in_([r["name"] for r in DEFAULT_ROLES])
        )
    )
    existing_names: set[str] = {row.name for row in existing}

    new_roles = [
        {
            "name": r["name"],
            "description": r["description"],
            "is_custom": False,
            "created_at": datetime.now(UTC),
        }
        for r in DEFAULT_ROLES
        if r["name"] not in existing_names
    ]
    if new_roles:
        op.bulk_insert(roles_table, new_roles)

    role_rows = conn.execute(sa.select(roles_table.c.id, roles_table.c.name))
    return {row.name: row.id for row in role_rows}


def _seed_permissions(conn, role_map: dict[str, int]) -> None:
    """Idempotently insert permissions and link them to the default roles."""
    permissions_table = sa.table(
        "permissions",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
    )
    role_permissions_table = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Integer),
        sa.column("permission_id", sa.Integer),
    )

    # ── Insert missing permission definitions ─────────────────────────────
    perm_names = [p["name"] for p in PERMISSIONS]
    existing = conn.execute(
        sa.select(permissions_table.c.name).where(permissions_table.c.name.in_(perm_names))
    )
    existing_names: set[str] = {row.name for row in existing}

    to_insert = [p for p in PERMISSIONS if p["name"] not in existing_names]
    if to_insert:
        op.bulk_insert(permissions_table, to_insert)

    perm_rows = conn.execute(
        sa.select(permissions_table.c.id, permissions_table.c.name)
    )
    perm_map: dict[str, int] = {row.name: row.id for row in perm_rows}

    # ── Build role→permission assignments ─────────────────────────────────
    assignments: list[dict[str, int]] = []

    def _add(role_name: str, perm_names: list[str]) -> None:
        role_id = role_map.get(role_name)
        if role_id is None:
            return
        for pname in perm_names:
            pid = perm_map.get(pname)
            if pid is not None:
                assignments.append({"role_id": role_id, "permission_id": pid})

    _add("admin", ADMIN_PERMISSIONS)
    _add("operator", OPERATOR_PERMISSIONS)
    _add("viewer", VIEWER_PERMISSIONS)

    # ── Filter out already-existing links (idempotent) ────────────────────
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


def upgrade() -> None:
    conn = op.get_bind()
    role_map = _seed_roles(conn)
    _seed_permissions(conn, role_map)


def downgrade() -> None:
    """Remove seeded role_permissions, permissions and default roles.

    role_permissions has ON DELETE CASCADE on both FKs, but we delete it
    explicitly to keep the rollback order unambiguous.
    """
    conn = op.get_bind()

    permissions_table = sa.table(
        "permissions",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
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

    # Delete only the rows this migration owns (the canonical permission set
    # and the default built-in roles), not any user-created permissions/roles.
    perm_names = [p["name"] for p in PERMISSIONS]
    perm_ids = [
        row.id
        for row in conn.execute(
            sa.select(permissions_table.c.id).where(
                permissions_table.c.name.in_(perm_names)
            )
        )
    ]
    if perm_ids:
        conn.execute(
            role_permissions_table.delete().where(
                role_permissions_table.c.permission_id.in_(perm_ids)
            )
        )
        conn.execute(
            permissions_table.delete().where(permissions_table.c.id.in_(perm_ids))
        )

    role_names = [r["name"] for r in DEFAULT_ROLES]
    role_ids = [
        row.id
        for row in conn.execute(
            sa.select(roles_table.c.id).where(roles_table.c.name.in_(role_names))
        )
    ]
    if role_ids:
        conn.execute(
            role_permissions_table.delete().where(
                role_permissions_table.c.role_id.in_(role_ids)
            )
        )
        conn.execute(roles_table.delete().where(roles_table.c.id.in_(role_ids)))
