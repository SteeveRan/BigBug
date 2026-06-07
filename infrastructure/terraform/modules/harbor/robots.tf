/**
 * @file robots.tf
 * @description CI/CD robot accounts with project-level permissions
 * @resource harbor_robot_account
 *
 * v3.x schema:
 *   level (required) — "system" or "project"
 *   permissions { kind, namespace, access { resource, action } }
 */

resource "harbor_robot_account" "gold_images_ci" {
  name        = "gold-images-ci"
  description = "CI/CD robot account for gold-images project"
  level       = "project"
  permissions {
    kind      = "project"
    namespace = harbor_project.gold_images.name
    access {
      resource = "repository"
      action   = "push"
    }
    access {
      resource = "repository"
      action   = "pull"
    }
    access {
      resource = "artifact"
      action   = "read"
    }
  }
}

resource "harbor_robot_account" "app_images_ci" {
  name        = "app-images-ci"
  description = "CI/CD robot account for app-images project"
  level       = "project"
  permissions {
    kind      = "project"
    namespace = harbor_project.app_images.name
    access {
      resource = "repository"
      action   = "push"
    }
    access {
      resource = "repository"
      action   = "pull"
    }
    access {
      resource = "artifact"
      action   = "read"
    }
  }
}

resource "harbor_robot_account" "mirrors_ci" {
  name        = "mirrors-ci"
  description = "CI/CD robot account for mirrors project"
  level       = "project"
  permissions {
    kind      = "project"
    namespace = harbor_project.mirrors.name
    access {
      resource = "repository"
      action   = "push"
    }
    access {
      resource = "repository"
      action   = "pull"
    }
    access {
      resource = "artifact"
      action   = "read"
    }
  }
}
