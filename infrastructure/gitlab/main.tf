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
}

# Data source to retrieve the root/admin user ID
# Required for creating personal access tokens
data "gitlab_user" "root" {
  username = "root"
}
