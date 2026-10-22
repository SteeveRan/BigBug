output "haproxy_ingress_status" {
  description = "Deployed haproxy-ingress release status"
  value       = helm_release.haproxy_ingress.status
}

output "valkey_service" {
  description = "Valkey Service (no auth, dev)"
  value       = "valkey.bigbug.svc:6379"
}
