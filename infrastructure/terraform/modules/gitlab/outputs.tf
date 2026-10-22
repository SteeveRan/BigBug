/**
 * @file outputs.tf
 * @description Output values exported by the GitLab configuration.
 */

output "mirrors_group_id" {
  description = "Mirrors group ID"
  value       = gitlab_group.mirrors.id
}

output "mirrors_group_path" {
  description = "Mirrors group full path"
  value       = gitlab_group.mirrors.full_path
}

output "backend_user_id" {
  description = "Backend service account user ID"
  value       = gitlab_user.backend.id
}

output "backend_user_username" {
  description = "Backend service account username"
  value       = gitlab_user.backend.username
}
