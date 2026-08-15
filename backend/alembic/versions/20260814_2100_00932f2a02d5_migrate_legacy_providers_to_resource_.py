"""migrate legacy providers to resource_providers

Revision ID: 00932f2a02d5
Revises: 78cd1e526b72
Create Date: 2026-08-14 21:00:37.782230+00:00

Phase 3 of the unified Providers V3 refactoring (plans/features/providers-unified.md):

* data-migrates the five legacy instance tables + ``source_providers`` into
  ``resource_providers`` without loss (section 7, phase 3; mapping 11.3.4);
* moves instance secrets into new ``credentials`` rows following the
  try-decrypt → copy-ciphertext-as-is / encrypt-plaintext order (11.1.3);
* relinks consumers to the new providers via additive ``provider_id`` /
  ``target_provider_id`` columns (1.4).

Legacy tables and their columns are intentionally NOT dropped here — that is
phase 7. The old FK columns (``source_repositories.source_provider_id``,
``pipelines.gitlab_instance_id``, ``docker_image_sources.registry_instance_id``
and ``target_registry_url``) are left untouched for rollback / read-through.

Naming / downgrade assumptions
------------------------------

* Provider ``name`` slugs are namespaced ``legacy-{table}-{legacy.name}`` (and
  ``legacy-source-{id}`` for ``source_providers``, which have no ``name``
  column). The prefix guarantees global uniqueness across the merged tables,
  avoids collisions with future seed slugs and gives a deterministic downgrade
  marker (``name LIKE 'legacy-%'``).
* Migrated credentials are named ``migrated-{table}-{instance.name}`` (11.1.3)
  and are removed on downgrade via ``name LIKE 'migrated-%'``.
* Legacy instance rows have no ``owner_user_id`` (the column never existed on
  those tables), yet ``category='private'`` requires an owner (CHECK
  ``ck_resource_providers_private_owner``). Private rows are therefore assigned
  to the platform admin user (the user holding the ``admin`` role). When no
  admin user exists yet (fresh DB — in which case there is no legacy data to
  migrate), the row degrades to ``public`` instead of failing the CHECK.
* Secrets never appear in logs; plaintext exists only in memory inside the
  fallback branch (11.1.3).
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.core.secrets import SecretEncryptionError, decrypt_secret, encrypt_secret

# revision identifiers, used by Alembic.
revision: str = "00932f2a02d5"
down_revision: str | None = "78cd1e526b72"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ── Mapping tables (single source of truth for this migration) ──────────────

# docker_registry_instances.RegistryProvider → resource_providers.subtype (11.3.4)
_REGISTRY_PROVIDER_TO_SUBTYPE = {
    "docker_hub": "docker_hub",
    "quay_io": "quay",
    "gcr": "gcr",
    "ecr": "ecr",
    "acr": "acr",
    "ghcr": "ghcr",
    "harbor": "harbor",
    "generic": "generic_registry",
}

# source_providers.ProviderType → resource_providers.subtype
_PROVIDER_TYPE_TO_SUBTYPE = {
    "github": "github",
    "gitlab": "gitlab",
    "generic": "generic_git",
}

# Credential ``provider`` label per legacy table (free-form String(50)).
_CREDENTIAL_PROVIDER = {
    "gitlab": "gitlab",
    "github": "github",
    "harbor": "harbor",
    "docker": "docker",
    "helm": "helm",
}


# ── Small helpers ───────────────────────────────────────────────────────────


def _norm_url(url: str | None) -> str:
    """Normalise a registry/repo URL for fuzzy matching.

    Strips scheme, lower-cases and removes trailing slashes. This is a
    deliberate simplification — legacy ``target_registry_url`` is an untyped
    string, so matching is best-effort (ponytail: O(1) heuristic; upgrade path
    is the typed ``target_provider_id`` this migration introduces).
    """
    value = (url or "").strip().lower().rstrip("/")
    for prefix in ("https://", "http://"):
        if value.startswith(prefix):
            value = value[len(prefix):]
    return value.rstrip("/")


def _norm_helm_url(url: str | None) -> str:
    """Normalise a Helm repo URL, dropping the trailing ``/index.yaml``."""
    value = _norm_url(url)
    if value.endswith("/index.yaml"):
        value = value[: -len("/index.yaml")]
    return value


def _migrate_secret(value: str | None) -> str | None:
    """Return the ciphertext to store in ``credentials.encrypted_secret``.

    Follows 11.1.3: a value that already decrypts is Fernet ciphertext and is
    copied **as-is**; a value that fails to decrypt is a pre-Fernet plaintext
    and is encrypted. The plaintext never leaves this function.
    """
    if not value:
        return None
    try:
        decrypt_secret(value)
        return value
    except SecretEncryptionError:
        return encrypt_secret(value)


def _admin_user_id(conn) -> int | None:
    """Resolve the id of the platform admin user, if one exists."""
    row = conn.execute(
        sa.text(
            "SELECT u.id FROM users u "
            "JOIN user_roles ur ON ur.user_id = u.id "
            "JOIN roles r ON r.id = ur.role_id "
            "WHERE r.name = 'admin' ORDER BY u.id LIMIT 1"
        )
    ).first()
    return row.id if row is not None else None


def _rows(conn, table: str) -> list[dict]:
    """Read every row of *table* as a plain dict keyed by column name."""
    return [dict(row._mapping) for row in conn.execute(sa.text(f"SELECT * FROM {table}"))]


def _insert_credential(
    conn,
    *,
    name: str,
    credential_type: str,
    provider: str,
    username: str | None,
    ciphertext: str | None,
    created_at,
    updated_at,
) -> int | None:
    """Insert a migrated credential (idempotent by unique ``name``)."""
    existing = conn.execute(
        sa.text("SELECT id FROM credentials WHERE name = :name"), {"name": name}
    ).first()
    if existing is not None:
        return existing.id

    row = conn.execute(
        sa.text(
            "INSERT INTO credentials "
            "(name, credential_type, provider, username, encrypted_secret, "
            " status_flag, status_text, created_at, updated_at) "
            "VALUES "
            "(:name, CAST(:credential_type AS credential_type_enum), :provider, "
            " :username, :encrypted_secret, 0, 'OK', :created_at, :updated_at) "
            "RETURNING id"
        ),
        {
            "name": name,
            "credential_type": credential_type,
            "provider": provider,
            "username": username,
            "encrypted_secret": ciphertext,
            "created_at": created_at,
            "updated_at": updated_at,
        },
    ).first()
    return row.id


def _insert_provider(conn, *, name: str, **values) -> int:
    """Insert a migrated ``resource_providers`` row (idempotent by ``name``).

    ``config`` is JSON-serialised before binding and cast to ``jsonb``; enum
    columns are cast from bound strings.
    """
    existing = conn.execute(
        sa.text("SELECT id FROM resource_providers WHERE name = :name"), {"name": name}
    ).first()
    if existing is not None:
        return existing.id

    params = dict(values)
    params["name"] = name
    params["config"] = json.dumps(values.get("config") or {})

    row = conn.execute(
        sa.text(
            "INSERT INTO resource_providers "
            "(domain, subtype, category, visibility, direction, name, label, "
            " description, base_url, config, credential_id, owner_user_id, "
            " is_active, is_default, is_protected, verify_ssl, priority, "
            " status_flag, status_text, last_checked_at, is_deleted, deleted_at, "
            " created_at, updated_at) "
            "VALUES "
            "(CAST(:domain AS provider_domain_enum), "
            " CAST(:subtype AS provider_subtype_enum), "
            " CAST(:category AS provider_category_enum), "
            " CAST(:visibility AS provider_visibility_enum), "
            " CAST(:direction AS provider_direction_enum), "
            " :name, :label, :description, :base_url, "
            " CAST(:config AS jsonb), :credential_id, :owner_user_id, "
            " :is_active, :is_default, :is_protected, :verify_ssl, :priority, "
            " :status_flag, :status_text, :last_checked_at, :is_deleted, :deleted_at, "
            " :created_at, :updated_at) "
            "RETURNING id"
        ),
        params,
    ).first()
    return row.id


def _private_or_public(admin_id: int | None, *, want_private: bool) -> tuple[str, str, int | None]:
    """Resolve category/visibility/owner for a possibly-private row.

    ``private`` requires an owner (DB CHECK); without an admin user we degrade
    to ``public`` rather than fail the constraint (see module docstring).
    """
    if want_private and admin_id is not None:
        return "private", "owner", admin_id
    return "public", "public", None


def _migrate_data() -> None:
    conn = op.get_bind()
    admin_id = _admin_user_id(conn)

    # Target registries referenced by docker_image_sources (→ category=system, 11.3.4).
    target_urls: set[str] = set()
    for row in conn.execute(
        sa.text(
            "SELECT DISTINCT target_registry_url FROM docker_image_sources "
            "WHERE target_registry_url IS NOT NULL AND target_registry_url != ''"
        )
    ):
        target_urls.add(_norm_url(row.target_registry_url))

    # Cross-reference maps used by the FK relink step below.
    source_map: dict[int, int] = {}  # source_providers.id → resource_providers.id
    gitlab_map: dict[int, int] = {}  # gitlab_instances.id → resource_providers.id
    docker_map: dict[int, int] = {}  # docker_registry_instances.id → resource_providers.id
    docker_by_url: dict[str, int] = {}  # normalised url → resource_providers.id
    helm_by_url: dict[str, int] = {}  # normalised url → resource_providers.id

    # ═══════════════════════════════════════════════════════════════════════
    # 1. source_providers → resource_providers (git). credential_id reused.
    # ═══════════════════════════════════════════════════════════════════════
    for row in _rows(conn, "source_providers"):
        subtype = _PROVIDER_TYPE_TO_SUBTYPE.get(row["provider_type"], "generic_git")
        is_anon = bool(row["is_anon"])
        category, visibility, owner = _private_or_public(admin_id, want_private=not is_anon)

        provider_id = _insert_provider(
            conn,
            name=f"legacy-source-{row['id']}",
            domain="git",
            subtype=subtype,
            category=category,
            visibility=visibility,
            direction="external",
            label=row["label"],
            description=None,
            base_url=None,
            config={},
            credential_id=row["credential_id"],
            owner_user_id=owner,
            is_active=True,
            is_default=False,
            is_protected=bool(row["is_builtin"]),
            verify_ssl=True,
            priority=0,
            status_flag=0,
            status_text=None,
            last_checked_at=None,
            is_deleted=bool(row["is_deleted"]),
            deleted_at=row["deleted_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        source_map[row["id"]] = provider_id

    # ═══════════════════════════════════════════════════════════════════════
    # 2. gitlab_instances → resource_providers (git/gitlab)
    # ═══════════════════════════════════════════════════════════════════════
    for row in _rows(conn, "gitlab_instances"):
        is_default = bool(row["is_default"])
        category, direction = (
            ("system", "internal") if is_default else ("private", "external")
        )
        visibility = "owner" if category == "system" else "owner"
        owner = admin_id if category == "private" else None
        if category == "private" and owner is None:
            category, visibility, owner = "public", "public", None

        ciphertext = _migrate_secret(row["token"])
        credential_id = None
        if ciphertext is not None:
            credential_id = _insert_credential(
                conn,
                name=f"migrated-gitlab-{row['name']}",
                credential_type="gitlab_token",
                provider=_CREDENTIAL_PROVIDER["gitlab"],
                username=None,
                ciphertext=ciphertext,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

        config = {}
        if row.get("default_group_id") is not None:
            config["default_group_id"] = row["default_group_id"]

        provider_id = _insert_provider(
            conn,
            name=f"legacy-gitlab-{row['name']}",
            domain="git",
            subtype="gitlab",
            category=category,
            visibility=visibility,
            direction=direction,
            label=row["name"],
            description=None,
            base_url=row["url"],
            config=config,
            credential_id=credential_id,
            owner_user_id=owner,
            is_active=bool(row["is_active"]),
            is_default=is_default,
            is_protected=(category == "system"),
            verify_ssl=bool(row["verify_ssl"]),
            priority=0,
            status_flag=row["status_flag"],
            status_text=row["status_text"],
            last_checked_at=row["last_checked_at"],
            is_deleted=False,
            deleted_at=None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        gitlab_map[row["id"]] = provider_id

    # ═══════════════════════════════════════════════════════════════════════
    # 3. github_instances → resource_providers (git/github, private/external)
    # ═══════════════════════════════════════════════════════════════════════
    for row in _rows(conn, "github_instances"):
        category, visibility, owner = _private_or_public(admin_id, want_private=True)

        ciphertext = _migrate_secret(row["token"])
        credential_id = None
        if ciphertext is not None:
            credential_id = _insert_credential(
                conn,
                name=f"migrated-github-{row['name']}",
                credential_type="github_token",
                provider=_CREDENTIAL_PROVIDER["github"],
                username=None,
                ciphertext=ciphertext,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

        _insert_provider(
            conn,
            name=f"legacy-github-{row['name']}",
            domain="git",
            subtype="github",
            category=category,
            visibility=visibility,
            direction="external",
            label=row["name"],
            description=None,
            base_url=None,
            config={},
            credential_id=credential_id,
            owner_user_id=owner,
            is_active=bool(row["is_active"]),
            is_default=bool(row["is_default"]),
            is_protected=False,
            verify_ssl=True,
            priority=0,
            status_flag=row["status_flag"],
            status_text=row["status_text"],
            last_checked_at=row["last_checked_at"],
            is_deleted=False,
            deleted_at=None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 4. harbor_instances → resource_providers (docker/harbor, system/internal)
    # ═══════════════════════════════════════════════════════════════════════
    for row in _rows(conn, "harbor_instances"):
        ciphertext = _migrate_secret(row["password"])
        credential_id = None
        if ciphertext is not None:
            credential_id = _insert_credential(
                conn,
                name=f"migrated-harbor-{row['name']}",
                credential_type="https_basic",
                provider=_CREDENTIAL_PROVIDER["harbor"],
                username=row["username"],
                ciphertext=ciphertext,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

        config = {}
        if row.get("default_project") is not None:
            config["default_project"] = row["default_project"]

        _insert_provider(
            conn,
            name=f"legacy-harbor-{row['name']}",
            domain="docker",
            subtype="harbor",
            category="system",
            visibility="owner",
            direction="internal",
            label=row["name"],
            description=None,
            base_url=row["url"],
            config=config,
            credential_id=credential_id,
            owner_user_id=None,
            is_active=bool(row["is_active"]),
            is_default=bool(row["is_default"]),
            is_protected=True,
            verify_ssl=bool(row["verify_ssl"]),
            priority=0,
            status_flag=row["status_flag"],
            status_text=row["status_text"],
            last_checked_at=row["last_checked_at"],
            is_deleted=False,
            deleted_at=None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 5. docker_registry_instances → resource_providers (docker)
    # ═══════════════════════════════════════════════════════════════════════
    for row in _rows(conn, "docker_registry_instances"):
        subtype = _REGISTRY_PROVIDER_TO_SUBTYPE.get(
            row["registry_provider"], "generic_registry"
        )
        direction = "internal" if row["registry_type"] == "internal" else "external"
        is_target = _norm_url(row["url"]) in target_urls
        category = "system" if is_target else "private"
        visibility = "owner"
        owner = None if category == "system" else admin_id
        if category == "private" and owner is None:
            category, visibility, owner = "public", "public", None

        ciphertext = _migrate_secret(row["password"])
        credential_id = None
        if ciphertext is not None:
            credential_id = _insert_credential(
                conn,
                name=f"migrated-docker-{row['name']}",
                credential_type="https_basic",
                provider=_CREDENTIAL_PROVIDER["docker"],
                username=row["username"],
                ciphertext=ciphertext,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

        config = {}
        if subtype == "generic_registry":
            config["api_style"] = "registry_v2"

        provider_id = _insert_provider(
            conn,
            name=f"legacy-docker-{row['name']}",
            domain="docker",
            subtype=subtype,
            category=category,
            visibility=visibility,
            direction=direction,
            label=row["name"],
            description=None,
            base_url=row["url"],
            config=config,
            credential_id=credential_id,
            owner_user_id=owner,
            is_active=bool(row["is_active"]),
            is_default=bool(row["is_default"]),
            is_protected=(category == "system"),
            verify_ssl=bool(row["verify_ssl"]),
            priority=row["priority"],
            status_flag=row["status_flag"],
            status_text=row["status_text"],
            last_checked_at=row["last_checked_at"],
            is_deleted=False,
            deleted_at=None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        docker_map[row["id"]] = provider_id
        docker_by_url[_norm_url(row["url"])] = provider_id

    # ═══════════════════════════════════════════════════════════════════════
    # 6. helm_repository_instances → resource_providers (helm/helm_repo)
    # ═══════════════════════════════════════════════════════════════════════
    for row in _rows(conn, "helm_repository_instances"):
        has_secret = bool(row.get("password")) or bool(row.get("username"))
        category, visibility, owner = _private_or_public(admin_id, want_private=has_secret)

        ciphertext = _migrate_secret(row["password"])
        credential_id = None
        if ciphertext is not None:
            credential_id = _insert_credential(
                conn,
                name=f"migrated-helm-{row['name']}",
                credential_type="https_basic",
                provider=_CREDENTIAL_PROVIDER["helm"],
                username=row["username"],
                ciphertext=ciphertext,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

        provider_id = _insert_provider(
            conn,
            name=f"legacy-helm-{row['name']}",
            domain="helm",
            subtype="helm_repo",
            category=category,
            visibility=visibility,
            direction="external",
            label=row["name"],
            description=None,
            base_url=row["url"],
            config={},
            credential_id=credential_id,
            owner_user_id=owner,
            is_active=bool(row["is_active"]),
            is_default=bool(row["is_default"]),
            is_protected=False,
            verify_ssl=bool(row["verify_ssl"]),
            priority=0,
            status_flag=row["status_flag"],
            status_text=row["status_text"],
            last_checked_at=row["last_checked_at"],
            is_deleted=False,
            deleted_at=None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        helm_by_url[_norm_helm_url(row["url"])] = provider_id

    # ═══════════════════════════════════════════════════════════════════════
    # 7. Relink consumers (1.4)
    # ═══════════════════════════════════════════════════════════════════════
    for row in conn.execute(
        sa.text(
            "SELECT id, source_provider_id FROM source_repositories "
            "WHERE source_provider_id IS NOT NULL"
        )
    ):
        provider_id = source_map.get(row.source_provider_id)
        if provider_id is not None:
            conn.execute(
                sa.text("UPDATE source_repositories SET provider_id = :p WHERE id = :i"),
                {"p": provider_id, "i": row.id},
            )

    for row in conn.execute(
        sa.text(
            "SELECT id, gitlab_instance_id FROM pipelines WHERE gitlab_instance_id IS NOT NULL"
        )
    ):
        provider_id = gitlab_map.get(row.gitlab_instance_id)
        if provider_id is not None:
            conn.execute(
                sa.text("UPDATE pipelines SET provider_id = :p WHERE id = :i"),
                {"p": provider_id, "i": row.id},
            )

    for row in conn.execute(
        sa.text("SELECT id, registry_instance_id, target_registry_url FROM docker_image_sources")
    ):
        if row.registry_instance_id is not None:
            provider_id = docker_map.get(row.registry_instance_id)
            if provider_id is not None:
                conn.execute(
                    sa.text(
                        "UPDATE docker_image_sources SET provider_id = :p WHERE id = :i"
                    ),
                    {"p": provider_id, "i": row.id},
                )
        if row.target_registry_url:
            target_provider_id = docker_by_url.get(_norm_url(row.target_registry_url))
            if target_provider_id is not None:
                conn.execute(
                    sa.text(
                        "UPDATE docker_image_sources SET target_provider_id = :p WHERE id = :i"
                    ),
                    {"p": target_provider_id, "i": row.id},
                )

    for row in conn.execute(sa.text("SELECT id, repo_url FROM helm_chart_sources")):
        provider_id = helm_by_url.get(_norm_helm_url(row.repo_url))
        if provider_id is not None:
            conn.execute(
                sa.text("UPDATE helm_chart_sources SET provider_id = :p WHERE id = :i"),
                {"p": provider_id, "i": row.id},
            )


def _revert_data() -> None:
    """Remove migrated rows (prepares for downgrade)."""
    conn = op.get_bind()
    # resource_providers references credentials via SET NULL, but we drop both
    # here so order is not strictly significant.
    conn.execute(sa.text("DELETE FROM resource_providers WHERE name LIKE 'legacy-%'"))
    conn.execute(sa.text("DELETE FROM credentials WHERE name LIKE 'migrated-%'"))


def upgrade() -> None:
    # ── Additive relink columns (old columns stay for rollback / phase 7) ────
    op.add_column(
        "source_repositories", sa.Column("provider_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_source_repositories_provider_id",
        "source_repositories",
        "resource_providers",
        ["provider_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_source_repositories_provider_id"),
        "source_repositories",
        ["provider_id"],
    )

    op.add_column("pipelines", sa.Column("provider_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_pipelines_provider_id",
        "pipelines",
        "resource_providers",
        ["provider_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_pipelines_provider_id"), "pipelines", ["provider_id"])

    op.add_column(
        "docker_image_sources", sa.Column("provider_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_docker_image_sources_provider_id",
        "docker_image_sources",
        "resource_providers",
        ["provider_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_docker_image_sources_provider_id"),
        "docker_image_sources",
        ["provider_id"],
    )
    op.add_column(
        "docker_image_sources", sa.Column("target_provider_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_docker_image_sources_target_provider_id",
        "docker_image_sources",
        "resource_providers",
        ["target_provider_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_docker_image_sources_target_provider_id"),
        "docker_image_sources",
        ["target_provider_id"],
    )

    op.add_column(
        "helm_chart_sources", sa.Column("provider_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_helm_chart_sources_provider_id",
        "helm_chart_sources",
        "resource_providers",
        ["provider_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_helm_chart_sources_provider_id"), "helm_chart_sources", ["provider_id"]
    )

    # ── Data migration + relink ─────────────────────────────────────────────
    _migrate_data()


def downgrade() -> None:
    # ── Drop relink columns ─────────────────────────────────────────────────
    op.drop_index(op.f("ix_helm_chart_sources_provider_id"), table_name="helm_chart_sources")
    op.drop_constraint(
        "fk_helm_chart_sources_provider_id", "helm_chart_sources", type_="foreignkey"
    )
    op.drop_column("helm_chart_sources", "provider_id")

    op.drop_index(
        op.f("ix_docker_image_sources_target_provider_id"), table_name="docker_image_sources"
    )
    op.drop_constraint(
        "fk_docker_image_sources_target_provider_id", "docker_image_sources", type_="foreignkey"
    )
    op.drop_column("docker_image_sources", "target_provider_id")

    op.drop_index(op.f("ix_docker_image_sources_provider_id"), table_name="docker_image_sources")
    op.drop_constraint(
        "fk_docker_image_sources_provider_id", "docker_image_sources", type_="foreignkey"
    )
    op.drop_column("docker_image_sources", "provider_id")

    op.drop_index(op.f("ix_pipelines_provider_id"), table_name="pipelines")
    op.drop_constraint("fk_pipelines_provider_id", "pipelines", type_="foreignkey")
    op.drop_column("pipelines", "provider_id")

    op.drop_index(op.f("ix_source_repositories_provider_id"), table_name="source_repositories")
    op.drop_constraint(
        "fk_source_repositories_provider_id", "source_repositories", type_="foreignkey"
    )
    op.drop_column("source_repositories", "provider_id")

    # ── Remove migrated data ────────────────────────────────────────────────
    _revert_data()
