"""seed_gitlab_project_permissions

Revision ID: 5d4c3b2a1e0f
Revises: 6e8b9c0d1a2f
Create Date: 2026-08-20 00:43:00.000000+00:00

Seeds the 8 gitlab-project management permissions and links them to the
default roles (admin, operator, viewer) per
``plans/gitlab-project-management-spec.md`` §4 / ``permissions.md``.

Idempotent: inserts only missing permission rows and missing role→permission
links. ``downgrade()`` removes only the rows this migration owns.
"""
from datetime import UTC, datetime
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5d4c3b2a1e0f"
down_revision: Union[str, None] = "6e8b9c0d1a2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PERMISSIONS: list[dict[str, str]] = [
    {"name": "gitlab_projects:read", "description": "list/get gitlab projects (own + team + public)"},
    {"name": "gitlab_projects:write", "description": "create/update gitlab projects and push files"},
    {"name": "gitlab_projects:delete", "description": "soft/hard delete gitlab projects"},
    {"name": "gitlab_projects:read_all", "description": "access all private gitlab projects (admin marker)"},
    {"name": "components:read", "description": "list/get gitlab components"},
    {"name": "components:write", "description": "create/update gitlab component registrations"},
    {"name": "components:delete", "description": "delete gitlab component registrations"},
    {"name": "components:push", "description": "push component content to a gitlab project (files+tag)"},
]

ADMIN_PERMISSIONS: list[str] = [p["name"] for p in PERMISSIONS]
OPERATOR_PERMISSIONS: list[str] = [
    "gitlab_projects:read",
    "gitlab_projects:write",
    "components:read",
    "components:write",
    "components:push",
]
VIEWER_PERMISSIONS: list[str] = [
    "gitlab_projects:read",
    "components:read",
]


def _seed_permissions(conn) -> None:
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

    # ── Resolve role ids ──────────────────────────────────────────────────
    roles_table = sa.table(
        "roles",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
    )
    role_rows = conn.execute(sa.select(roles_table.c.id, roles_table.c.name))
    role_map: dict[str, int] = {row.name: row.id for row in role_rows}

    # ── Build role→permission assignments ─────────────────────────────────
    assignments: list[dict[str, int]] = []

    def _add(role_name: str, perms: list[str]) -> None:
        role_id = role_map.get(role_name)
        if role_id is None:
            return
        for pname in perms:
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
    _seed_permissions(conn)


def downgrade() -> None:
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
