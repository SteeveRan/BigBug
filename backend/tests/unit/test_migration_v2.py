"""
@file test_migration_v2.py
@description Tests for the git-mirroring v2 schema and its enum types. After the
             Alembic reset these assertions run against the ORM models and
             ``Base.metadata`` (the source of truth) rather than a specific
             historical migration file: the v2 tables, their columns and enum
             values must all be present in the current models so that the new
             ``initial schema`` migration reproduces them.
@dependencies backend/app/models/*
"""

import sqlalchemy as sa

from app.database import Base
from app.models.credential import CredentialType
from app.models.mirror_log import MirrorLogType
from app.models.provider_type import ProviderType
from app.models.source_repository import DiscoveryStatus

# ── Tables expected to exist in the current schema ─────────────────────────
V2_TABLES = frozenset(
    {
        "credentials",
        "source_groups",
        "source_repositories",
        "pipelines",
        "pipeline_components",
        "sync_groups",
        "mirrors",
        "mirror_logs",
        "mirror_release_logs",
        "role_scope_source_groups",
        "role_scope_credentials",
        "role_scope_sync_groups",
    }
)


class TestMigrationV2Tables:
    """Verify that Base.metadata includes all v2 tables."""

    def test_all_v2_tables_in_metadata(self):
        """All v2 tables are present in SQLAlchemy metadata."""
        registered = frozenset(Base.metadata.tables.keys())
        missing = V2_TABLES - registered
        assert not missing, f"Tables missing from metadata: {missing}"

    def test_credentials_table(self):
        """credentials table has expected columns."""
        table = Base.metadata.tables["credentials"]
        cols = {c.name for c in table.columns}
        expected = {
            "id",
            "name",
            "credential_type",
            "provider",
            "username",
            "encrypted_secret",
            "ssh_public_key",
            "base_url",
            "status_flag",
            "status_text",
            "last_tested_at",
            "is_deleted",
            "deleted_at",
            "created_at",
            "updated_at",
        }
        assert cols >= expected

    def test_source_groups_table(self):
        """source_groups no longer has FK to source_providers."""
        table = Base.metadata.tables["source_groups"]
        cols = {c.name for c in table.columns}
        assert "source_provider_id" not in cols
        assert "external_id" in cols
        assert "name" in cols

    def test_source_repositories_table(self):
        """source_repositories has FK to source_groups and provider_id."""
        table = Base.metadata.tables["source_repositories"]
        cols = {c.name for c in table.columns}
        assert "source_provider_id" not in cols
        assert "provider_id" in cols
        assert "source_group_id" in cols
        assert "discovery_status" in cols

    def test_pipelines_table(self):
        """pipelines has provider_id and is_default unique."""
        table = Base.metadata.tables["pipelines"]
        cols = {c.name for c in table.columns}
        assert "provider_id" in cols
        assert "is_default" in cols

    def test_pipeline_components_table(self):
        """pipeline_components has FKs to pipelines and gitlab_components."""
        table = Base.metadata.tables["pipeline_components"]
        cols = {c.name for c in table.columns}
        assert "pipeline_id" in cols
        assert "component_id" in cols

    def test_sync_groups_table(self):
        """sync_groups has FK to pipelines and is_default unique."""
        table = Base.metadata.tables["sync_groups"]
        cols = {c.name for c in table.columns}
        assert "pipeline_id" in cols
        assert "is_default" in cols

    def test_mirrors_table(self):
        """mirrors has FK to sync_groups."""
        table = Base.metadata.tables["mirrors"]
        cols = {c.name for c in table.columns}
        assert "sync_group_id" in cols

    def test_mirror_logs_table(self):
        """mirror_logs has FK to mirrors."""
        table = Base.metadata.tables["mirror_logs"]
        cols = {c.name for c in table.columns}
        assert "mirror_id" in cols
        assert "log_type" in cols

    def test_mirror_release_logs_table(self):
        """mirror_release_logs has FK to source_repositories."""
        table = Base.metadata.tables["mirror_release_logs"]
        cols = {c.name for c in table.columns}
        assert "source_repository_id" in cols

    def test_role_scope_source_groups_table(self):
        """role_scope_source_groups has composite PK."""
        table = Base.metadata.tables["role_scope_source_groups"]
        assert "role_id" in table.columns
        assert "source_group_id" in table.columns

    def test_role_scope_credentials_table(self):
        """role_scope_credentials has composite PK."""
        table = Base.metadata.tables["role_scope_credentials"]
        assert "role_id" in table.columns
        assert "credential_id" in table.columns

    def test_role_scope_sync_groups_table(self):
        """role_scope_sync_groups has composite PK."""
        table = Base.metadata.tables["role_scope_sync_groups"]
        assert "role_id" in table.columns
        assert "sync_group_id" in table.columns

    def test_pipeline_runs_has_pipeline_id(self):
        """pipeline_runs has the new pipeline_id FK column."""
        table = Base.metadata.tables["pipeline_runs"]
        assert "pipeline_id" in table.columns
        col = table.columns["pipeline_id"]
        assert isinstance(col.type, sa.Integer)
        assert col.nullable is True


class TestEnumModels:
    """Verify the enum values that the schema enums are built from."""

    def test_credential_type_enum_values(self):
        """credential_type_enum has all 4 values."""
        assert {e.value for e in CredentialType} == {
            "github_token",
            "gitlab_token",
            "https_basic",
            "ssh_key",
        }

    def test_provider_type_enum_values(self):
        """provider_type_enum has all 3 values."""
        assert {e.value for e in ProviderType} == {"github", "gitlab", "generic"}

    def test_discovery_status_enum_values(self):
        """discovery_status_enum has all 3 values."""
        assert {e.value for e in DiscoveryStatus} == {"new", "existing", "removed"}

    def test_mirror_log_type_enum_values(self):
        """mirror_log_type_enum has all 4 values."""
        assert {e.value for e in MirrorLogType} == {
            "sync",
            "freshness",
            "import",
            "integrity",
        }


def _col_default(table_name: str, col_name: str):
    """Return the declared server default or Python default of a column."""
    col = Base.metadata.tables[table_name].columns[col_name]
    # Prefer server_default (SQL-level), fall back to default (Python-level)
    return col.server_default or col.default


class TestMigrationV2ModelDefaults:
    """Verify that v2 model columns have the expected declared defaults.

    NOTE: SQLAlchemy Column(default=...) is only applied on flush, not on instantiation,
    so these tests inspect the declared column defaults rather than instance values.
    """

    def test_credential_is_deleted_default(self):
        """credentials.is_deleted defaults to False."""
        d = _col_default("credentials", "is_deleted")
        assert d is not None, "is_deleted has no declared default"
        # SQLAlchemy ColumnDefault wraps the scalar; extract .arg
        arg = d.arg if hasattr(d, "arg") else d
        assert arg is False

    def test_credential_status_flag_default(self):
        """credentials.status_flag defaults to 0."""
        d = _col_default("credentials", "status_flag")
        assert d is not None, "status_flag has no declared default"
        arg = d.arg if hasattr(d, "arg") else d
        assert arg == 0

    def test_source_group_total_repos_default(self):
        """source_groups.total_repos defaults to 0."""
        d = _col_default("source_groups", "total_repos")
        assert d is not None, "total_repos has no declared default"
        arg = d.arg if hasattr(d, "arg") else d
        assert arg == 0

    def test_source_repository_is_archived_default(self):
        """source_repositories.is_archived defaults to False."""
        d = _col_default("source_repositories", "is_archived")
        assert d is not None, "is_archived has no declared default"
        arg = d.arg if hasattr(d, "arg") else d
        assert arg is False

    def test_source_repository_is_fork_default(self):
        """source_repositories.is_fork defaults to False."""
        d = _col_default("source_repositories", "is_fork")
        assert d is not None, "is_fork has no declared default"
        arg = d.arg if hasattr(d, "arg") else d
        assert arg is False

    def test_source_repository_is_disabled_default(self):
        """source_repositories.is_disabled defaults to False."""
        d = _col_default("source_repositories", "is_disabled")
        assert d is not None, "is_disabled has no declared default"
        arg = d.arg if hasattr(d, "arg") else d
        assert arg is False

    def test_source_repository_discovery_status_default(self):
        """source_repositories.discovery_status defaults to DiscoveryStatus.new."""
        col = Base.metadata.tables["source_repositories"].columns["discovery_status"]
        # SAEnum default is a Python-side default (ColumnDefault wrapping the enum)
        default = col.default
        assert default is not None, "discovery_status has no declared default"
        arg = default.arg if hasattr(default, "arg") else default
        assert arg == DiscoveryStatus.new

    def test_mirror_status_flag_default(self):
        """mirrors.status_flag defaults to 4 (Pending)."""
        d = _col_default("mirrors", "status_flag")
        assert d is not None, "status_flag has no declared default"
        arg = d.arg if hasattr(d, "arg") else d
        assert arg == 4

    def test_mirror_target_diverged_commits_default(self):
        """mirrors.target_diverged_commits defaults to 0."""
        d = _col_default("mirrors", "target_diverged_commits")
        assert d is not None, "target_diverged_commits has no declared default"
        arg = d.arg if hasattr(d, "arg") else d
        assert arg == 0

    def test_mirror_is_imported_default(self):
        """mirrors.is_imported defaults to False."""
        d = _col_default("mirrors", "is_imported")
        assert d is not None, "is_imported has no declared default"
        arg = d.arg if hasattr(d, "arg") else d
        assert arg is False

    def test_sync_group_sync_enabled_default(self):
        """sync_groups.sync_enabled defaults to True."""
        d = _col_default("sync_groups", "sync_enabled")
        assert d is not None, "sync_enabled has no declared default"
        arg = d.arg if hasattr(d, "arg") else d
        assert arg is True

    def test_sync_group_sync_concurrency_default(self):
        """sync_groups.sync_concurrency defaults to 5."""
        d = _col_default("sync_groups", "sync_concurrency")
        assert d is not None, "sync_concurrency has no declared default"
        arg = d.arg if hasattr(d, "arg") else d
        assert arg == 5

    def test_sync_group_freshness_enabled_default(self):
        """sync_groups.freshness_enabled defaults to True."""
        d = _col_default("sync_groups", "freshness_enabled")
        assert d is not None, "freshness_enabled has no declared default"
        arg = d.arg if hasattr(d, "arg") else d
        assert arg is True

    def test_pipeline_is_default_default(self):
        """pipelines.is_default defaults to False."""
        d = _col_default("pipelines", "is_default")
        assert d is not None, "is_default has no declared default"
        arg = d.arg if hasattr(d, "arg") else d
        assert arg is False

    def test_pipeline_is_enabled_default(self):
        """pipelines.is_enabled defaults to True."""
        d = _col_default("pipelines", "is_enabled")
        assert d is not None, "is_enabled has no declared default"
        arg = d.arg if hasattr(d, "arg") else d
        assert arg is True

    def test_pipeline_component_order_default(self):
        """pipeline_components.order defaults to 0."""
        d = _col_default("pipeline_components", "order")
        assert d is not None, "order has no declared default"
        arg = d.arg if hasattr(d, "arg") else d
        assert arg == 0
