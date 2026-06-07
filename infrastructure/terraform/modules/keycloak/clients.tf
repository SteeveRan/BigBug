/**
 * @file clients.tf
 * @description OpenID Connect clients for Keycloak realm "bigbug"
 *              - backend:  confidential client for FastAPI (client secret auth)
 *              - frontend: public client for React SPA (PKCE S256 enforced)
 *              - harbor:   confidential client for Harbor Registry OIDC SSO
 */

# ── Backend confidential client ────────────────────────────────
resource "keycloak_openid_client" "backend" {
  realm_id  = keycloak_realm.bigbug.id
  client_id = var.backend_client_id
  name      = "BigBug Backend"
  enabled   = true

  access_type = "CONFIDENTIAL"

  standard_flow_enabled       = true
  direct_access_grants_enabled = true
  service_accounts_enabled    = false

  valid_redirect_uris = ["*"]
  web_origins         = ["*"]

  client_secret = var.backend_client_secret
}

# ── Harbor confidential client (OIDC SSO) ───────────────────────
resource "keycloak_openid_client" "harbor" {
  realm_id  = keycloak_realm.bigbug.id
  client_id = var.harbor_client_id
  name      = "Harbor Registry"
  enabled   = true

  access_type = "CONFIDENTIAL"

  standard_flow_enabled        = true
  direct_access_grants_enabled = true
  implicit_flow_enabled        = false
  service_accounts_enabled     = false

  root_url                       = var.harbor_root_url
  base_url                       = var.harbor_root_url
  admin_url                      = var.harbor_root_url
  valid_redirect_uris            = var.harbor_redirect_uris
  valid_post_logout_redirect_uris = var.harbor_post_logout_redirect_uris
  web_origins                    = [var.harbor_root_url]

  client_secret = var.harbor_client_secret
}

# ── Frontend public client (SPA, PKCE S256) ────────────────────
resource "keycloak_openid_client" "frontend" {
  realm_id  = keycloak_realm.bigbug.id
  client_id = var.frontend_client_id
  name      = "BigBug Frontend"
  enabled   = true

  access_type = "PUBLIC"

  standard_flow_enabled       = true
  direct_access_grants_enabled = false
  implicit_flow_enabled       = false
  service_accounts_enabled    = false

  # PKCE required for public clients per security best practices
  pkce_code_challenge_method = "S256"

  valid_redirect_uris = var.frontend_redirect_uris
  web_origins         = ["+"]
}
