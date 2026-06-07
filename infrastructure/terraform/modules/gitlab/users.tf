/**
 * @file users.tf
 * @description GitLab service account user for BigBug backend integration.
 *              A dedicated local user (not root) owns the PAT and has
 *              appropriate group membership for mirror operations.
 */

resource "gitlab_user" "backend" {
  name             = var.backend_user_name
  username         = var.backend_user_username
  email            = var.backend_user_email
  password         = var.backend_user_password
  is_admin         = false
  projects_limit   = 100
  can_create_group = false
  skip_confirmation = true
}
