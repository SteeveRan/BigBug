output "namespace" {
  value = kubernetes_namespace.harbor.metadata[0].name
}

output "harbor_release_name" {
  value = helm_release.harbor.name
}
