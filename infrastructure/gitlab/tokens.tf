/**
 * @file tokens.tf
 * @description GitLab Personal Access Token for backend integration.
 *              The token grants api, read_repository, write_repository scopes.
 */

resource "gitlab_personal_access_token" "backend_integration" {
  user_id    = data.gitlab_user.root.id
  name       = var.backend_token_name
  expires_at = var.backend_token_expires_at

  scopes = var.backend_token_scopes
}
