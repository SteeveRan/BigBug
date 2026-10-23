output "namespace" {
  value = kubernetes_namespace.keycloak.metadata[0].name
}

output "keycloakx_release_name" {
  value = helm_release.keycloakx.name
}
