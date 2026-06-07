/**
 * @file main.tf
 * @description OpenTofu/Terraform provider configuration for Harbor
 * @provider goharbor/harbor ~> 3.12
 *
 * Resource groups (split by concern):
 *   auth.tf          — OIDC authentication (Keycloak)
 *   projects.tf      — Harbor projects
 *   robots.tf        — CI/CD robot accounts
 *   registries.tf    — External container registries
 *   replications.tf  — Replication policies
 *   webhooks.tf      — Project webhook notifications
 */

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    harbor = {
      source  = "goharbor/harbor"
      version = "~> 3.12"
    }
  }
}

provider "harbor" {
  url      = var.harbor_url
  username = var.harbor_username
  password = var.harbor_password
}
