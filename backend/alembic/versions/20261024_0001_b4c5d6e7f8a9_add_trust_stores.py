"""add_trust_stores

Revision ID: b4c5d6e7f8a9
Revises: a9f8e7d6c5b4
Create Date: 2026-10-24 00:00:00.000000+00:00

Adds the Trust Store entities (ADR-0037, issue #89):

* ``trust_stores`` — named CA bundles, name unique among live rows
  (partial unique index, mirrors ``uq_resource_providers_name``).
* ``trust_store_certificates`` — PEM certificates of a store,
  unique (trust_store_id, name).
* ``resource_providers.trust_store_id`` — nullable FK, ondelete=RESTRICT.
* Seeds ``trust_stores:read`` (admin, operator) and ``trust_stores:write``
  (admin) — idempotent, pattern of ``seed_gitlab_project_permissions``.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, None] = "a9f8e7d6c5b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PERMISSIONS: list[dict[str, str]] = [
    {
        "name": "trust_stores:read",
        "description": "Просмотр трастсторов и их сертификатов",
    },
    {
        "name": "trust_stores:write",
        "description": "Создание/изменение/удаление трастсторов и сертификатов",
    },
]

ADMIN_PERMISSIONS: list[str] = [p["name"] for p in PERMISSIONS]
OPERATOR_PERMISSIONS: list[str] = ["trust_stores:read"]
VIEWER_PERMISSIONS: list[str] = []


def upgrade() -> None:
    op.create_table(
        "trust_stores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_trust_stores_name",
        "trust_stores",
        ["name"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
        sqlite_where=sa.text("is_deleted = false"),
    )
    op.create_index(op.f("ix_trust_stores_id"), "trust_stores", ["id"], unique=False)

    op.create_table(
        "trust_store_certificates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trust_store_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("pem", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["trust_store_id"],
            ["trust_stores.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_trust_store_certificates_store",
        "trust_store_certificates",
        ["trust_store_id"],
        unique=False,
    )
    op.create_index(op.f("ix_trust_store_certificates_id"), "trust_store_certificates", ["id"], unique=False)
    op.create_index(
        "uq_trust_store_certificates_name",
        "trust_store_certificates",
        ["trust_store_id", "name"],
        unique=True,
    )

    op.add_column(
        "resource_providers",
        sa.Column("trust_store_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_resource_providers_trust_store_id",
        "resource_providers",
        "trust_stores",
        ["trust_store_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    _seed_permissions(op.get_bind())


def _seed_permissions(conn) -> None:
    """Idempotently insert trust-store permissions and link them to roles."""
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

    perm_names = [p["name"] for p in PERMISSIONS]
    existing = conn.execute(
        sa.select(permissions_table.c.name).where(permissions_table.c.name.in_(perm_names))
    )
    existing_names: set[str] = {row.name for row in existing}

    to_insert = [p for p in PERMISSIONS if p["name"] not in existing_names]
    if to_insert:
        op.bulk_insert(permissions_table, to_insert)

    perm_rows = conn.execute(sa.select(permissions_table.c.id, permissions_table.c.name))
    perm_map: dict[str, int] = {row.name: row.id for row in perm_rows}

    roles_table = sa.table(
        "roles",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
    )
    role_rows = conn.execute(sa.select(roles_table.c.id, roles_table.c.name))
    role_map: dict[str, int] = {row.name: row.id for row in role_rows}

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

    existing_rp = conn.execute(
        sa.select(
            role_permissions_table.c.role_id,
            role_permissions_table.c.permission_id,
        )
    )
    existing_rp_set = {(row.role_id, row.permission_id) for row in existing_rp}
    to_assign = [a for a in assignments if (a["role_id"], a["permission_id"]) not in existing_rp_set]
    if to_assign:
        op.bulk_insert(role_permissions_table, to_assign)


def downgrade() -> None:
    conn = op.get_bind()

    # ── Seed removal (FK-safe order: links → permissions) ─────────────────
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
            sa.select(permissions_table.c.id).where(permissions_table.c.name.in_(perm_names))
        )
    ]
    if perm_ids:
        conn.execute(
            role_permissions_table.delete().where(
                role_permissions_table.c.permission_id.in_(perm_ids)
            )
        )
        conn.execute(permissions_table.delete().where(permissions_table.c.id.in_(perm_ids)))

    # ── Schema removal ────────────────────────────────────────────────────
    op.drop_constraint(
        "fk_resource_providers_trust_store_id",
        "resource_providers",
        type_="foreignkey",
    )
    op.drop_column("resource_providers", "trust_store_id")
    op.drop_index("uq_trust_store_certificates_name", "trust_store_certificates")
    op.drop_index(op.f("ix_trust_store_certificates_id"), "trust_store_certificates")
    op.drop_index("ix_trust_store_certificates_store", "trust_store_certificates")
    op.drop_table("trust_store_certificates")
    op.drop_index(op.f("ix_trust_stores_id"), "trust_stores")
    op.drop_index("uq_trust_stores_name", "trust_stores")
    op.drop_table("trust_stores")
