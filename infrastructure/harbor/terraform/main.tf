/**
 * @file main.tf
 * @description OpenTofu/Terraform provider configuration for Harbor
 * @provider goharbor/harbor ~> 3.0
 *
 * Provisions:
 *   - OIDC authentication (Keycloak integration)
 *   - Projects: gold-images, app-images, mirrors
 *   - Robot accounts for CI/CD
 *   - Replication registries and policies
 *   - Webhook endpoints for notifications
 */

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    harbor = {
      source  = "goharbor/harbor"
      version = "~> 3.0"
    }
  }
}

# ─── Provider ────────────────────────────────────────────────────────────────

provider "harbor" {
  url      = var.harbor_url
  username = var.harbor_username
  password = var.harbor_password
}

# ─── OIDC Authentication (Keycloak Integration) ──────────────────────────────
# Mirrors the manual setup described in: infrastructure/harbor/setup/keycloak-integration.md

resource "harbor_config_auth" "oidc" {
  auth_mode          = var.auth_mode
  oidc_name          = var.oidc_provider_name
  oidc_endpoint      = var.oidc_endpoint
  oidc_client_id     = var.oidc_client_id
  oidc_client_secret = var.oidc_client_secret
  oidc_groups_claim  = var.oidc_groups_claim
  oidc_scope         = var.oidc_scope
  oidc_verify_cert   = var.oidc_verify_cert
  oidc_auto_onboard  = var.oidc_auto_onboard
  oidc_user_claim    = var.oidc_user_claim
}

# ─── Projects ────────────────────────────────────────────────────────────────
# Replicates init-harbor.sh project creation

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

# ─── Robot Accounts ──────────────────────────────────────────────────────────
# CI/CD robot accounts with project-specific permissions

resource "harbor_robot_account" "gold_images_ci" {
  name        = "gold-images-ci"
  description = "CI/CD robot account for gold-images project"
  project_id  = harbor_project.gold_images.id
  permissions {
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
  project_id  = harbor_project.app_images.id
  permissions {
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
  project_id  = harbor_project.mirrors.id
  permissions {
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

# ─── External Registries (for Replication) ───────────────────────────────────

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

# ─── Replication Policies ────────────────────────────────────────────────────

resource "harbor_replication" "gold_images_mirror" {
  name        = "gold-images-mirror"
  action      = "pull"
  schedule    = var.replication_schedule
  dest_namespace = harbor_project.gold_images.name

  filters {
    name = "library/alpine"
  }
  filters {
    name = "library/ubuntu"
  }
}

resource "harbor_replication" "mirrors_sync" {
  name        = "mirrors-sync"
  action      = "pull"
  schedule    = var.replication_schedule
  dest_namespace = harbor_project.mirrors.name

  filters {
    name = "**"
  }
}

# ─── Webhooks ────────────────────────────────────────────────────────────────

resource "harbor_webhook" "backend_notifications" {
  name        = "bigbug-backend-webhook"
  project_id  = harbor_project.gold_images.id
  notify_type = "http"
  event_types = [
    "PUSH_ARTIFACT",
    "DELETE_ARTIFACT",
    "SCANNING_COMPLETED",
  ]
  targets {
    type     = "http"
    address  = var.webhook_backend_url
    skip_cert_verify = true
  }
}
