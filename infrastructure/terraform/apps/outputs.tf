/**
 * @file outputs.tf
 * @description Outputs for the apps root.
 */

output "keycloak_url" {
  description = "External Keycloak URL (ADR-0022 addressing)"
  value       = "http://${var.keycloak_hostname}"
}

output "keycloak_namespace" {
  description = "Namespace where keycloakx runs"
  value       = module.keycloak_init.namespace
}
