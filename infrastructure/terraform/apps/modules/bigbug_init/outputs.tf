/**
 * @file outputs.tf
 * @description Documented secret names/keys — the contract the helm chart
 *              (charts/bigbug, ADR-0023) consumes via secretKeyRef.
 */

output "secret_names" {
  description = "k8s Secrets created by this module (ns bigbug) with their data keys"
  value = {
    db_credentials = {
      name = kubernetes_secret_v1.db_credentials.metadata[0].name
      keys = ["DATABASE_URL", "username", "password", "database", "host", "port"]
    }
    fernet_key = {
      name = kubernetes_secret_v1.fernet_key.metadata[0].name
      keys = ["ENCRYPTION_KEY"]
    }
    keycloak_oidc = {
      name = kubernetes_secret_v1.keycloak_oidc.metadata[0].name
      keys = ["client_id", "client_secret"]
    }
  }
}

output "database_url" {
  description = "Application DATABASE_URL (host tools, sensitive)"
  value       = local.database_url
  sensitive   = true
}

output "namespace" {
  description = "App namespace"
  value       = kubernetes_namespace.bigbug.metadata[0].name
}
