/**
 * @file registries.tf
 * @description External container registries for replication
 * @resource harbor_registry
 */

resource "harbor_registry" "docker_hub" {
  provider_name = "docker-hub"
  name          = var.dockerhub_registry_name
  endpoint_url  = var.dockerhub_endpoint_url
}

resource "harbor_registry" "quay" {
  provider_name = "docker-hub"
  name          = var.quay_registry_name
  endpoint_url  = var.quay_endpoint_url
}
