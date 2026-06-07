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

output "backend_token" {
  description = "Backend personal access token (store securely)"
  value       = gitlab_personal_access_token.backend_integration.token
  sensitive   = true
}

output "backend_token_name" {
  description = "Backend PAT name"
  value       = gitlab_personal_access_token.backend_integration.name
}

output "backend_token_expires_at" {
  description = "Backend PAT expiration date"
  value       = gitlab_personal_access_token.backend_integration.expires_at
}
