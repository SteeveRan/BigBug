/**
 * @file outputs.tf
 * @description Outputs for the apps root.
 */

output "keycloak_url" {
  description = "External Keycloak URL (ADR-0022 addressing)"
  value       = "http://${var.keycloak_hostname}"
}

output "keycloak_namespace" {
  description = "Namespace where keycloakx runs"
  value       = module.keycloak_init.namespace
}

# ── GitLab base setup (config root merged 2026-10-23, ADR-0033) ──────────────

output "gitlab_mirrors_group_id" {
  description = "Mirrors group ID"
  value       = module.gitlab.mirrors_group_id
}

output "gitlab_mirrors_group_path" {
  description = "Mirrors group full path"
  value       = module.gitlab.mirrors_group_path
}

output "gitlab_backend_user_id" {
  description = "Backend service account user ID"
  value       = module.gitlab.backend_user_id
}

output "gitlab_backend_user_username" {
  description = "Backend service account username"
  value       = module.gitlab.backend_user_username
}
