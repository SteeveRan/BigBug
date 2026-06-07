/**
 * @file outputs.tf
 * @description Root module output values — aggregated from all sub-modules.
 */

# ═══════════════════════════════════════════════════════════════════════════════
# Keycloak
# ═══════════════════════════════════════════════════════════════════════════════

output "keycloak_realm_id" {
  description = "Keycloak realm ID"
  value       = module.keycloak.realm_id
}

output "keycloak_realm_name" {
  description = "Keycloak realm name"
  value       = module.keycloak.realm_name
}

output "keycloak_realm_url" {
  description = "Keycloak realm URL (OIDC endpoint)"
  value       = module.keycloak.realm_url
}

output "keycloak_backend_client_id" {
  description = "BigBug backend OIDC client ID"
  value       = module.keycloak.backend_client_id
}

output "keycloak_backend_client_secret" {
  description = "BigBug backend OIDC client secret"
  value       = module.keycloak.backend_client_secret
  sensitive   = true
}

output "keycloak_frontend_client_id" {
  description = "BigBug frontend OIDC client ID"
  value       = module.keycloak.frontend_client_id
}

output "keycloak_harbor_client_id" {
  description = "Harbor OIDC client ID"
  value       = module.keycloak.harbor_client_id
}

output "keycloak_harbor_client_secret" {
  description = "Harbor OIDC client secret"
  value       = module.keycloak.harbor_client_secret
  sensitive   = true
}

output "keycloak_test_user_username" {
  description = "Test user username"
  value       = module.keycloak.test_user_username
}

# ═══════════════════════════════════════════════════════════════════════════════
# Harbor
# ═══════════════════════════════════════════════════════════════════════════════

output "harbor_gold_images_project_id" {
  description = "Gold images project ID"
  value       = module.harbor.gold_images_project_id
}

output "harbor_gold_images_project_name" {
  description = "Gold images project name"
  value       = module.harbor.gold_images_project_name
}

output "harbor_app_images_project_id" {
  description = "App images project ID"
  value       = module.harbor.app_images_project_id
}

output "harbor_app_images_project_name" {
  description = "App images project name"
  value       = module.harbor.app_images_project_name
}

output "harbor_mirrors_project_id" {
  description = "Mirrors project ID"
  value       = module.harbor.mirrors_project_id
}

output "harbor_mirrors_project_name" {
  description = "Mirrors project name"
  value       = module.harbor.mirrors_project_name
}

output "harbor_gold_images_ci_robot_name" {
  description = "Gold images CI robot account name"
  value       = module.harbor.gold_images_ci_robot_name
}

output "harbor_gold_images_ci_robot_secret" {
  description = "Gold images CI robot account secret"
  value       = module.harbor.gold_images_ci_robot_secret
  sensitive   = true
}

output "harbor_app_images_ci_robot_name" {
  description = "App images CI robot account name"
  value       = module.harbor.app_images_ci_robot_name
}

output "harbor_app_images_ci_robot_secret" {
  description = "App images CI robot account secret"
  value       = module.harbor.app_images_ci_robot_secret
  sensitive   = true
}

output "harbor_mirrors_ci_robot_name" {
  description = "Mirrors CI robot account name"
  value       = module.harbor.mirrors_ci_robot_name
}

output "harbor_mirrors_ci_robot_secret" {
  description = "Mirrors CI robot account secret"
  value       = module.harbor.mirrors_ci_robot_secret
  sensitive   = true
}

output "harbor_dockerhub_registry_id" {
  description = "Docker Hub registry ID"
  value       = module.harbor.dockerhub_registry_id
}

output "harbor_quay_registry_id" {
  description = "Quay.io registry ID"
  value       = module.harbor.quay_registry_id
}

output "harbor_webhook_id" {
  description = "Backend webhook endpoint ID"
  value       = module.harbor.webhook_id
}

output "harbor_registry_url" {
  description = "Harbor registry URL"
  value       = module.harbor.registry_url
}

# ═══════════════════════════════════════════════════════════════════════════════
# GitLab
# ═══════════════════════════════════════════════════════════════════════════════

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

output "gitlab_backend_token" {
  description = "Backend personal access token (store securely)"
  value       = module.gitlab.backend_token
  sensitive   = true
}

output "gitlab_backend_token_name" {
  description = "Backend PAT name"
  value       = module.gitlab.backend_token_name
}

output "gitlab_backend_token_expires_at" {
  description = "Backend PAT expiration date"
  value       = module.gitlab.backend_token_expires_at
}
