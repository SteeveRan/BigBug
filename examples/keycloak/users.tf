/**
 * @file users.tf
 * @description Test user for BigBug development environment.
 *              Default: bigbug / bigbug with role "admin".
 */

resource "keycloak_user" "test_admin" {
  realm_id   = keycloak_realm.bigbug.id
  username   = var.test_user_username
  email      = var.test_user_email
  enabled    = true

  email_verified = true

  initial_password {
    value     = var.test_user_password
    temporary = false
  }
}

# Assign admin role to the test user
resource "keycloak_user_roles" "test_admin_roles" {
  realm_id = keycloak_realm.bigbug.id
  user_id  = keycloak_user.test_admin.id

  role_ids = [
    keycloak_role.admin.id,
  ]
}
