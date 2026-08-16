"""add_new_permissions_pipelines_integrations_oidc_audit

Revision ID: 745f271b2faf
Revises: 2b26ce93a7b9
Create Date: 2026-06-08 17:29:19.564878+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '745f271b2faf'
down_revision: Union[str, None] = '2b26ce93a7b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── New permission definitions ───────────────────────────────────────────
# NOTE: pipelines:read already seeded by d1e2f3a4b5c6 (add_pipeline_runs_and_components)
NEW_PERMISSIONS = [
    # Pipelines (read already exists from earlier migration)
    {"name": "pipelines:write", "description": "Создание и запуск пайплайнов"},
    {"name": "pipelines:delete", "description": "Отмена и удаление пайплайнов"},
    # Integrations
    {"name": "integrations:read", "description": "Просмотр конфигураций интеграций"},
    {"name": "integrations:write", "description": "Управление интеграциями"},
    # OIDC
    {"name": "oidc:read", "description": "Просмотр OIDC/OAuth2 конфигурации"},
    {"name": "oidc:write", "description": "Управление OIDC/OAuth2 конфигурацией"},
    # Audit
    {"name": "audit:read", "description": "Просмотр аудит лога"},
]

# ── Role → new permission assignments ────────────────────────────────────

# Admin: all new permissions
ADMIN_NEW_PERMISSIONS = [p["name"] for p in NEW_PERMISSIONS]

# Operator: pipelines read/write (not delete), audit read
OPERATOR_NEW_PERMISSIONS = [
    "pipelines:read",
    "pipelines:write",
    "audit:read",
]

# Viewer: read-only for new resources
VIEWER_NEW_PERMISSIONS = [
    "pipelines:read",
    "integrations:read",
    "oidc:read",
    "audit:read",
]

# ── Additional changes to existing permissions ───────────────────────────
# Viewer gets users:read and roles:read (previously only Admin had them)
VIEWER_ADDITIONAL_PERMISSIONS = [
    "users:read",
    "roles:read",
]


def upgrade() -> None:
    conn = op.get_bind()

    # ── Insert new permissions (idempotent) ──────────────────────────
    permissions_table = sa.table(
        "permissions",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
    )

    # Filter out permissions that already exist in the DB
    new_perm_names = [p["name"] for p in NEW_PERMISSIONS]
    existing_result = conn.execute(
        sa.select(permissions_table.c.name).where(
            permissions_table.c.name.in_(new_perm_names)
        )
    )
    existing_names: set[str] = {row.name for row in existing_result}

    to_insert = [p for p in NEW_PERMISSIONS if p["name"] not in existing_names]
    if to_insert:
        op.bulk_insert(permissions_table, to_insert)

    # Build permission name → id map (ALL permissions, including new ones)
    perm_result = conn.execute(
        sa.select(permissions_table.c.id, permissions_table.c.name)
    )
    perm_map: dict[str, int] = {row.name: row.id for row in perm_result}

    # ── Look up existing roles ───────────────────────────────────────
    roles_table = sa.table(
        "roles", sa.column("id", sa.Integer), sa.column("name", sa.String)
    )
    role_result = conn.execute(
        sa.select(roles_table.c.id, roles_table.c.name)
    )
    role_map: dict[str, int] = {row.name: row.id for row in role_result}

    # ── Build role_permission assignments ────────────────────────────
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

    _add_assignments("admin", ADMIN_NEW_PERMISSIONS)
    _add_assignments("operator", OPERATOR_NEW_PERMISSIONS)
    _add_assignments("viewer", VIEWER_NEW_PERMISSIONS)
    _add_assignments("viewer", VIEWER_ADDITIONAL_PERMISSIONS)

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


def downgrade() -> None:
    conn = op.get_bind()

    permissions_table = sa.table(
        "permissions",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
    )
    roles_table = sa.table(
        "roles", sa.column("id", sa.Integer), sa.column("name", sa.String)
    )
    role_permissions_table = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Integer),
        sa.column("permission_id", sa.Integer),
    )

    # ── Collect IDs of new permissions ───────────────────────────────
    new_perm_names = [p["name"] for p in NEW_PERMISSIONS]
    new_perm_result = conn.execute(
        sa.select(permissions_table.c.id).where(
            permissions_table.c.name.in_(new_perm_names)
        )
    )
    new_perm_ids = [row.id for row in new_perm_result]

    # ── Remove role_permission entries for new permissions ───────────
    if new_perm_ids:
        op.execute(
            sa.delete(role_permissions_table).where(
                role_permissions_table.c.permission_id.in_(new_perm_ids)
            )
        )

    # ── Remove users:read and roles:read from viewer role ────────────
    viewer_role_id = conn.execute(
        sa.select(roles_table.c.id).where(roles_table.c.name == "viewer")
    ).scalar_one_or_none()

    if viewer_role_id is not None:
        extra_perm_result = conn.execute(
            sa.select(permissions_table.c.id).where(
                permissions_table.c.name.in_(VIEWER_ADDITIONAL_PERMISSIONS)
            )
        )
        extra_perm_ids = [row.id for row in extra_perm_result]

        if extra_perm_ids:
            op.execute(
                sa.delete(role_permissions_table).where(
                    sa.and_(
                        role_permissions_table.c.role_id == viewer_role_id,
                        role_permissions_table.c.permission_id.in_(extra_perm_ids),
                    )
                )
            )

    # ── Delete new permissions ───────────────────────────────────────
    if new_perm_ids:
        op.execute(
            sa.delete(permissions_table).where(
                permissions_table.c.id.in_(new_perm_ids)
            )
        )
