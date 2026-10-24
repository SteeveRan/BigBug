/**
 * @file variables.tf
 * @description Input variables for the infra-apps root.
 */

variable "kubeconfig_path" {
  description = "Path to kubeconfig of the target cluster"
  type        = string
  default     = "~/.kube/config"
}

variable "kubeconfig_context" {
  description = "kubeconfig context to use (kind-bigbug-dev for dev)"
  type        = string
  default     = "kind-bigbug-dev"
}

variable "cnpg_storage_size" {
  description = "CNPG cluster storage size (dev default)"
  type        = string
  default     = "5Gi"
}

variable "keycloak_hostname" {
  description = "External hostname of Keycloak (ingress host, ADR-0022 addressing)"
  type        = string
  default     = "keycloak.local"
}

variable "keycloak_admin_username" {
  description = "Keycloak bootstrap admin username (only used on first DB init)"
  type        = string
  default     = "admin"
}

variable "keycloak_admin_password" {
  description = "Keycloak bootstrap admin password (only used on first DB init)"
  type        = string
  default     = "admin"
}

# ── Keycloak config (modules/keycloak, migrated from config root — #57/#58) ──

variable "keycloak_url" {
  description = "Keycloak server URL (keycloakx in kind, https://keycloak.local — ADR-0030)"
  type        = string
  default     = "https://keycloak.local"
}

variable "realm_name" {
  description = "Keycloak realm name"
  type        = string
  default     = "bigbug"
}

variable "backend_client_id" {
  description = "OIDC client ID for BigBug backend"
  type        = string
  default     = "bigbug-backend"
}

variable "backend_client_secret" {
  description = "OIDC client secret for BigBug backend"
  type        = string
  sensitive   = true
  default     = "bigbug-backend-secret"
}

variable "frontend_client_id" {
  description = "OIDC client ID for BigBug frontend (SPA)"
  type        = string
  default     = "bigbug-frontend"
}

variable "frontend_redirect_uris" {
  description = "Valid redirect URIs for frontend SPA client"
  type        = list(string)
  default     = ["http://localhost:5173/*", "http://localhost:3000/*"]
}

variable "harbor_client_id" {
  description = "OIDC client ID for Harbor (created in Keycloak)"
  type        = string
  default     = "harbor"
}

variable "harbor_client_secret" {
  description = "OIDC client secret for Harbor (created in Keycloak)"
  type        = string
  sensitive   = true
  default     = "harbor-oidc-secret"
}

variable "harbor_redirect_uris" {
  description = "Valid redirect URIs for Harbor OIDC client (https, no :30443 — ADR-0030 §8)"
  type        = list(string)
  default     = ["https://harbor.local/c/oidc/callback", "https://harbor.local/*"]
}

variable "harbor_post_logout_redirect_uris" {
  description = "Post-logout redirect URIs for Harbor OIDC client"
  type        = list(string)
  default     = ["https://harbor.local/c/oidc/logout", "https://harbor.local/"]
}

variable "harbor_root_url" {
  description = "Root URL for Harbor OIDC client"
  type        = string
  default     = "https://harbor.local"
}

variable "test_user_username" {
  description = "Test user username in Keycloak"
  type        = string
  default     = "bigbug"
}

variable "test_user_password" {
  description = "Test user password in Keycloak"
  type        = string
  sensitive   = true
  default     = "bigbug"
}

variable "test_user_email" {
  description = "Test user email in Keycloak"
  type        = string
  default     = "bigbug@example.com"
}

# ── GitLab base setup (config root merged 2026-10-23, ADR-0033) ──────────────

variable "gitlab_url" {
  description = "GitLab instance URL (https omnibus — ADR-0030 §9)"
  type        = string
  default     = "https://gitlab.local:8443"
}

variable "gitlab_ca_cert" {
  description = "Path to the stand CA (kind/certs.sh → ~/.local/state/bigbug/certs/ca.crt, ADR-0030 §2 rev #62). Absolute default — shared per machine"
  type        = string
  default     = "~/.local/state/bigbug/certs/ca.crt"
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
  description = "Password for the backend service account. Leave null to auto-generate (random_password, persisted in state)"
  type        = string
  sensitive   = true
  default     = null
}
