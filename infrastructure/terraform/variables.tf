/**
 * @file variables.tf
 * @description Root module input variables — covers all three sub-modules
 *              (Keycloak, Harbor, GitLab).
 */

# ═══════════════════════════════════════════════════════════════════════════════
# Keycloak
# ═══════════════════════════════════════════════════════════════════════════════

variable "keycloak_url" {
  description = "Keycloak server URL"
  type        = string
  default     = "http://localhost:8180"
}

variable "keycloak_admin_username" {
  description = "Keycloak admin username"
  type        = string
  default     = "admin"
}

variable "keycloak_admin_password" {
  description = "Keycloak admin password"
  type        = string
  sensitive   = true
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

# Harbor OIDC client (created in Keycloak, consumed by Harbor module)

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
  description = "Valid redirect URIs for Harbor OIDC client"
  type        = list(string)
  default     = ["https://harbor.local:30443/c/oidc/callback", "https://harbor.local:30443/*"]
}

variable "harbor_post_logout_redirect_uris" {
  description = "Post-logout redirect URIs for Harbor OIDC client"
  type        = list(string)
  default     = ["https://harbor.local:30443/c/oidc/logout", "https://harbor.local:30443/"]
}

variable "harbor_root_url" {
  description = "Root URL for Harbor OIDC client"
  type        = string
  default     = "https://harbor.local:30443"
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

# ═══════════════════════════════════════════════════════════════════════════════
# Harbor
# ═══════════════════════════════════════════════════════════════════════════════

variable "harbor_url" {
  description = "Harbor instance URL"
  type        = string
  default     = "https://harbor.local"
}

variable "harbor_username" {
  description = "Harbor admin username"
  type        = string
  default     = "admin"
}

variable "harbor_password" {
  description = "Harbor admin password"
  type        = string
  sensitive   = true
  default     = "Harbor12345"
}

# Harbor OIDC
# Note: oidc_client_id and oidc_client_secret come from Keycloak outputs,
# but we accept them as variables here so they can be set in terraform.tfvars
# and passed to both modules consistently.

variable "harbor_auth_mode" {
  description = "Harbor authentication mode (oidc_auth | db_auth)"
  type        = string
  default     = "oidc_auth"
}

variable "harbor_oidc_provider_name" {
  description = "OIDC provider display name in Harbor"
  type        = string
  default     = "Keycloak"
}

variable "harbor_oidc_endpoint" {
  description = "OIDC provider endpoint URL"
  type        = string
  default     = "http://localhost:8180/realms/bigbug"
}

variable "harbor_oidc_groups_claim" {
  description = "OIDC claim for groups"
  type        = string
  default     = "groups"
}

variable "harbor_oidc_scope" {
  description = "OIDC scope"
  type        = string
  default     = "openid,profile,email,groups"
}

variable "harbor_oidc_verify_cert" {
  description = "Verify OIDC provider certificate"
  type        = bool
  default     = false
}

variable "harbor_oidc_auto_onboard" {
  description = "Automatically create users on first OIDC login"
  type        = bool
  default     = true
}

variable "harbor_oidc_user_claim" {
  description = "OIDC claim for username"
  type        = string
  default     = "preferred_username"
}

# Harbor Projects

variable "gold_images_project_name" {
  description = "Harbor project name for gold images"
  type        = string
  default     = "gold-images"
}

variable "gold_images_storage_quota" {
  description = "Storage quota in GB for gold-images project (-1 = unlimited)"
  type        = number
  default     = -1
}

variable "app_images_project_name" {
  description = "Harbor project name for app images"
  type        = string
  default     = "app-images"
}

variable "app_images_storage_quota" {
  description = "Storage quota in GB for app-images project (-1 = unlimited)"
  type        = number
  default     = -1
}

variable "mirrors_project_name" {
  description = "Harbor project name for mirrors"
  type        = string
  default     = "mirrors"
}

variable "mirrors_storage_quota" {
  description = "Storage quota in GB for mirrors project (-1 = unlimited)"
  type        = number
  default     = -1
}

# Harbor Registries

variable "dockerhub_registry_name" {
  description = "Display name for Docker Hub registry in Harbor"
  type        = string
  default     = "docker-hub"
}

variable "dockerhub_endpoint_url" {
  description = "Docker Hub endpoint URL"
  type        = string
  default     = "https://hub.docker.com"
}

variable "quay_registry_name" {
  description = "Display name for Quay.io registry in Harbor"
  type        = string
  default     = "quay-io"
}

variable "quay_endpoint_url" {
  description = "Quay.io endpoint URL"
  type        = string
  default     = "https://quay.io"
}

# Harbor Replication

variable "replication_schedule" {
  description = "Cron schedule for replication policies"
  type        = string
  default     = "0 0 2 * * *"
}

# Harbor Webhooks

variable "webhook_backend_url" {
  description = "BigBug backend webhook URL"
  type        = string
  default     = "http://localhost:8000/api/webhooks/harbor"
}

# ═══════════════════════════════════════════════════════════════════════════════
# GitLab
# ═══════════════════════════════════════════════════════════════════════════════

variable "gitlab_url" {
  description = "GitLab instance URL"
  type        = string
  default     = "http://localhost:8080"
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

variable "backend_token_name" {
  description = "Name for the backend PAT"
  type        = string
  default     = "bigbug-backend-token"
}

variable "backend_token_expires_at" {
  description = "Expiration date for backend PAT (ISO 8601 format)"
  type        = string
  default     = "2027-12-31"
}

variable "backend_token_scopes" {
  description = "Scopes for the backend PAT"
  type        = list(string)
  default     = ["api", "read_repository", "write_repository"]
}
