"""remove legacy permissions (phase 5)

Revision ID: b8d4e5f6a7c9
Revises: a4c1e9f0b7d3
Create Date: 2026-08-15 00:00:00.000000+00:00

Phase 5 of the unified Providers V3 refactoring (plans/features/providers-unified.md,
section 6.2). Deletes legacy permission definitions from both ``permissions``
and ``role_permissions`` (the latter is cleaned explicitly even though the FK
has ON DELETE CASCADE, so the downgrade has a precise rollback):

* ``credentials:use``      — internal provider logic; users never consume a
                             credential directly anymore
* ``integrations:read``    — replaced by ``providers:read``
* ``integrations:write``   — replaced by ``providers:write`` + ``providers_system:write``
* ``integrations:manage``  — legacy in DB, replaced by ``integrations:read/write``
* ``docker_registry:manage`` — legacy in DB
* ``helm_repository:manage`` — legacy in DB
* ``pipelines:manage``     — legacy in DB, replaced by ``pipelines:write`` + ``pipelines:delete``

``credentials:read`` is intentionally **kept** — it now gets actually enforced
by ``app/api/credentials.py`` (list/get).

Downgrade restores the permission definitions with their historical descriptions
(the source of truth for descriptions lives in the original seeding migrations).
Role→permission assignments are NOT reconstructed here: they were granted by
``docker/seed_admin.py`` and by the original seeding migrations, which is out of
scope for a data rollback of this revision.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8d4e5f6a7c9"
down_revision: str | None = "a4c1e9f0b7d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ── Legacy permissions removed by this revision ─────────────────────────────
# name → historical description (used to reconstruct definitions on downgrade).
_LEGACY_PERMISSIONS: dict[str, str] = {
    "credentials:use": "Use credentials in sync operations",
    "integrations:read": "Просмотр конфигураций интеграций",
    "integrations:write": "Управление интеграциями",
    "integrations:manage": "Управление инстансами интеграций (GitLab, Harbor, GitHub)",
    "docker_registry:manage": "Управление инстансами Docker Registry",
    "helm_repository:manage": "Управление инстансами Helm Repository",
    "pipelines:manage": "Trigger, cancel, retry pipelines and manage components",
}


def upgrade() -> None:
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

    names = list(_LEGACY_PERMISSIONS.keys())

    # Resolve permission IDs before deleting (order matters: role_permissions
    # references permissions, so clean the association rows first even though
    # the FK would cascade).
    result = conn.execute(
        sa.select(permissions_table.c.id).where(permissions_table.c.name.in_(names))
    )
    permission_ids = [row.id for row in result]

    if permission_ids:
        conn.execute(
            role_permissions_table.delete().where(
                role_permissions_table.c.permission_id.in_(permission_ids)
            )
        )

    conn.execute(permissions_table.delete().where(permissions_table.c.name.in_(names)))


def downgrade() -> None:
    conn = op.get_bind()

    permissions_table = sa.table(
        "permissions",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
    )

    # Restore only definitions that are not already present (idempotent).
    existing_result = conn.execute(
        sa.select(permissions_table.c.name).where(
            permissions_table.c.name.in_(list(_LEGACY_PERMISSIONS.keys()))
        )
    )
    existing_names = {row.name for row in existing_result}

    to_insert = [
        {"name": name, "description": desc}
        for name, desc in _LEGACY_PERMISSIONS.items()
        if name not in existing_names
    ]
    if to_insert:
        op.bulk_insert(permissions_table, to_insert)

    # NOTE: role→permission assignments are intentionally not restored. They were
    # granted by ``docker/seed_admin.py`` (runtime seed) and the original seeding
    # migrations, and are outside the scope of this data revision's rollback.
