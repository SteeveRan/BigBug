/**
 * @file variables.tf
 * @description Root module input variables — GitLab only (ADR-0033).
 *
 * Keycloak/Harbor variables moved to terraform/apps/variables.tf
 * (ADR-0029 update #58).
 */

# ═══════════════════════════════════════════════════════════════════════════════
# GitLab
# ═══════════════════════════════════════════════════════════════════════════════

variable "gitlab_url" {
  description = "GitLab instance URL (https omnibus — ADR-0030 §9)"
  type        = string
  default     = "https://gitlab.local:8443"
}

variable "gitlab_ca_cert" {
  description = "Path to GitLab TLS cert (self-signed from kind/certs.sh, ADR-0030); resolved relative to this root dir"
  type        = string
  default     = "../../kind/certs/gitlab.local/tls.crt"
}

variable "gitlab_token" {
  description = "GitLab root personal access token for provider authentication"
  type        = string
  sensitive   = true
}

variable "mirrors_group_name" {
  description = "GitLab group name for mirror repositories"
  type        = string
  default     = "bigbug-mirrors"
}

variable "backend_user_name" {
  description = "Display name for the backend service account user"
  type        = string
  default     = "BigBug Backend"
}

variable "backend_user_username" {
  description = "Username for the backend service account"
  type        = string
  default     = "bigbug-backend"
}

variable "backend_user_email" {
  description = "Email for the backend service account"
  type        = string
  default     = "bigbug-backend@localhost.localdomain"
}

variable "backend_user_password" {
  description = "Password for the backend service account (auto-generated if null)"
  type        = string
  sensitive   = true
  default     = null
}
