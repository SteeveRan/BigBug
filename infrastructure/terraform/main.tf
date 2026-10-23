/**
 * @file main.tf
 * @description Config root — GitLab base setup only (ADR-0033).
 *
 * Keycloak/Harbor config moved to terraform/apps (modules keycloak_conf /
 * harbor_conf — ADR-0029 update #58). This root manages the GitLab zone:
 * group bigbug-mirrors, backend service-account user, group membership.
 *
 * GitLab PAT bootstrap (init.sh, gitlab-rails runner) is a documented
 * imperative exception from IaC (ADR-0033 §PAT).
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

# ──────────────────────────────────────────────────────────────────────────────
# Module: GitLab
# ──────────────────────────────────────────────────────────────────────────────
module "gitlab" {
  source = "./modules/gitlab"

  gitlab_url   = var.gitlab_url
  gitlab_token = var.gitlab_token
  gitlab_ca_cert = var.gitlab_ca_cert

  mirrors_group_name = var.mirrors_group_name

  backend_user_name     = var.backend_user_name
  backend_user_username = var.backend_user_username
  backend_user_email    = var.backend_user_email
  backend_user_password = var.backend_user_password
}
