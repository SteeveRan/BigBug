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
  gitlab_project_id: string | null;
  gitlab_project_url: string | null;
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
}

export interface DockerRegistryInstanceUpdate {
  name?: string | null;
  url?: string | null;
  username?: string | null;
  password?: string | null;
  is_active?: boolean | null;
  verify_ssl?: boolean | null;
  is_default?: boolean | null;
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
