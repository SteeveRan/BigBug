/**
 * @file projects.tf
 * @description Harbor projects
 * @resource harbor_project
 */

resource "harbor_project" "gold_images" {
  name                   = var.gold_images_project_name
  public                 = false
  vulnerability_scanning = false
  storage_quota          = var.gold_images_storage_quota
}

resource "harbor_project" "app_images" {
  name                   = var.app_images_project_name
  public                 = true
  vulnerability_scanning = false
  storage_quota          = var.app_images_storage_quota
}

resource "harbor_project" "mirrors" {
  name                   = var.mirrors_project_name
  public                 = true
  vulnerability_scanning = false
  storage_quota          = var.mirrors_storage_quota
}
