/**
 * @file main.tf
 * @description Root OpenTofu configuration — orchestrates all infrastructure modules.
 *
 * Execution order (implicit via dependency graph):
 *   1. Keycloak  — realm, OIDC clients, roles, test user
 *   2. Harbor    — OIDC auth (uses Keycloak harbor client secret), projects, robots, registries, webhooks
 *   3. GitLab    — group, backend service account, PAT (no dependency on Keycloak/Harbor outputs)
 *
 * Single `tofu apply` is sufficient — OpenTofu resolves the dependency graph automatically.
 */

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    keycloak = {
      source  = "mrparkers/keycloak"
      version = "~> 4.0"
    }
    harbor = {
      source  = "goharbor/harbor"
      version = "~> 3.12"
    }
    gitlab = {
      source  = "gitlabhq/gitlab"
      version = "~> 17.0"
    }
  }
}

# ──────────────────────────────────────────────────────────────────────────────
# Module: Keycloak
# ──────────────────────────────────────────────────────────────────────────────
module "keycloak" {
  source = "./modules/keycloak"

  keycloak_url            = var.keycloak_url
  keycloak_admin_username = var.keycloak_admin_username
  keycloak_admin_password = var.keycloak_admin_password
  realm_name              = var.realm_name

  backend_client_id     = var.backend_client_id
  backend_client_secret = var.backend_client_secret

  frontend_client_id    = var.frontend_client_id
  frontend_redirect_uris = var.frontend_redirect_uris

  harbor_client_id               = var.harbor_client_id
  harbor_client_secret           = var.harbor_client_secret
  harbor_redirect_uris           = var.harbor_redirect_uris
  harbor_post_logout_redirect_uris = var.harbor_post_logout_redirect_uris
  harbor_root_url                = var.harbor_root_url

  test_user_username = var.test_user_username
  test_user_password = var.test_user_password
  test_user_email    = var.test_user_email
}

# ──────────────────────────────────────────────────────────────────────────────
# Module: Harbor
# ──────────────────────────────────────────────────────────────────────────────
module "harbor" {
  source = "./modules/harbor"

  harbor_url      = var.harbor_url
  harbor_username = var.harbor_username
  harbor_password = var.harbor_password

  # OIDC — Keycloak-created client credentials
  auth_mode          = var.harbor_auth_mode
  oidc_provider_name = var.harbor_oidc_provider_name
  oidc_endpoint      = var.harbor_oidc_endpoint
  oidc_client_id     = var.harbor_client_id
  oidc_client_secret = module.keycloak.harbor_client_secret
  oidc_groups_claim  = var.harbor_oidc_groups_claim
  oidc_scope         = var.harbor_oidc_scope
  oidc_verify_cert   = var.harbor_oidc_verify_cert
  oidc_auto_onboard  = var.harbor_oidc_auto_onboard
  oidc_user_claim    = var.harbor_oidc_user_claim

  # Projects
  gold_images_project_name  = var.gold_images_project_name
  gold_images_storage_quota = var.gold_images_storage_quota
  app_images_project_name   = var.app_images_project_name
  app_images_storage_quota  = var.app_images_storage_quota
  mirrors_project_name      = var.mirrors_project_name
  mirrors_storage_quota     = var.mirrors_storage_quota

  # Registries
  dockerhub_registry_name = var.dockerhub_registry_name
  dockerhub_endpoint_url  = var.dockerhub_endpoint_url
  quay_registry_name      = var.quay_registry_name
  quay_endpoint_url       = var.quay_endpoint_url

  # Replication
  replication_schedule = var.replication_schedule

  # Webhooks
  webhook_backend_url = var.webhook_backend_url
}

# ──────────────────────────────────────────────────────────────────────────────
# Module: GitLab
# ──────────────────────────────────────────────────────────────────────────────
module "gitlab" {
  source = "./modules/gitlab"

  gitlab_url   = var.gitlab_url
  gitlab_token = var.gitlab_token

  mirrors_group_name = var.mirrors_group_name

  backend_user_name     = var.backend_user_name
  backend_user_username = var.backend_user_username
  backend_user_email    = var.backend_user_email
  backend_user_password = var.backend_user_password

  backend_token_name       = var.backend_token_name
  backend_token_expires_at = var.backend_token_expires_at
  backend_token_scopes     = var.backend_token_scopes
}
