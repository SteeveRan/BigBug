/**
 * @file groups.tf
 * @description Keycloak groups mapped to Harbor roles (examples/harbor/
 *              keycloak-integration.md §3.1). Exposed to Harbor via the
 *              "groups" client scope mapper (clients.tf); lost realm
 *              recreation without these, so they live in IaC now.
 */

resource "keycloak_group" "harbor_admin" {
  realm_id = keycloak_realm.bigbug.id
  name     = "harbor-admin"
}

resource "keycloak_group" "harbor_dev" {
  realm_id = keycloak_realm.bigbug.id
  name     = "harbor-dev"
}

resource "keycloak_group" "harbor_guest" {
  realm_id = keycloak_realm.bigbug.id
  name     = "harbor-guest"
}

# Test user gets admin group so OIDC login onboards as Harbor System Admin.
resource "keycloak_group_memberships" "test_user" {
  realm_id = keycloak_realm.bigbug.id
  group_id = keycloak_group.harbor_admin.id
  members  = [var.test_user_username]
}
