output "haproxy_ingress_status" {
  description = "Deployed haproxy-ingress release status"
  value       = helm_release.haproxy_ingress.status
}
