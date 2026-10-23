/**
 * @file outputs.tf
 * @description Root module output values — GitLab only (ADR-0033).
 */

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
