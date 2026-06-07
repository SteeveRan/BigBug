/**
 * @file outputs.tf
 * @description Output values exported by the Harbor configuration.
 */

# ─── Projects ────────────────────────────────────────────────────────────────

output "gold_images_project_id" {
  description = "Gold images project ID"
  value       = harbor_project.gold_images.id
}

output "gold_images_project_name" {
  description = "Gold images project name"
  value       = harbor_project.gold_images.name
}

output "app_images_project_id" {
  description = "App images project ID"
  value       = harbor_project.app_images.id
}

output "app_images_project_name" {
  description = "App images project name"
  value       = harbor_project.app_images.name
}

output "mirrors_project_id" {
  description = "Mirrors project ID"
  value       = harbor_project.mirrors.id
}

output "mirrors_project_name" {
  description = "Mirrors project name"
  value       = harbor_project.mirrors.name
}

# ─── Robot Accounts ──────────────────────────────────────────────────────────

output "gold_images_ci_robot_name" {
  description = "Gold images CI robot account name"
  value       = harbor_robot_account.gold_images_ci.name
}

output "gold_images_ci_robot_secret" {
  description = "Gold images CI robot account secret"
  value       = harbor_robot_account.gold_images_ci.secret
  sensitive   = true
}

output "app_images_ci_robot_name" {
  description = "App images CI robot account name"
  value       = harbor_robot_account.app_images_ci.name
}

output "app_images_ci_robot_secret" {
  description = "App images CI robot account secret"
  value       = harbor_robot_account.app_images_ci.secret
  sensitive   = true
}

output "mirrors_ci_robot_name" {
  description = "Mirrors CI robot account name"
  value       = harbor_robot_account.mirrors_ci.name
}

output "mirrors_ci_robot_secret" {
  description = "Mirrors CI robot account secret"
  value       = harbor_robot_account.mirrors_ci.secret
  sensitive   = true
}

# ─── Registries ──────────────────────────────────────────────────────────────

output "dockerhub_registry_id" {
  description = "Docker Hub registry endpoint ID"
  value       = harbor_registry.docker_hub.id
}

output "quay_registry_id" {
  description = "Quay.io registry endpoint ID"
  value       = harbor_registry.quay.id
}

# ─── Webhooks ────────────────────────────────────────────────────────────────

output "webhook_id" {
  description = "Backend notification webhook ID"
  value       = harbor_project_webhook.backend_notifications.id
}

# ─── Registry URLs (for docker login) ────────────────────────────────────────

output "registry_url" {
  description = "Harbor registry base URL (for docker login)"
  value       = replace(var.harbor_url, "/^https?://([^/:]+)(:\\d+)?$/", "$1")
}
