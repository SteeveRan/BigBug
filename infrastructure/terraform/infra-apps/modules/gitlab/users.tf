/**
 * @file users.tf
 * @description GitLab service account user for BigBug backend integration.
 *              A dedicated local user (not root) owns the PAT and has
 *              appropriate group membership for mirror operations.
 */

# Backend service-account password: explicit via var, or auto-generated
# (persisted in state — the same password is reused on re-applies).
resource "random_password" "backend_user" {
  count   = var.backend_user_password == null ? 1 : 0
  length  = 20
  special = false
}

locals {
  backend_user_password = coalesce(var.backend_user_password, try(random_password.backend_user[0].result, null))
}

resource "gitlab_user" "backend" {
  name              = var.backend_user_name
  username          = var.backend_user_username
  email             = var.backend_user_email
  password          = local.backend_user_password
  is_admin          = false
  projects_limit    = 100
  can_create_group  = false
  skip_confirmation = true
}
