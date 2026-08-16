"""
Vulture whitelist — подтверждённые ложные срабатывания для backend BigBug.

Этот файл передаётся vulture как дополнительный модуль (см.
backend/scripts/vulture.sh). Каждая группа снабжена обоснованием, ПОЧЕМУ
это ложное срабатывание: vulture не видит использование через
FastAPI-декораторы, Pydantic-сериализацию, SQLAlchemy-маппинг и
pydantic-settings.

Находки, которых здесь НЕТ, — реальные кандидаты в мёртвый код (см. отчёт).
"""


class Whitelist:
    """Хелпер для синтаксически корректного доступа к мок-объектам."""

    def __getattr__(self, _):
        pass


_ = Whitelist()


# Pydantic schema field/class/validator (serialization)
access_token
architectures_a
architectures_b
BuildLogOut
by_gitlab_instance
by_sync_group
collected_at
differing_tags
digest_a
digest_b
exists
_.has_credential
_._mask_secret
matching_tags
members_count
mirror_count
MirrorDuplicateCheckOut
MirrorDuplicateCheck
MirrorLogCreate
_.mirrors_count
my_role
note
only_in_a
only_in_b
realm
release_body
release_name
release_tag
RoleOut
signed
size_bytes_a
size_bytes_b
SourceGroupCreate
SourceGroupUpdate
success
taget_path
team_name
token_type
total_groups
total_mirrors
total_tags
users_count
_._validate_by_registry
_._validate_config_deny
_._validate
_._validate_visibility

# SQLAlchemy column/relationship/property (ORM)
app_image
app_version
assigned_at
build_logs
build_schedules
built_at
chart_url
commits_behind
cosign_signature
detected_at
discovered_at
dockerfile
docker_image_source
duration_ms
finished_at
github_created_at
github_id
github_pushed_at
github_updated_at
gitlab_pipeline_url
gitlab_project_url
gold_image
helm_chart_source
homepage_url
import_
is_disabled
is_draft
is_fork
is_imported
is_private
is_signed
is_stale
last_checked_at
last_commit_message
last_freshness_check_at
last_freshness_status
last_known_commit_author
last_known_commit_date
last_run_at
last_seen_at
last_synced_at
last_sync_status
last_tested_at
latest_prerelease_date
latest_prerelease_url
latest_release_date
latest_release_url
license_text
log_output
mirrored_repos
org_id
os_family
pipeline_components
pipeline_runs
readme_md
release_logs
removed
role_scopes
sha256_digest
source_commit_date
source_created_at
source_pushed_at
source_updated_at
stars_count
sync_logs
sync_schedules
target_extra_commits
_.team_name
total_repos
triggered_by_user_id
trigger_type
urls
vulnerabilities
vulnerability_severity

# ORM attribute write, serialized via Pydantic from_attributes
_.app_version
_.built_at
_.chart_url
_.cosign_signature
_.finished_at
_.github_created_at
_.github_id
_.github_pushed_at
_.github_updated_at
_.homepage_url
_.is_disabled
_.is_draft
_.is_fork
_.is_private
_.is_signed
_.last_checked_at
_.last_commit_message
_.last_freshness_check_at
_.last_freshness_status
_.last_known_commit_author
_.last_known_commit_date
_.last_run_at
_.last_seen_at
_.last_synced_at
_.last_tested_at
_.latest_prerelease_date
_.latest_prerelease_url
_.latest_release_date
_.latest_release_url
_.log_output
_.readme_md
_.source_created_at
_.source_pushed_at
_.source_updated_at
_.stars_count
_.urls
_.users_count
_.vulnerabilities
_.vulnerability_severity

# Pydantic response field (AnalyzeImageResponse)
compatible_registries
detected_provider
detected_registry_host
is_new_registry_needed
normalized_image
suggested_registry

# pydantic-settings field/property/validator
default_stale_threshold_days
keycloak_client_id
keycloak_client_secret
keycloak_frontend_client_id
_.keycloak_jwks_url
_.keycloak_openid_config_url
keycloak_public_url
_.keycloak_token_url
rate_limit_global
redis_url
_.validate_database_url

# Pydantic v2 / pydantic-settings model_config
model_config

# FastAPI/pydantic framework usage
provider_url
scanned_at

