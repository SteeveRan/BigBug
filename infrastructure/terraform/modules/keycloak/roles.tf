/**
 * @file roles.tf
 * @description Realm roles consumed by backend RBAC (app/core/rbac.py RoleName enum).
 *              Keep in sync with the Python enum: admin, operator, viewer.
 */

resource "keycloak_role" "admin" {
  realm_id    = keycloak_realm.bigbug.id
  name        = "admin"
  description = "BigBug RBAC role: full access + user/role management"
}

resource "keycloak_role" "operator" {
  realm_id    = keycloak_realm.bigbug.id
  name        = "operator"
  description = "BigBug RBAC role: manage projects, mirrors, images, helm charts, docker images, trigger syncs"
}

resource "keycloak_role" "viewer" {
  realm_id    = keycloak_realm.bigbug.id
  name        = "viewer"
  description = "BigBug RBAC role: read-only access to all resources"
}
