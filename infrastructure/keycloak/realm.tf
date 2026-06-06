/**
 * @file realm.tf
 * @description Keycloak realm "bigbug" for the BigBug application
 */

resource "keycloak_realm" "bigbug" {
  realm        = var.realm_name
  enabled      = true
  display_name = "BigBug"

  # Allow SSO via any scheme in development
  ssl_required = "external"

  # Token settings
  access_token_lifespan  = "15m"
  sso_session_idle_timeout = "30m"
  sso_session_max_lifespan = "10h"

  # Allow user self-registration via SSO
  registration_allowed = false
  verify_email         = false
}
