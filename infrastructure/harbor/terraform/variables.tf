/**
 * @file variables.tf
 * @description Input variables for the Harbor OpenTofu configuration.
 */

# ─── Harbor Connection ───────────────────────────────────────────────────────

variable "harbor_url" {
  description = "Harbor instance URL (e.g. https://harbor.local)"
  type        = string
  default     = "https://harbor.local"
}

variable "harbor_username" {
  description = "Harbor admin username"
  type        = string
  default     = "admin"
  sensitive   = true
}

variable "harbor_password" {
  description = "Harbor admin password"
  type        = string
  sensitive   = true
}

# ─── OIDC / Keycloak Integration ─────────────────────────────────────────────

variable "auth_mode" {
  description = "Harbor authentication mode (db_auth or oidc_auth)"
  type        = string
  default     = "oidc_auth"
}

variable "oidc_provider_name" {
  description = "OIDC provider display name"
  type        = string
  default     = "Keycloak"
}

variable "oidc_endpoint" {
  description = "OIDC provider endpoint URL (e.g. http://172.17.0.1:8180/realms/bigbug)"
  type        = string
  default     = "http://localhost:8180/realms/bigbug"
}

variable "oidc_client_id" {
  description = "OIDC client ID (from Keycloak → Clients → harbor)"
  type        = string
  default     = "harbor"
}

variable "oidc_client_secret" {
  description = "OIDC client secret (from Keycloak → Clients → harbor → Credentials)"
  type        = string
  sensitive   = true
}

variable "oidc_groups_claim" {
  description = "OIDC groups claim name"
  type        = string
  default     = "groups"
}

variable "oidc_scope" {
  description = "OIDC scopes requested"
  type        = string
  default     = "openid,profile,email,groups"
}

variable "oidc_verify_cert" {
  description = "Verify OIDC provider certificate (disable for local dev)"
  type        = bool
  default     = false
}

variable "oidc_auto_onboard" {
  description = "Automatically create users on first OIDC login"
  type        = bool
  default     = true
}

variable "oidc_user_claim" {
  description = "OIDC claim to use as Harbor username"
  type        = string
  default     = "preferred_username"
}

# ─── Projects ────────────────────────────────────────────────────────────────

variable "gold_images_project_name" {
  description = "Gold images project name"
  type        = string
  default     = "gold-images"
}

variable "gold_images_storage_quota" {
  description = "Storage quota for gold-images project in GB (-1 = unlimited)"
  type        = number
  default     = -1
}

variable "app_images_project_name" {
  description = "App images project name"
  type        = string
  default     = "app-images"
}

variable "app_images_storage_quota" {
  description = "Storage quota for app-images project in GB (-1 = unlimited)"
  type        = number
  default     = -1
}

variable "mirrors_project_name" {
  description = "Mirrors project name"
  type        = string
  default     = "mirrors"
}

variable "mirrors_storage_quota" {
  description = "Storage quota for mirrors project in GB (-1 = unlimited)"
  type        = number
  default     = -1
}

# ─── Replication ─────────────────────────────────────────────────────────────

variable "dockerhub_registry_name" {
  description = "Name for Docker Hub registry entry in Harbor"
  type        = string
  default     = "docker-hub"
}

variable "dockerhub_endpoint_url" {
  description = "Docker Hub registry endpoint URL"
  type        = string
  default     = "https://hub.docker.com"
}

variable "quay_registry_name" {
  description = "Name for Quay.io registry entry in Harbor"
  type        = string
  default     = "quay-io"
}

variable "quay_endpoint_url" {
  description = "Quay.io registry endpoint URL"
  type        = string
  default     = "https://quay.io"
}

variable "replication_schedule" {
  description = "Cron schedule for replication policies (6-field cron: sec min hour day month weekday)"
  type        = string
  default     = "0 0 2 * * *"
}

# ─── Webhooks ────────────────────────────────────────────────────────────────

variable "webhook_backend_url" {
  description = "BigBug backend webhook receiver URL"
  type        = string
  default     = "http://localhost:8000/api/webhooks/harbor"
}
