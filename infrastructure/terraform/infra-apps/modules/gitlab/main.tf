/**
 * @file main.tf
 * @description OpenTofu/Terraform provider configuration for GitLab
 * @provider gitlabhq/gitlab ~> 17.0
 */

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    gitlab = {
      source  = "gitlabhq/gitlab"
      version = "~> 17.0"
    }
  }
}

provider "gitlab" {
  token    = var.gitlab_token
  base_url = var.gitlab_url
  # Self-signed cert from kind/certs.sh (ADR-0030 §9) — never skip verification
  cacert_file = var.gitlab_ca_cert != "" ? var.gitlab_ca_cert : null
}
