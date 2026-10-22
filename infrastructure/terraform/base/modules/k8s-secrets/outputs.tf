/**
 * @file outputs.tf
 * @description Documented secret names/keys — the contract the helm chart
 *              (ADR-0023, issue I6) is expected to consume via secretKeyRef.
 */

output "secret_names" {
  description = "k8s Secrets created by this module (ns bigbug) with their data keys"
  value = {
    db_credentials = {
      name = kubernetes_secret.db_credentials.metadata[0].name
      keys = ["DATABASE_URL", "username", "password", "database", "host", "port"]
    }
    fernet_key = {
      name = kubernetes_secret.fernet_key.metadata[0].name
      keys = ["ENCRYPTION_KEY"]
    }
  }
}

output "fernet_key" {
  description = "Fernet ENCRYPTION_KEY (host tools / .env fallback, sensitive)"
  value       = local.fernet_key
  sensitive   = true
}

output "database_url" {
  description = "Application DATABASE_URL (host tools, sensitive)"
  value       = local.database_url
  sensitive   = true
}
