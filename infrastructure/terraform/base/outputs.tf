output "haproxy_ingress_status" {
  description = "Deployed haproxy-ingress release status"
  value       = helm_release.haproxy_ingress.status
}

output "cnpg_cluster_name" {
  description = "CNPG Cluster CR name (ns bigbug)"
  value       = kubernetes_manifest.cnpg_cluster.manifest.metadata.name
}

output "cnpg_app_secret" {
  description = "Secret with application DB credentials (ns bigbug)"
  value       = "bigbug-dev-app"
}

output "cnpg_read_write_service" {
  description = "Read-write Service for the CNPG cluster"
  value       = "bigbug-dev-rw.bigbug.svc:5432"
}

output "valkey_service" {
  description = "Valkey Service (no auth, dev)"
  value       = "valkey.bigbug.svc:6379"
}
