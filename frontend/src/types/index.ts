export interface GithubOrg {
  id: number
  login: string
  type: string
  avatar_url: string | null
  github_id: number | null
}

export interface GithubRelease {
  id: number
  tag_name: string
  name: string | null
  is_prerelease: boolean
  is_draft: boolean
  published_at: string | null
}

export interface GithubProject {
  id: number
  org_id: number
  org: GithubOrg
  name: string
  full_name: string
  github_url: string
  description: string | null
  custom_description: string | null
  readme_md: string | null
  default_branch: string
  homepage_url: string | null
  license_spdx: string | null
  license_name: string | null
  is_archived: boolean
  is_fork: boolean
  is_stale: boolean
  stale_threshold_days: number
  last_synced_at: string | null
  github_created_at: string | null
  github_updated_at: string | null
  github_pushed_at: string | null
  created_at: string
  updated_at: string
}

export interface GitlabMirror {
  id: number
  project_id: number
  gitlab_project_id: string | null
  gitlab_namespace: string | null
  gitlab_url: string
  gitlab_name: string | null
  mirrored_branch: string
  last_synced_release_tag: string | null
  last_sync_at: string | null
  status_flag: number
  status_text: string | null
  is_imported: boolean
  created_at: string
  updated_at: string
}

export interface SyncLog {
  id: number
  mirror_id: number
  pipeline_id: string | null
  pipeline_url: string | null
  status_flag: number
  status_text: string | null
  log_output: string | null
  triggered_by: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string
}

export interface SyncSchedule {
  id: number
  mirror_id: number
  cron_expression: string | null
  is_enabled: boolean
  use_default_schedule: boolean
  next_run_at: string | null
  last_run_at: string | null
}

export interface GoldImage {
  id: number
  name: string
  os_family: string
  description: string | null
  dockerfile: string | null
  gitlab_project_id: string | null
  gitlab_project_url: string | null
  created_at: string
  updated_at: string
}

export interface AppImage {
  id: number
  project_id: number | null
  gold_image_id: number | null
  name: string
  description: string | null
  dockerfile: string | null
  gitlab_project_id: string | null
  gitlab_project_url: string | null
  created_at: string
  updated_at: string
}

export interface ImageVersion {
  id: number
  image_type: 'gold' | 'app'
  gold_image_id: number | null
  app_image_id: number | null
  version_tag: string
  arch: string
  registry_url: string | null
  sha256_digest: string | null
  cosign_signature: string | null
  is_signed: boolean
  status_flag: number
  status_text: string | null
  built_at: string | null
  created_at: string
}

export interface BuildLog {
  id: number
  image_version_id: number
  pipeline_id: string | null
  pipeline_url: string | null
  status_flag: number
  status_text: string | null
  log_output: string | null
  triggered_by: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string
}

export interface User {
  id: number
  username: string
  email: string
  is_active: boolean
  roles: string[]
}

// Status flag constants
export const STATUS_FLAG = {
  OK: 0,
  FAILED: 1,
  WARNING: 2,
  IN_PROGRESS: 3,
  PENDING: 4,
} as const

export type StatusFlag = (typeof STATUS_FLAG)[keyof typeof STATUS_FLAG]
