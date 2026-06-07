/**
 * @file replications.tf
 * @description Replication policies — pull images from external registries into Harbor projects
 * @resource harbor_replication
 */

resource "harbor_replication" "gold_images_mirror" {
  name           = "gold-images-mirror"
  action         = "pull"
  schedule       = var.replication_schedule
  registry_id    = harbor_registry.docker_hub.registry_id
  dest_namespace = harbor_project.gold_images.name

  filters {
    name = "library/alpine"
  }
  filters {
    name = "library/ubuntu"
  }
}

resource "harbor_replication" "mirrors_sync" {
  name           = "mirrors-sync"
  action         = "pull"
  schedule       = var.replication_schedule
  registry_id    = harbor_registry.docker_hub.registry_id
  dest_namespace = harbor_project.mirrors.name

  filters {
    name = "**"
  }
}
