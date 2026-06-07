/**
 * @file tokens.tf
 * @description GitLab Personal Access Token for backend integration.
 *              Created for the dedicated backend service account (not root).
 *              The token grants api, read_repository, write_repository scopes.
 *              Expiration is computed as now + 90 days (well within GitLab CE 365-day limit).
 */

resource "gitlab_personal_access_token" "backend_integration" {
  user_id    = gitlab_user.backend.id
  name       = var.backend_token_name
  expires_at = formatdate("YYYY-MM-DD", timeadd(timestamp(), "2160h")) # now + 90 days

  scopes = var.backend_token_scopes

  lifecycle {
    ignore_changes = [expires_at]
  }
}
