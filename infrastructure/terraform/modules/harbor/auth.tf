/**
 * @file auth.tf
 * @description OIDC authentication — Keycloak integration
 * @resource harbor_config_auth
 *
 * Mirrors the manual setup described in:
 *   infrastructure/harbor/setup/keycloak-integration.md
 */

resource "harbor_config_auth" "oidc" {
  auth_mode                     = var.auth_mode
  oidc_name                     = var.oidc_provider_name
  oidc_endpoint                 = var.oidc_endpoint
  oidc_client_id                = var.oidc_client_id
  oidc_client_secret_wo         = var.oidc_client_secret
  oidc_client_secret_wo_version = 1
  oidc_groups_claim             = var.oidc_groups_claim
  oidc_scope                    = var.oidc_scope
  oidc_verify_cert              = var.oidc_verify_cert
  oidc_auto_onboard             = var.oidc_auto_onboard
  oidc_user_claim               = var.oidc_user_claim
}
