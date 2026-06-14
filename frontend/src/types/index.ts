/** @deprecated Используй SourceGroup/SourceRepository из Git Mirroring V2 */
export interface GithubOrg {
  id: number;
  login: string;
  type: string;
  avatar_url: string | null;
  github_id: number | null;
}

export interface GithubRelease {
  id: number;
  tag_name: string;
  name: string | null;
  is_prerelease: boolean;
  is_draft: boolean;
  published_at: string | null;
}

/** @deprecated Используй SourceGroup/SourceRepository из Git Mirroring V2 */
export interface GithubProject {
  id: number;
  org_id: number;
  org: GithubOrg;
  name: string;
  full_name: string;
  github_url: string;
  description: string | null;
  custom_description: string | null;
  readme_md: string | null;
  default_branch: string;
  homepage_url: string | null;
  license_spdx: string | null;
  license_name: string | null;
  is_archived: boolean;
  is_fork: boolean;
  is_stale: boolean;
  stale_threshold_days: number;
  last_synced_at: string | null;
  github_created_at: string | null;
  github_updated_at: string | null;
  github_pushed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface GitlabMirror {
  id: number;
  project_id: number;
  gitlab_project_id: string | null;
  gitlab_namespace: string | null;
  gitlab_url: string;
  gitlab_name: string | null;
  mirrored_branch: string;
  last_synced_release_tag: string | null;
  last_sync_at: string | null;
  status_flag: number;
  status_text: string | null;
  is_imported: boolean;
  created_at: string;
  updated_at: string;
}

export interface SyncLog {
  id: number;
  mirror_id: number;
  pipeline_id: string | null;
  pipeline_url: string | null;
  status_flag: number;
  status_text: string | null;
  log_output: string | null;
  triggered_by: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface SyncSchedule {
  id: number;
  mirror_id: number;
  cron_expression: string | null;
  is_enabled: boolean;
  use_default_schedule: boolean;
  next_run_at: string | null;
  last_run_at: string | null;
}

export interface GoldImage {
  id: number;
  name: string;
  os_family: string;
  description: string | null;
  dockerfile: string | null;
  gitlab_project_id: string | null;
  gitlab_project_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface AppImage {
  id: number;
  project_id: number | null;
  gold_image_id: number | null;
  name: string;
  description: string | null;
  dockerfile: string | null;
  gitlab_project_id: string | null;
  gitlab_project_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface ImageVersion {
  id: number;
  image_type: 'gold' | 'app';
  gold_image_id: number | null;
  app_image_id: number | null;
  version_tag: string;
  arch: string;
  registry_url: string | null;
  sha256_digest: string | null;
  cosign_signature: string | null;
  is_signed: boolean;
  status_flag: number;
  status_text: string | null;
  vulnerabilities?: number | null;
  vulnerability_severity?: string | null;
  built_at: string | null;
  created_at: string;
}

export interface BuildLog {
  id: number;
  image_version_id: number;
  pipeline_id: string | null;
  pipeline_url: string | null;
  status_flag: number;
  status_text: string | null;
  log_output: string | null;
  triggered_by: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface User {
  id: number;
  username: string;
  email: string;
  is_active: boolean;
  roles: string[];
}

// Status flag constants
export const STATUS_FLAG = {
  OK: 0,
  FAILED: 1,
  WARNING: 2,
  IN_PROGRESS: 3,
  PENDING: 4,
} as const;

export type StatusFlag = (typeof STATUS_FLAG)[keyof typeof STATUS_FLAG];

// ──── Helm Chart Types ─────────────────────────────────────────────────────

export interface HelmChartSource {
  id: number;
  name: string;
  repo_url: string;
  description: string | null;
  gitlab_project_id: string | null;
  gitlab_project_url: string | null;
  last_synced_at: string | null;
  status_flag: number;
  status_text: string | null;
  created_at: string;
  updated_at: string;
}

export interface HelmChartSourceDetail extends HelmChartSource {
  versions: HelmChartVersion[];
}

export interface HelmChartVersion {
  id: number;
  source_id: number;
  chart_name: string;
  version: string;
  app_version: string | null;
  description: string | null;
  digest: string | null;
  chart_url: string | null;
  is_synced: boolean;
  status_flag: number;
  status_text: string | null;
  last_synced_at: string | null;
  created_at: string;
}

export interface HelmSyncLog {
  id: number;
  source_id: number;
  pipeline_id: string | null;
  pipeline_url: string | null;
  status_flag: number;
  status_text: string | null;
  log_output: string | null;
  triggered_by: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

// ──── Docker Image Types ───────────────────────────────────────────────────

export interface DockerImageSource {
  id: number;
  name: string;
  registry_url: string;
  description: string | null;
  registry_instance_id: number | null;
  registry_instance: DockerRegistryInstance | null;
  gitlab_project_id: string | null;
  gitlab_project_url: string | null;
  target_registry_url?: string | null;
  target_project?: string | null;
  last_synced_at: string | null;
  status_flag: number;
  status_text: string | null;
  created_at: string;
  updated_at: string;
}

export interface DockerImageSourceDetail extends DockerImageSource {
  tags: DockerImageTag[];
}

export interface DockerImageTag {
  id: number;
  source_id: number;
  image_name: string;
  tag: string;
  digest: string | null;
  size_bytes: number | null;
  architectures: string | null;
  is_synced: boolean;
  status_flag: number;
  status_text: string | null;
  last_synced_at: string | null;
  created_at: string;
}

export interface DockerSyncLog {
  id: number;
  source_id: number;
  pipeline_id: string | null;
  pipeline_url: string | null;
  status_flag: number;
  status_text: string | null;
  log_output: string | null;
  triggered_by: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface DockerSyncSchedule {
  id: number;
  sync_type: string;
  docker_image_source_id: number;
  cron_expression: string | null;
  is_enabled: boolean;
  use_default_schedule: boolean;
  next_run_at: string | null;
  last_run_at: string | null;
  created_at: string;
  updated_at: string;
}

// ──── RBAC Types ───────────────────────────────────────────────────────────

/** Одно право доступа (например, "mirrors:read", "helm:write") */
export interface Permission {
  id: number;
  name: string;
  description: string | null;
}

/** Роль с привязанными permissions */
export interface Role {
  id: number;
  name: string;
  description: string | null;
  is_custom: boolean;
  created_by_user_id: number | null;
  permissions: Permission[];
  /** Number of users assigned to this role */
  users_count?: number;
  /** Scope: IDs of source groups this role can access */
  source_group_ids?: number[];
  /** Scope: IDs of credentials this role can access */
  credential_ids?: number[];
  /** Scope: IDs of sync groups this role can access */
  sync_group_ids?: number[];
}

/** Ответ от GET /api/auth/me/permissions */
export interface UserPermissions {
  user_id: number;
  role: string;
  permissions: string[];
}

/** Данные для создания новой роли */
export interface RoleCreate {
  name: string;
  description?: string | null;
  permission_names: string[];
}

/** Данные для обновления существующей роли */
export interface RoleUpdate {
  name?: string | null;
  description?: string | null;
  permission_names?: string[] | null;
}

/** Scope assigned to a role (full read representation) */
export interface RoleScope {
  source_group_ids: number[];
  credential_ids: number[];
  sync_group_ids: number[];
}

/** Request to replace role scope for a given scope type */
export interface RoleScopeUpdate {
  source_group_ids?: number[];
  credential_ids?: number[];
  sync_group_ids?: number[];
}

/** Single scope item add/remove */
export interface ScopeItemRequest {
  source_group_id?: number;
  credential_id?: number;
  sync_group_id?: number;
}

// ──── Integration Instance Types ────────────────────────────────────────────

/** Result of a POST /test connection check */
export interface ConnectionTestResult {
  success: boolean;
  message: string;
  status_code: number | null;
}

// ── GitLab Instance ─────────────────────────────────────────────────────────

export interface GitlabInstance {
  id: number;
  name: string;
  url: string;
  is_active: boolean;
  verify_ssl: boolean;
  is_default: boolean;
  default_group_id: number | null;
  status_flag: number;
  status_text: string;
  last_checked_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface GitlabInstanceCreate {
  name: string;
  url: string;
  token?: string | null;
  is_active?: boolean;
  verify_ssl?: boolean;
  is_default?: boolean;
  default_group_id?: number | null;
}

export interface GitlabInstanceUpdate {
  name?: string | null;
  url?: string | null;
  token?: string | null;
  is_active?: boolean | null;
  verify_ssl?: boolean | null;
  is_default?: boolean | null;
  default_group_id?: number | null;
}

// ── Harbor Instance ─────────────────────────────────────────────────────────

export interface HarborInstance {
  id: number;
  name: string;
  url: string;
  username: string;
  is_active: boolean;
  verify_ssl: boolean;
  is_default: boolean;
  default_project: string | null;
  status_flag: number;
  status_text: string;
  last_checked_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface HarborInstanceCreate {
  name: string;
  url: string;
  username: string;
  password?: string | null;
  is_active?: boolean;
  verify_ssl?: boolean;
  is_default?: boolean;
  default_project?: string | null;
}

export interface HarborInstanceUpdate {
  name?: string | null;
  url?: string | null;
  username?: string | null;
  password?: string | null;
  is_active?: boolean | null;
  verify_ssl?: boolean | null;
  is_default?: boolean | null;
  default_project?: string | null;
}

// ── GitHub Instance ─────────────────────────────────────────────────────────

export interface GithubInstance {
  id: number;
  name: string;
  is_active: boolean;
  is_default: boolean;
  status_flag: number;
  status_text: string;
  last_checked_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface GithubInstanceCreate {
  name: string;
  token?: string | null;
  is_active?: boolean;
  is_default?: boolean;
}

export interface GithubInstanceUpdate {
  name?: string | null;
  token?: string | null;
  is_active?: boolean | null;
  is_default?: boolean | null;
}

// ── Docker Registry Instance ─────────────────────────────────────────────────

export interface DockerRegistryInstance {
  id: number;
  name: string;
  url: string;
  username: string | null;
  is_active: boolean;
  verify_ssl: boolean;
  is_default: boolean;
  registry_type: 'internal' | 'external';
  registry_provider:
    | 'docker_hub'
    | 'quay_io'
    | 'gcr'
    | 'ecr'
    | 'acr'
    | 'ghcr'
    | 'harbor'
    | 'generic';
  priority: number;
  status_flag: number;
  status_text: string;
  last_checked_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface DockerRegistryInstanceCreate {
  name: string;
  url: string;
  username?: string | null;
  password?: string | null;
  is_active?: boolean;
  verify_ssl?: boolean;
  is_default?: boolean;
  registry_type?: string;
  registry_provider?: string;
  priority?: number;
}

export interface DockerRegistryInstanceUpdate {
  name?: string | null;
  url?: string | null;
  username?: string | null;
  password?: string | null;
  is_active?: boolean | null;
  verify_ssl?: boolean | null;
  is_default?: boolean | null;
  registry_type?: string | null;
  registry_provider?: string | null;
  priority?: number | null;
}

// ── Helm Repository Instance ─────────────────────────────────────────────────

export interface HelmRepositoryInstance {
  id: number;
  name: string;
  url: string;
  username: string | null;
  is_active: boolean;
  verify_ssl: boolean;
  is_default: boolean;
  status_flag: number;
  status_text: string;
  last_checked_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface HelmRepositoryInstanceCreate {
  name: string;
  url: string;
  username?: string | null;
  password?: string | null;
  is_active?: boolean;
  verify_ssl?: boolean;
  is_default?: boolean;
}

export interface HelmRepositoryInstanceUpdate {
  name?: string | null;
  url?: string | null;
  username?: string | null;
  password?: string | null;
  is_active?: boolean | null;
  verify_ssl?: boolean | null;
  is_default?: boolean | null;
}

// ──── OIDC Configuration Types ─────────────────────────────────────────────

export interface OIDCConfig {
  id: number;
  issuer_url: string;
  client_id: string;
  client_secret: string; // будет "********" в ответе
  frontend_client_id: string;
  enabled: boolean;
  public_url: string | null;
  role_mapping: Record<string, string>;
  created_at: string;
  updated_at: string;
}

export interface OIDCConfigUpdate {
  issuer_url?: string;
  client_id?: string;
  client_secret?: string;
  frontend_client_id?: string;
  enabled?: boolean;
  public_url?: string | null;
  role_mapping?: Record<string, string>;
}

// ──── Pipeline Run Types ──────────────────────────────────────────────────

export interface PipelineRun {
  id: number;
  gitlab_instance_id: number;
  gitlab_project_id: number;
  gitlab_pipeline_id: number | null;
  triggered_by_user_id: number | null;
  trigger_type: 'manual' | 'scheduled' | 'webhook';
  ref: string;
  variables: Record<string, string>;
  status_flag: number; // 0=OK, 1=Failed, 3=Running, 4=Pending
  status_text: string;
  duration: number | null;
  web_url: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface PipelineRunCreate {
  gitlab_instance_id: number;
  gitlab_project_id: number;
  ref: string;
  variables?: Record<string, string>;
}

export interface PipelineRunList {
  items: PipelineRun[];
  total: number;
  page: number;
  page_size: number;
}

// ──── GitLab Component Types ──────────────────────────────────────────────

export interface GitLabComponent {
  id: number;
  name: string;
  description: string | null;
  gitlab_instance_id: number;
  project_path: string;
  component_path: string;
  version: string | null;
  inputs_schema: Record<string, unknown> | null;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface GitLabComponentCreate {
  name: string;
  description?: string;
  gitlab_instance_id: number;
  project_path: string;
  component_path: string;
  version?: string;
  inputs_schema?: Record<string, unknown>;
}

export interface GitLabComponentUpdate {
  name?: string;
  description?: string | null;
  gitlab_instance_id?: number;
  project_path?: string;
  component_path?: string;
  version?: string | null;
  inputs_schema?: Record<string, unknown> | null;
  is_enabled?: boolean;
}

// ──── Audit Log Types ────────────────────────────────────────────────────────

export interface AuditLog {
  id: number;
  user_id: number | null;
  username: string;
  action: string;
  resource_type: string;
  resource_id: number | null;
  resource_name: string | null;
  details: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

export interface AuditLogList {
  items: AuditLog[];
  total: number;
}

// ──── Vulnerability Scanning Types ──────────────────────────────────────────

export interface VulnerabilityScanResult {
  total: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  negligible?: number;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'none' | 'unknown' | null;
  message?: string;
}

export interface ScanRequest {
  harbor_instance_id: number;
  project_name: string;
  repository_name: string;
  artifact_digest: string;
}

// ──── Cosign Signing Types ────────────────────────────────────────────────────

export interface SignImageRequest {
  image_reference: string;
  cosign_private_key: string;
}

export interface VerifyImageRequest {
  image_reference: string;
  cosign_public_key: string;
}

export interface SignImageResult {
  signed: boolean;
  image: string;
  note?: string;
}

export interface VerifyImageResult {
  verified: boolean;
  image: string;
  error?: string;
}

// ──── Docker Image Compare Types ─────────────────────────────────────────────

export interface DockerImageTagCompareItem {
  tag: string;
  digest_a: string | null;
  digest_b: string | null;
  match: boolean | null;
  architectures_a: string | null;
  architectures_b: string | null;
  size_bytes_a: number | null;
  size_bytes_b: number | null;
}

export interface DockerImageCompareSummary {
  total_tags: number;
  matching_tags: number;
  differing_tags: number;
  only_in_a: number;
  only_in_b: number;
}

export interface DockerImageCompareResponse {
  source_a: DockerImageSource;
  source_b: DockerImageSource;
  tags: DockerImageTagCompareItem[];
  summary: DockerImageCompareSummary;
}

// ──── Docker Image Analysis ─────────────────────────────────────────────────

export interface AnalyzeImageResponse {
  image_name: string;
  normalized_image: string;
  detected_registry_host: string;
  detected_provider: string;
  suggested_registry: DockerRegistryInstance | null;
  compatible_registries: DockerRegistryInstance[];
  is_new_registry_needed: boolean;
}

// ============================================================
// Git Mirroring V2 Types
// ============================================================

export type ProviderType = 'github' | 'gitlab' | 'generic';

export interface Credential {
  id: number;
  name: string;
  credential_type: string;
  status_flag: number;
  status_text: string;
  created_at: string;
}

export interface SourceProvider {
  id: number;
  label: string;
  provider_type: ProviderType;
  credential_id: number | null;
  credential?: Credential;
  config_json?: Record<string, unknown>;
  status_flag: number;
  status_text: string;
  groups_count?: number;
  created_at: string;
  updated_at: string;
}

export interface SourceProviderCreate {
  label: string;
  provider_type: ProviderType;
  credential_id: number;
  config_json?: Record<string, unknown>;
}

export interface SourceProviderUpdate {
  label?: string;
  credential_id?: number;
  config_json?: Record<string, unknown>;
  status_flag?: number;
}

export interface SourceGroup {
  id: number;
  external_id: string;
  name: string;
  full_name: string;
  description?: string;
  avatar_url?: string;
  source_provider_id: number;
  source_provider?: SourceProvider;
  repositories_total: number;
  repositories_mirrored: number;
  new_repos_count?: number;
  created_at: string;
  updated_at: string;
}

export interface SourceRepository {
  id: number;
  external_id: string;
  name: string;
  full_name: string;
  description?: string;
  private: boolean;
  fork: boolean;
  archived: boolean;
  language?: string;
  default_branch: string;
  html_url: string;
  clone_url: string;
  stars: number;
  forks: number;
  source_group_id: number | null;
  source_group_name?: string;
  license_spdx?: string;
  license_name?: string;
  latest_release_tag?: string;
  latest_release_name?: string;
  latest_release_published_at?: string;
  discovery_status: number;
  discovery_status_text: string;
  has_readme: boolean;
  is_mirrored?: boolean;
  mirrors_count?: number;
  created_at: string;
  updated_at: string;
}

export interface SourceRepositoryCreate {
  provider_type: 'github' | 'gitlab' | 'generic';
  clone_url: string;
  source_group_id?: number;
  description?: string;
}

export interface SourceRepositoryReadme {
  repository_id: number;
  html?: string;
  markdown?: string;
  fetched_at?: string;
}

export interface SourceRepositoryRelease {
  id: number;
  release_tag: string;
  release_name?: string;
  release_body?: string;
  is_prerelease: boolean;
  published_at: string;
  html_url: string;
}

export interface Mirror {
  id: number;
  source_repository_id: number;
  source_repository?: SourceRepository;
  target_namespace: string;
  target_project_name: string;
  target_path: string;
  sync_group_id: number;
  sync_group_name?: string;
  target_gitlab_name?: string;
  status_flag: number;
  status_text: string;
  discovery_status: number;
  discovery_status_text: string;
  last_sync_at?: string;
  last_freshness_check_at?: string;
  is_active: boolean;
  is_imported?: boolean;
  created_at: string;
  updated_at: string;
}

export interface MirrorDetail extends Mirror {
  target_project_id?: string;
  target_web_url?: string;
  last_known_commit_sha?: string;
  last_known_commit_date?: string;
  last_known_commit_author?: string;
  target_diverged_commits?: number;
  last_sync_status?: string;
  last_freshness_status?: string;
  mirror_logs?: MirrorLog[];
  source_repository?: SourceRepository;
  sync_group?: SyncGroup;
}

export interface MirrorCreate {
  source_repository_id: number;
  target_namespace: string;
  target_project_name: string;
  sync_group_id: number;
}

export interface MirrorBulkCreate {
  mirrors: MirrorCreate[];
}

export interface MirrorUpdate {
  target_namespace?: string;
  target_project_name?: string;
  sync_group_id?: number;
  is_active?: boolean;
}

export interface ImportMirrorRequest {
  source_repository_id: number;
  target_namespace: string;
  target_project_name: string;
}

export interface MirrorLog {
  id: number;
  mirror_id: number;
  pipeline_run_id?: number;
  gitlab_pipeline_id?: string;
  gitlab_pipeline_url?: string;
  log_type: 'sync' | 'freshness' | 'integrity' | 'release' | 'import';
  status_flag: number;
  status_text: string;
  message?: string;
  details?: Record<string, unknown>;
  details_json?: Record<string, unknown>;
  source_commit_sha?: string;
  source_commit_date?: string;
  target_commit_sha?: string;
  commits_behind?: number;
  target_extra_commits?: number;
  started_at?: string;
  finished_at?: string;
  completed_at?: string;
  duration_ms?: number;
  triggered_by?: string;
  created_at: string;
}

export interface MirrorDuplicateCheck {
  duplicates: Array<{
    mirror_id: number;
    source_repo_id: number;
    source_url: string;
    target_path: string;
    sync_group_name: string;
  }>;
  accessible: Record<string, unknown>[];
  inaccessible: Record<string, unknown>[];
}

export interface MirrorFilters {
  source_group_id?: number;
  sync_group_id?: number;
  status_flag?: number;
  search?: string;
  limit?: number;
  offset?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

export interface SyncGroup {
  id: number;
  name: string;
  description?: string;
  pipeline_id: number | null;
  pipeline?: PipelineConfig | null;
  is_default: boolean;
  mirrors_count?: number;
  sync_cron: string | null;
  sync_enabled: boolean;
  sync_concurrency: number;
  freshness_cron: string | null;
  freshness_enabled: boolean;
  freshness_concurrency: number;
  created_at: string;
  updated_at: string;
}

export interface SyncGroupCreate {
  name: string;
  description?: string;
  pipeline_id?: number | null;
  sync_cron?: string | null;
  sync_enabled?: boolean;
  sync_concurrency?: number;
  freshness_cron?: string | null;
  freshness_enabled?: boolean;
  freshness_concurrency?: number;
}

export interface SyncGroupUpdate {
  name?: string;
  description?: string;
  pipeline_id?: number | null;
  sync_cron?: string | null;
  sync_enabled?: boolean;
  sync_concurrency?: number;
  freshness_cron?: string | null;
  freshness_enabled?: boolean;
  freshness_concurrency?: number;
}

// ──── Pipeline Configuration Types ─────────────────────────────────────────

export interface PipelineComponentRef {
  component_id: number;
  order?: number;
  overrides?: Record<string, unknown> | null;
}

export interface PipelineConfigComponent {
  id: number;
  pipeline_id: number;
  component_id: number;
  order: number;
  overrides: Record<string, unknown>;
  component?: GitLabComponent | null;
}

export interface PipelineConfig {
  id: number;
  name: string;
  description: string | null;
  gitlab_instance_id: number | null;
  ref: string | null;
  default_variables: Record<string, unknown> | null;
  is_default: boolean;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
  components: PipelineConfigComponent[];
  gitlab_instance?: GitlabInstance | null;
}

export interface PipelineConfigCreate {
  name: string;
  description?: string | null;
  gitlab_instance_id?: number | null;
  ref?: string | null;
  default_variables?: Record<string, unknown> | null;
  is_default?: boolean | null;
  is_enabled?: boolean;
  components?: PipelineComponentRef[] | null;
}

export interface PipelineConfigUpdate {
  description?: string | null;
  gitlab_instance_id?: number | null;
  ref?: string | null;
  default_variables?: Record<string, unknown> | null;
  is_default?: boolean | null;
  is_enabled?: boolean | null;
  components?: PipelineComponentRef[] | null;
}

export interface PipelineConfigDuplicateRequest {
  name: string;
}

export interface PipelineListItem {
  id: number;
  name: string;
  gitlab_instance_name: string | null;
  ref: string | null;
  is_default: boolean;
  is_enabled: boolean;
  components_count: number;
  sync_groups_count: number;
  created_at: string;
  updated_at: string;
}

// ──── Orphaned Mirrors Types ─────────────────────────────────────────────────

/** Причина, по которой зеркало стало осиротевшим */
export type OrphanReason =
  | 'provider_deleted'
  | 'credentials_invalid'
  | 'source_not_found'
  | 'target_manual_delete';

/** Осиротевшее зеркало */
export interface OrphanedMirror {
  mirror_id: number;
  mirror_name: string;
  source_url: string;
  target_path: string;
  sync_group_name: string | null;
  gitlab_instance_url: string;
  orphan_reason: OrphanReason;
  orphan_reason_text: string;
  detected_at: string;
}

/** Ответ API списка orphaned mirrors */
export interface OrphanedMirrorListResponse {
  items: OrphanedMirror[];
  total: number;
}

/** Запрос на переназначение orphaned зеркала в SyncGroup */
export interface OrphanedReassignRequest {
  sync_group_id: number;
}

/** Запрос на изменение target_path orphaned зеркала */
export interface OrphanedMoveTargetRequest {
  target_path: string;
}

/** Результат проверки целостности зеркала */
export interface IntegrityCheckResult {
  mirror_id: number;
  status: 'clean' | 'diverged' | 'corrupted';
  source_commit: string | null;
  target_commit: string | null;
  details: string[];
}

export interface LicenseReportItem {
  spdx: string;
  name: string;
  count: number;
  is_restricted: boolean;
  repositories: Array<{
    id: number;
    name: string;
    full_name: string;
  }>;
}

// ============================================================
// Git Mirroring Reports Types
// ============================================================

// ──── Duplicates Report ──────────────────────────────────────────────────

export interface DuplicateMirrorItem {
  mirror_id: number;
  source_url: string;
  target_gitlab_instance_name: string | null;
  target_path: string | null;
  status_flag: number;
  status_text: string | null;
  created_at: string;
  sync_group_name: string | null;
}

export interface DuplicateGroup {
  source_url: string;
  mirror_count: number;
  mirrors: DuplicateMirrorItem[];
}

export interface DuplicatesReport {
  warning: string;
  total_groups: number;
  total_mirrors: number;
  groups: DuplicateGroup[];
}

// ──── Storage Report ─────────────────────────────────────────────────────

export interface MirrorStorageItem {
  mirror_id: number;
  source_url: string;
  target_gitlab_instance_name: string | null;
  target_path: string | null;
  sync_group_name: string | null;
  repo_size_bytes: number | null;
  history_size_bytes: number | null;
  total_size_bytes: number | null;
  error: string | null;
  accessible: boolean;
}

export interface StorageSummary {
  key: string;
  repo_size_bytes: number;
  history_size_bytes: number;
  total_size_bytes: number;
}

export interface StorageReport {
  items: MirrorStorageItem[];
  by_gitlab_instance: StorageSummary[];
  by_sync_group: StorageSummary[];
  grand_total: StorageSummary | null;
  collected_at: string | null;
  is_stale: boolean;
  collection_status: 'idle' | 'in_progress' | 'complete' | 'error';
}

export interface StorageRefreshStatus {
  collection_status: string;
  message: string;
}

// ──── Status Report ──────────────────────────────────────────────────────

export interface StatusCountItem {
  status_flag: number;
  status_text: string;
  count: number;
  label: string;
}

export interface MirrorStatusItem {
  mirror_id: number;
  source_url: string;
  status_flag: number;
  status_text: string | null;
  target_path: string | null;
  sync_group_name: string | null;
}

export interface StatusReport {
  status_counts: StatusCountItem[];
  total_mirrors: number;
  ok_mirrors: MirrorStatusItem[];
  failed_mirrors: MirrorStatusItem[];
  warning_mirrors: MirrorStatusItem[];
  in_progress_mirrors: MirrorStatusItem[];
  pending_mirrors: MirrorStatusItem[];
}

// ──── Syncs Report ───────────────────────────────────────────────────────

export interface DailySyncsItem {
  date: string;
  total: number;
  successful: number;
  failed: number;
  stale: number;
}

export interface SyncGroupSyncsItem {
  sync_group_name: string;
  total: number;
  successful: number;
  failed: number;
  stale: number;
}

export interface TopSyncMirrorItem {
  mirror_id: number;
  source_url: string;
  taget_path: string | null;
  count: number;
}

export interface SyncsReport {
  period_start: string;
  period_end: string;
  daily: DailySyncsItem[];
  by_sync_group: SyncGroupSyncsItem[];
  top_by_syncs: TopSyncMirrorItem[];
  top_by_errors: TopSyncMirrorItem[];
}

// ──── Bulk Operations ────────────────────────────────────────────────────

export interface BulkOperationResultItem {
  mirror_id: number;
  success: boolean;
  message: string | null;
}

export interface BulkOperationResponse {
  operation: string;
  total: number;
  succeeded: number;
  failed: number;
  results: BulkOperationResultItem[];
}
