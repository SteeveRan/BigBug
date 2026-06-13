"""add_git_mirroring_v2_tables

Revision ID: 139d156bc39b
Revises: f1a2b3c4d5e6
Create Date: 2026-06-13 13:07:12.093562+00:00

Creates all new tables for git-mirroring v2 architecture and migrates
data from legacy tables (github_instances, gitlab_instances, github_orgs,
github_projects, github_releases, gitlab_mirrors, sync_logs) into the
new schema.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "139d156bc39b"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _get_credential_type_enum() -> sa.Enum:
    return sa.Enum(
        "github_token", "gitlab_token", "https_basic", "ssh_key",
        name="credential_type_enum",
        create_type=False,
    )


def _get_provider_type_enum() -> sa.Enum:
    return sa.Enum(
        "github", "gitlab", "bitbucket",
        name="provider_type_enum",
        create_type=False,
    )


def _get_discovery_status_enum() -> sa.Enum:
    return sa.Enum(
        "new", "existing", "removed",
        name="discovery_status_enum",
        create_type=False,
    )


def _get_mirror_log_type_enum() -> sa.Enum:
    return sa.Enum(
        "sync", "freshness", "import", "integrity",
        name="mirror_log_type_enum",
        create_type=False,
    )


def _migrate_data() -> None:
    """Migrate data from legacy tables to new v2 tables.

    Builds cross-reference mappings as Python dicts then uses raw SQL
    via op.execute() for bulk INSERT … SELECT operations.
    """
    conn = op.get_bind()

    # ═══════════════════════════════════════════════════════════════════════
    # 1. github_instances → credentials
    # ═══════════════════════════════════════════════════════════════════════
    conn.execute(sa.text("""
        INSERT INTO credentials (name, credential_type, provider, encrypted_secret,
                                 status_flag, status_text, created_at, updated_at)
        SELECT
            gi.name,
            'github_token',
            'github',
            gi.token,
            COALESCE(gi.status_flag, 0),
            COALESCE(gi.status_text, 'OK'),
            gi.created_at,
            gi.updated_at
        FROM github_instances gi
        WHERE gi.token IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM credentials c
              WHERE c.name = gi.name AND c.credential_type = 'github_token'
          )
    """))
    conn.execute(sa.text("""
        INSERT INTO credentials (name, credential_type, provider, encrypted_secret,
                                 status_flag, status_text, created_at, updated_at)
        SELECT
            gi.name,
            'github_token',
            'github',
            NULL,
            COALESCE(gi.status_flag, 0),
            COALESCE(gi.status_text, 'OK'),
            gi.created_at,
            gi.updated_at
        FROM github_instances gi
        WHERE gi.token IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM credentials c
              WHERE c.name = gi.name AND c.credential_type = 'github_token'
          )
    """))

    # Build mapping: github_instance.id → credential.id
    gi_to_cred = {}
    result = conn.execute(sa.text("""
        SELECT gi.id AS gi_id, c.id AS cred_id
        FROM github_instances gi
        JOIN credentials c ON c.name = gi.name AND c.credential_type = 'github_token'
    """))
    for row in result:
        gi_to_cred[row.gi_id] = row.cred_id

    # ═══════════════════════════════════════════════════════════════════════
    # 2. gitlab_instances → credentials (where token IS NOT NULL)
    # ═══════════════════════════════════════════════════════════════════════
    conn.execute(sa.text("""
        INSERT INTO credentials (name, credential_type, provider, encrypted_secret,
                                 base_url, status_flag, status_text, created_at, updated_at)
        SELECT
            gli.name,
            'gitlab_token',
            'gitlab',
            gli.token,
            gli.url,
            COALESCE(gli.status_flag, 0),
            COALESCE(gli.status_text, 'OK'),
            gli.created_at,
            gli.updated_at
        FROM gitlab_instances gli
        WHERE gli.token IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM credentials c
              WHERE c.name = gli.name AND c.credential_type = 'gitlab_token'
          )
    """))

    # Build mapping: gitlab_instance.id → credential.id
    gli_to_cred = {}
    result = conn.execute(sa.text("""
        SELECT gli.id AS gli_id, c.id AS cred_id
        FROM gitlab_instances gli
        JOIN credentials c ON c.name = gli.name AND c.credential_type = 'gitlab_token'
    """))
    for row in result:
        gli_to_cred[row.gli_id] = row.cred_id

    # ═══════════════════════════════════════════════════════════════════════
    # 3. github_instances → source_providers
    # ═══════════════════════════════════════════════════════════════════════
    for gi_id, cred_id in gi_to_cred.items():
        conn.execute(
            sa.text("""
                INSERT INTO source_providers (credential_id, provider_type, label,
                                              created_at, updated_at)
                SELECT
                    :cred_id,
                    'github',
                    gi.name || ' (GitHub)',
                    gi.created_at,
                    gi.updated_at
                FROM github_instances gi
                WHERE gi.id = :gi_id
                  AND NOT EXISTS (
                      SELECT 1 FROM source_providers sp
                      WHERE sp.label = gi.name || ' (GitHub)'
                        AND sp.provider_type = 'github'
                  )
            """),
            {"gi_id": gi_id, "cred_id": cred_id},
        )

    # For github_instances without credentials, create providers without credential_id
    conn.execute(sa.text("""
        INSERT INTO source_providers (credential_id, provider_type, label,
                                      created_at, updated_at)
        SELECT
            NULL,
            'github',
            gi.name || ' (GitHub)',
            gi.created_at,
            gi.updated_at
        FROM github_instances gi
        WHERE NOT EXISTS (
            SELECT 1 FROM credentials c
            WHERE c.name = gi.name AND c.credential_type = 'github_token'
        )
          AND NOT EXISTS (
              SELECT 1 FROM source_providers sp
              WHERE sp.label = gi.name || ' (GitHub)'
                AND sp.provider_type = 'github'
          )
    """))

    # Build mapping: github_instance.id → source_provider.id
    gi_to_sp = {}
    result = conn.execute(sa.text("""
        SELECT gi.id AS gi_id, sp.id AS sp_id
        FROM github_instances gi
        JOIN source_providers sp ON sp.label = gi.name || ' (GitHub)'
           AND sp.provider_type = 'github'
    """))
    for row in result:
        gi_to_sp[row.gi_id] = row.sp_id

    # ═══════════════════════════════════════════════════════════════════════
    # 4. gitlab_instances → source_providers
    # ═══════════════════════════════════════════════════════════════════════
    conn.execute(sa.text("""
        INSERT INTO source_providers (credential_id, provider_type, label,
                                      created_at, updated_at)
        SELECT
            NULL,
            'gitlab',
            gli.name || ' (GitLab)',
            gli.created_at,
            gli.updated_at
        FROM gitlab_instances gli
        WHERE NOT EXISTS (
            SELECT 1 FROM source_providers sp
            WHERE sp.label = gli.name || ' (GitLab)'
              AND sp.provider_type = 'gitlab'
        )
    """))

    # Build mapping: gitlab_instance.id → source_provider.id
    gli_to_sp = {}
    result = conn.execute(sa.text("""
        SELECT gli.id AS gli_id, sp.id AS sp_id
        FROM gitlab_instances gli
        JOIN source_providers sp ON sp.label = gli.name || ' (GitLab)'
           AND sp.provider_type = 'gitlab'
    """))
    for row in result:
        gli_to_sp[row.gli_id] = row.sp_id

    # ═══════════════════════════════════════════════════════════════════════
    # 5. github_orgs → source_groups
    # Use the first available GitHub SourceProvider for all orgs
    # (there is no direct github_org → github_instance FK in the legacy schema)
    # ═══════════════════════════════════════════════════════════════════════
    # Get the first GitHub source_provider (or any — pick min id)
    default_github_sp = None
    sp_result = conn.execute(
        sa.text("SELECT id FROM source_providers WHERE provider_type = 'github' ORDER BY id LIMIT 1")
    )
    sp_row = sp_result.first()
    if sp_row is not None:
        default_github_sp = sp_row.id

        # Insert source_groups with the default provider
        conn.execute(
            sa.text("""
                INSERT INTO source_groups (source_provider_id, external_id, name,
                                           full_path, web_url, description,
                                           created_at, updated_at)
                SELECT
                    :sp_id,
                    CAST(go.github_id AS VARCHAR),
                    go.login,
                    go.login,
                    go.avatar_url,
                    go.type,
                    go.created_at,
                    go.updated_at
                FROM github_orgs go
                WHERE NOT EXISTS (
                    SELECT 1 FROM source_groups sg
                    WHERE sg.external_id = CAST(go.github_id AS VARCHAR)
                      AND sg.source_provider_id = :sp_id
                )
            """),
            {"sp_id": default_github_sp},
        )

    # Build mapping: github_org.id → source_group.id
    go_to_sg = {}
    if default_github_sp is not None:
        result = conn.execute(sa.text("""
            SELECT go.id AS go_id, sg.id AS sg_id
            FROM github_orgs go
            JOIN source_groups sg ON sg.external_id = CAST(go.github_id AS VARCHAR)
               AND sg.source_provider_id = :sp_id
        """), {"sp_id": default_github_sp})
        for row in result:
            go_to_sg[row.go_id] = row.sg_id

    # ═══════════════════════════════════════════════════════════════════════
    # 6. github_projects → source_repositories
    # ═══════════════════════════════════════════════════════════════════════
    for gp_org_id, sg_id in go_to_sg.items():
        conn.execute(
            sa.text("""
                INSERT INTO source_repositories (
                    source_group_id, external_id, name, full_name, web_url,
                    description, default_branch, license_spdx, license_name,
                    is_archived, is_fork,
                    source_created_at, source_updated_at, source_pushed_at,
                    created_at, updated_at
                )
                SELECT
                    :sg_id,
                    CAST(gp.github_id AS VARCHAR),
                    gp.name,
                    gp.full_name,
                    gp.github_url,
                    gp.description,
                    gp.default_branch,
                    gp.license_spdx,
                    gp.license_name,
                    gp.is_archived,
                    gp.is_fork,
                    gp.github_created_at,
                    gp.github_updated_at,
                    gp.github_pushed_at,
                    gp.created_at,
                    gp.updated_at
                FROM github_projects gp
                WHERE gp.org_id = :go_id
                  AND NOT EXISTS (
                      SELECT 1 FROM source_repositories sr
                      WHERE sr.external_id = CAST(gp.github_id AS VARCHAR)
                        AND sr.source_group_id = :sg_id
                  )
            """),
            {"sg_id": sg_id, "go_id": gp_org_id},
        )

    # Build mapping: github_project.id → source_repository.id
    gp_to_sr = {}
    result = conn.execute(sa.text("""
        SELECT gp.id AS gp_id, sr.id AS sr_id
        FROM github_projects gp
        JOIN github_orgs go ON go.id = gp.org_id
        JOIN source_groups sg ON sg.external_id = CAST(go.github_id AS VARCHAR)
        JOIN source_repositories sr ON sr.external_id = CAST(gp.github_id AS VARCHAR)
           AND sr.source_group_id = sg.id
    """))
    for row in result:
        gp_to_sr[row.gp_id] = row.sr_id

    # ═══════════════════════════════════════════════════════════════════════
    # 7. github_releases → mirror_release_logs
    # ═══════════════════════════════════════════════════════════════════════
    conn.execute(sa.text("""
        INSERT INTO mirror_release_logs (
            source_repository_id, tag, name, description, url,
            published_at, is_prerelease, detected_at
        )
        SELECT
            sr.id,
            gr.tag_name,
            gr.name,
            gr.body,
            NULL,
            gr.published_at,
            gr.is_prerelease,
            gr.created_at
        FROM github_releases gr
        JOIN github_projects gp ON gp.id = gr.project_id
        JOIN source_repositories sr ON sr.external_id = CAST(gp.github_id AS VARCHAR)
        WHERE NOT EXISTS (
            SELECT 1 FROM mirror_release_logs mrl
            WHERE mrl.tag = gr.tag_name
              AND mrl.source_repository_id = sr.id
        )
    """))

    # ═══════════════════════════════════════════════════════════════════════
    # 8. gitlab_mirrors → mirrors
    # ═══════════════════════════════════════════════════════════════════════
    conn.execute(sa.text("""
        INSERT INTO mirrors (
            source_repository_id, target_namespace, target_project_name,
            target_project_id, target_web_url,
            status_flag, status_text, last_sync_at,
            is_imported, created_at, updated_at
        )
        SELECT
            sr.id,
            gm.gitlab_namespace,
            gm.gitlab_name,
            gm.gitlab_project_id,
            gm.gitlab_url,
            COALESCE(gm.status_flag, 4),
            COALESCE(gm.status_text, 'Pending'),
            gm.last_sync_at,
            COALESCE(gm.is_imported, FALSE),
            gm.created_at,
            gm.updated_at
        FROM gitlab_mirrors gm
        JOIN github_projects gp ON gp.id = gm.project_id
        JOIN source_repositories sr ON sr.external_id = CAST(gp.github_id AS VARCHAR)
        WHERE NOT EXISTS (
            SELECT 1 FROM mirrors m
            WHERE m.target_project_id = gm.gitlab_project_id
              AND m.target_web_url = gm.gitlab_url
        )
    """))

    # Build mapping: gitlab_mirror.id → mirror.id
    gm_to_m = {}
    result = conn.execute(sa.text("""
        SELECT gm.id AS gm_id, m.id AS m_id
        FROM gitlab_mirrors gm
        JOIN github_projects gp ON gp.id = gm.project_id
        JOIN source_repositories sr ON sr.external_id = CAST(gp.github_id AS VARCHAR)
        JOIN mirrors m ON m.source_repository_id = sr.id
           AND m.target_project_id = gm.gitlab_project_id
           AND m.target_web_url = gm.gitlab_url
    """))
    for row in result:
        gm_to_m[row.gm_id] = row.m_id

    # ═══════════════════════════════════════════════════════════════════════
    # 9. sync_logs → mirror_logs
    # ═══════════════════════════════════════════════════════════════════════
    conn.execute(sa.text("""
        INSERT INTO mirror_logs (
            mirror_id, log_type, gitlab_pipeline_id, gitlab_pipeline_url,
            status_flag, status_text, started_at, finished_at,
            triggered_by, created_at
        )
        SELECT
            m.id,
            'sync',
            sl.pipeline_id,
            sl.pipeline_url,
            COALESCE(sl.status_flag, 4),
            COALESCE(sl.status_text, 'Pending'),
            sl.started_at,
            sl.finished_at,
            sl.triggered_by,
            sl.created_at
        FROM sync_logs sl
        JOIN gitlab_mirrors gm ON gm.id = sl.mirror_id
        JOIN mirrors m ON m.target_project_id = gm.gitlab_project_id
           AND m.target_web_url = gm.gitlab_url
        WHERE NOT EXISTS (
            SELECT 1 FROM mirror_logs ml
            WHERE ml.mirror_id = m.id
              AND ml.gitlab_pipeline_id = sl.pipeline_id
              AND ml.log_type = 'sync'
        )
    """))

    # ═══════════════════════════════════════════════════════════════════════
    # 10. Create default Pipeline
    # ═══════════════════════════════════════════════════════════════════════
    # Link to first gitlab_instance if one exists
    first_gli = conn.execute(
        sa.text("SELECT id FROM gitlab_instances ORDER BY id LIMIT 1")
    ).first()
    gli_id = first_gli.id if first_gli is not None else None

    conn.execute(
        sa.text("""
            INSERT INTO pipelines (name, description, gitlab_instance_id, ref,
                                   is_default, is_enabled, created_at, updated_at)
            SELECT
                'Default',
                'Default pipeline (auto-created by migration)',
                :gli_id,
                'main',
                TRUE,
                TRUE,
                NOW(),
                NOW()
            WHERE NOT EXISTS (
                SELECT 1 FROM pipelines WHERE is_default = TRUE
            )
        """),
        {"gli_id": gli_id},
    )

    # Get default pipeline id
    default_pipeline = conn.execute(
        sa.text("SELECT id FROM pipelines WHERE is_default = TRUE LIMIT 1")
    ).first()
    default_pipeline_id = default_pipeline.id if default_pipeline else None

    # ═══════════════════════════════════════════════════════════════════════
    # 11. Create default SyncGroup
    # ═══════════════════════════════════════════════════════════════════════
    conn.execute(
        sa.text("""
            INSERT INTO sync_groups (name, description, pipeline_id, is_default,
                                     created_at, updated_at)
            SELECT
                'Default',
                'Default sync group (auto-created by migration)',
                :pipeline_id,
                TRUE,
                NOW(),
                NOW()
            WHERE NOT EXISTS (
                SELECT 1 FROM sync_groups WHERE is_default = TRUE
            )
        """),
        {"pipeline_id": default_pipeline_id},
    )

    # ═══════════════════════════════════════════════════════════════════════
    # 12. Link mirrors to default SyncGroup
    # ═══════════════════════════════════════════════════════════════════════
    conn.execute(sa.text("""
        UPDATE mirrors
        SET sync_group_id = (SELECT id FROM sync_groups WHERE is_default = TRUE LIMIT 1)
        WHERE sync_group_id IS NULL
    """))


def _revert_data() -> None:
    """Remove migrated data from new tables (prepares for downgrade)."""
    # Delete in reverse dependency order
    op.execute("DELETE FROM mirror_release_logs")
    op.execute("DELETE FROM mirror_logs")
    op.execute("DELETE FROM mirrors")
    op.execute("DELETE FROM source_repositories")
    op.execute("DELETE FROM source_groups")
    op.execute("DELETE FROM role_scope_sync_groups")
    op.execute("DELETE FROM role_scope_credentials")
    op.execute("DELETE FROM role_scope_source_groups")
    op.execute("DELETE FROM sync_groups")
    op.execute("DELETE FROM pipeline_components")
    op.execute("DELETE FROM pipelines")
    op.execute("DELETE FROM source_providers")
    op.execute("DELETE FROM credentials")


def upgrade() -> None:
    # ── Create enum types (idempotent via DO $$ ... EXCEPTION) ────────────
    for name, values in [
        (
            "credential_type_enum",
            "'github_token', 'gitlab_token', 'https_basic', 'ssh_key'",
        ),
        ("provider_type_enum", "'github', 'gitlab', 'bitbucket'"),
        ("discovery_status_enum", "'new', 'existing', 'removed'"),
        ("mirror_log_type_enum", "'sync', 'freshness', 'import', 'integrity'"),
    ]:
        op.execute(
            text(
                f"DO $$ BEGIN"
                f" CREATE TYPE {name} AS ENUM ({values});"
                f" EXCEPTION WHEN duplicate_object THEN NULL;"
                f" END $$"
            )
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 1. credentials
    # ═══════════════════════════════════════════════════════════════════════
    op.create_table(
        "credentials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "credential_type",
            sa.String(50),
            nullable=False,
        ),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("encrypted_secret", sa.Text(), nullable=True),
        sa.Column("ssh_public_key", sa.Text(), nullable=True),
        sa.Column("base_url", sa.String(500), nullable=True),
        sa.Column("status_flag", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status_text", sa.String(500), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_credentials_id"), "credentials", ["id"], unique=False)
    op.create_index(op.f("ix_credentials_name"), "credentials", ["name"], unique=True)

    # ═══════════════════════════════════════════════════════════════════════
    # 2. source_providers
    # ═══════════════════════════════════════════════════════════════════════
    op.create_table(
        "source_providers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "credential_id",
            sa.Integer(),
            sa.ForeignKey("credentials.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "provider_type",
            sa.String(50),
            nullable=False,
        ),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_source_providers_id"), "source_providers", ["id"], unique=False)

    # ═══════════════════════════════════════════════════════════════════════
    # 3. source_groups
    # ═══════════════════════════════════════════════════════════════════════
    op.create_table(
        "source_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "source_provider_id",
            sa.Integer(),
            sa.ForeignKey("source_providers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("full_path", sa.String(500), nullable=True),
        sa.Column("web_url", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("total_repos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mirrored_repos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_source_groups_id"), "source_groups", ["id"], unique=False)

    # ═══════════════════════════════════════════════════════════════════════
    # 4. source_repositories
    # ═══════════════════════════════════════════════════════════════════════
    op.create_table(
        "source_repositories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "source_group_id",
            sa.Integer(),
            sa.ForeignKey("source_groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(500), nullable=False),
        sa.Column("web_url", sa.String(500), nullable=True),
        sa.Column("clone_url_https", sa.String(500), nullable=True),
        sa.Column("clone_url_ssh", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_branch", sa.String(255), nullable=True),
        sa.Column("license_spdx", sa.String(100), nullable=True),
        sa.Column("license_name", sa.String(255), nullable=True),
        sa.Column("readme_html", sa.Text(), nullable=True),
        sa.Column("readme_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latest_release_tag", sa.String(255), nullable=True),
        sa.Column("latest_release_name", sa.String(255), nullable=True),
        sa.Column("latest_release_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latest_release_url", sa.String(500), nullable=True),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_fork", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_disabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "discovery_status",
            sa.String(50),
            nullable=False,
            server_default="new",
        ),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_pushed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_source_repositories_id"), "source_repositories", ["id"], unique=False
    )

    # ═══════════════════════════════════════════════════════════════════════
    # 5. pipelines
    # ═══════════════════════════════════════════════════════════════════════
    op.create_table(
        "pipelines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "gitlab_instance_id",
            sa.Integer(),
            sa.ForeignKey("gitlab_instances.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("ref", sa.String(255), nullable=False),
        sa.Column(
            "default_variables",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("is_default", name="uq_pipelines_default"),
    )
    op.create_index(op.f("ix_pipelines_id"), "pipelines", ["id"], unique=False)
    op.create_index(op.f("ix_pipelines_name"), "pipelines", ["name"], unique=True)

    # ═══════════════════════════════════════════════════════════════════════
    # 6. pipeline_components
    # ═══════════════════════════════════════════════════════════════════════
    op.create_table(
        "pipeline_components",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "pipeline_id",
            sa.Integer(),
            sa.ForeignKey("pipelines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "component_id",
            sa.Integer(),
            sa.ForeignKey("gitlab_components.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "overrides",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_pipeline_components_id"), "pipeline_components", ["id"], unique=False
    )

    # ═══════════════════════════════════════════════════════════════════════
    # 7. Add pipeline_id column to existing pipeline_runs table
    # ═══════════════════════════════════════════════════════════════════════
    op.add_column(
        "pipeline_runs",
        sa.Column("pipeline_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_pipeline_runs_pipeline_id"),
        "pipeline_runs",
        ["pipeline_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_pipeline_runs_pipeline_id",
        "pipeline_runs",
        "pipelines",
        ["pipeline_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # 8. sync_groups
    # ═══════════════════════════════════════════════════════════════════════
    op.create_table(
        "sync_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "pipeline_id",
            sa.Integer(),
            sa.ForeignKey("pipelines.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sync_cron", sa.String(100), nullable=True),
        sa.Column("sync_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sync_concurrency", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("freshness_cron", sa.String(100), nullable=True),
        sa.Column("freshness_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("freshness_concurrency", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("is_default", name="uq_sync_groups_default"),
    )
    op.create_index(op.f("ix_sync_groups_id"), "sync_groups", ["id"], unique=False)
    op.create_index(op.f("ix_sync_groups_name"), "sync_groups", ["name"], unique=True)

    # ═══════════════════════════════════════════════════════════════════════
    # 9. mirrors
    # ═══════════════════════════════════════════════════════════════════════
    op.create_table(
        "mirrors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "source_repository_id",
            sa.Integer(),
            sa.ForeignKey("source_repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sync_group_id",
            sa.Integer(),
            sa.ForeignKey("sync_groups.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("target_namespace", sa.String(500), nullable=True),
        sa.Column("target_project_name", sa.String(255), nullable=True),
        sa.Column("target_project_id", sa.String(255), nullable=True),
        sa.Column("target_web_url", sa.String(500), nullable=True),
        sa.Column("status_flag", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("status_text", sa.String(500), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_status", sa.String(50), nullable=True),
        sa.Column("last_freshness_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_freshness_status", sa.String(50), nullable=True),
        sa.Column("last_known_commit_sha", sa.String(40), nullable=True),
        sa.Column("last_known_commit_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_known_commit_author", sa.String(255), nullable=True),
        sa.Column("target_diverged_commits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_imported", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mirrors_id"), "mirrors", ["id"], unique=False)

    # ═══════════════════════════════════════════════════════════════════════
    # 10. mirror_logs
    # ═══════════════════════════════════════════════════════════════════════
    op.create_table(
        "mirror_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "mirror_id",
            sa.Integer(),
            sa.ForeignKey("mirrors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "log_type",
            sa.String(50),
            nullable=False,
        ),
        sa.Column(
            "pipeline_run_id",
            sa.Integer(),
            sa.ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("gitlab_pipeline_id", sa.String(255), nullable=True),
        sa.Column("gitlab_pipeline_url", sa.String(500), nullable=True),
        sa.Column("status_flag", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("status_text", sa.String(500), nullable=True),
        sa.Column("source_commit_sha", sa.String(40), nullable=True),
        sa.Column("source_commit_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("target_commit_sha", sa.String(40), nullable=True),
        sa.Column("commits_behind", sa.Integer(), nullable=True),
        sa.Column("target_extra_commits", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("triggered_by", sa.String(100), nullable=True),
        sa.Column("details", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mirror_logs_id"), "mirror_logs", ["id"], unique=False)
    op.create_index(
        op.f("ix_mirror_logs_mirror_id"), "mirror_logs", ["mirror_id"], unique=False
    )

    # ═══════════════════════════════════════════════════════════════════════
    # 11. mirror_release_logs
    # ═══════════════════════════════════════════════════════════════════════
    op.create_table(
        "mirror_release_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "source_repository_id",
            sa.Integer(),
            sa.ForeignKey("source_repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tag", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("url", sa.String(500), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_prerelease", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mirror_release_logs_id"), "mirror_release_logs", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_mirror_release_logs_source_repository_id"),
        "mirror_release_logs",
        ["source_repository_id"],
        unique=False,
    )

    # ═══════════════════════════════════════════════════════════════════════
    # 12. role_scope_source_groups
    # ═══════════════════════════════════════════════════════════════════════
    op.create_table(
        "role_scope_source_groups",
        sa.Column(
            "role_id",
            sa.Integer(),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "source_group_id",
            sa.Integer(),
            sa.ForeignKey("source_groups.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("role_id", "source_group_id"),
    )

    # ═══════════════════════════════════════════════════════════════════════
    # 13. role_scope_credentials
    # ═══════════════════════════════════════════════════════════════════════
    op.create_table(
        "role_scope_credentials",
        sa.Column(
            "role_id",
            sa.Integer(),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "credential_id",
            sa.Integer(),
            sa.ForeignKey("credentials.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("role_id", "credential_id"),
    )

    # ═══════════════════════════════════════════════════════════════════════
    # 14. role_scope_sync_groups
    # ═══════════════════════════════════════════════════════════════════════
    op.create_table(
        "role_scope_sync_groups",
        sa.Column(
            "role_id",
            sa.Integer(),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "sync_group_id",
            sa.Integer(),
            sa.ForeignKey("sync_groups.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("role_id", "sync_group_id"),
    )

    # ── Cast string columns to their enum types ─────────────────────────--
    op.execute(
        text(
            "ALTER TABLE credentials ALTER COLUMN credential_type "
            "TYPE credential_type_enum USING credential_type::credential_type_enum"
        )
    )
    op.execute(
        text(
            "ALTER TABLE source_providers ALTER COLUMN provider_type "
            "TYPE provider_type_enum USING provider_type::provider_type_enum"
        )
    )
    # discovery_status has a server_default — drop it first, then alter, then restore
    op.execute(
        text(
            "ALTER TABLE source_repositories ALTER COLUMN discovery_status "
            "DROP DEFAULT"
        )
    )
    op.execute(
        text(
            "ALTER TABLE source_repositories ALTER COLUMN discovery_status "
            "TYPE discovery_status_enum USING discovery_status::discovery_status_enum"
        )
    )
    op.execute(
        text(
            "ALTER TABLE source_repositories ALTER COLUMN discovery_status "
            "SET DEFAULT 'new'::discovery_status_enum"
        )
    )
    op.execute(
        text(
            "ALTER TABLE mirror_logs ALTER COLUMN log_type "
            "TYPE mirror_log_type_enum USING log_type::mirror_log_type_enum"
        )
    )

    # ═══════════════════════════════════════════════════════════════════════
    # 15. Migrate data
    # ═══════════════════════════════════════════════════════════════════════
    _migrate_data()


def downgrade() -> None:
    # ── Revert data first (so FK constraints don't block DROP TABLE) ───────
    _revert_data()

    # ── Drop tables in reverse dependency order ────────────────────────────
    op.drop_table("role_scope_sync_groups")
    op.drop_table("role_scope_credentials")
    op.drop_table("role_scope_source_groups")

    op.drop_index(
        op.f("ix_mirror_release_logs_source_repository_id"),
        table_name="mirror_release_logs",
    )
    op.drop_index(op.f("ix_mirror_release_logs_id"), table_name="mirror_release_logs")
    op.drop_table("mirror_release_logs")

    op.drop_index(op.f("ix_mirror_logs_mirror_id"), table_name="mirror_logs")
    op.drop_index(op.f("ix_mirror_logs_id"), table_name="mirror_logs")
    op.drop_table("mirror_logs")

    op.drop_index(op.f("ix_mirrors_id"), table_name="mirrors")
    op.drop_table("mirrors")

    op.drop_index(op.f("ix_sync_groups_name"), table_name="sync_groups")
    op.drop_index(op.f("ix_sync_groups_id"), table_name="sync_groups")
    op.drop_table("sync_groups")

    # ── Remove pipeline_id column from pipeline_runs ───────────────────────
    op.drop_constraint(
        "fk_pipeline_runs_pipeline_id", "pipeline_runs", type_="foreignkey"
    )
    op.drop_index(op.f("ix_pipeline_runs_pipeline_id"), table_name="pipeline_runs")
    op.drop_column("pipeline_runs", "pipeline_id")

    op.drop_index(op.f("ix_pipeline_components_id"), table_name="pipeline_components")
    op.drop_table("pipeline_components")

    op.drop_index(op.f("ix_pipelines_name"), table_name="pipelines")
    op.drop_index(op.f("ix_pipelines_id"), table_name="pipelines")
    op.drop_table("pipelines")

    op.drop_index(op.f("ix_source_repositories_id"), table_name="source_repositories")
    op.drop_table("source_repositories")

    op.drop_index(op.f("ix_source_groups_id"), table_name="source_groups")
    op.drop_table("source_groups")

    op.drop_index(op.f("ix_source_providers_id"), table_name="source_providers")
    op.drop_table("source_providers")

    op.drop_index(op.f("ix_credentials_name"), table_name="credentials")
    op.drop_index(op.f("ix_credentials_id"), table_name="credentials")
    op.drop_table("credentials")

    # ── Drop enum types ───────────────────────────────────────────────────
    op.execute(text("DROP TYPE IF EXISTS mirror_log_type_enum"))
    op.execute(text("DROP TYPE IF EXISTS discovery_status_enum"))
    op.execute(text("DROP TYPE IF EXISTS provider_type_enum"))
    op.execute(text("DROP TYPE IF EXISTS credential_type_enum"))
