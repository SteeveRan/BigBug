output "haproxy_ingress_status" {
  description = "Deployed haproxy-ingress release status"
  value       = helm_release.haproxy_ingress.status
}

output "redis_operator_status" {
  description = "Deployed redis-operator release status"
  value       = helm_release.redis_operator.status
}
