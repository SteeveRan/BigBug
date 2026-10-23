/**
 * @file outputs.tf
 * @description Output values exported by the Keycloak module.
 */

output "realm_id" {
  description = "Realm identifier"
  value       = keycloak_realm.bigbug.id
}

output "realm_name" {
  description = "Realm name"
  value       = var.realm_name
}

output "realm_url" {
  description = "Full URL to the realm"
  value       = "${var.keycloak_url}/realms/${var.realm_name}"
}

output "backend_client_id" {
  description = "Backend OIDC client ID"
  value       = keycloak_openid_client.backend.client_id
}

output "backend_client_secret" {
  description = "Backend OIDC client secret"
  value       = var.backend_client_secret
  sensitive   = true
}

output "frontend_client_id" {
  description = "Frontend OIDC client ID"
  value       = keycloak_openid_client.frontend.client_id
}

output "harbor_client_id" {
  description = "Harbor OIDC client ID"
  value       = keycloak_openid_client.harbor.client_id
}

output "harbor_client_secret" {
  description = "Harbor OIDC client secret"
  value       = var.harbor_client_secret
  sensitive   = true
}

output "test_user_username" {
  description = "Test user username"
  value       = keycloak_user.test_admin.username
}
