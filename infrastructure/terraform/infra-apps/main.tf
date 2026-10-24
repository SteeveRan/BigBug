/**
 * @file main.tf
 * @description INFRASTRUCTURE app instances in the bigbug-dev kind cluster
 *              (infra-apps root, ADR-0029): Keycloak stack (issue #57) —
 *              namespace, CNPG Postgres Cluster CR, keycloakx chart,
 *              realm/clients/roles/users config — Harbor (issue #58) —
 *              namespace, TLS secrets, chart release, API config — and the
 *              GitLab base setup (group, service-account; config root merged
 *              2026-10-23, ADR-0033).
 *
 *              NOT the BigBug application itself: its infra (ns `bigbug`)
 *              lives in the separate `apps` root so app-ворктрии не дерутся
 *              с инфра-апплаями (state-split; see ../apps).
 *
 * Platform layer (ingress, operators) lives in ../base (separate state).
 *
 * Prerequisite (in order):
 *   1. certs for *.local + host trust — ../../kind/certs.sh && trust-host.sh
 *      (certs live in ~/.local/state/bigbug/certs — shared per machine,
 *      same place as the tofu states)
 *   2. kind cluster `bigbug-dev` — ../../kind/bootstrap.sh
 *   3. base layer (CNPG operator + CRDs, haproxy-ingress, CoreDNS) — cd ../base && tofu apply
 *   4. this root: tofu init && tofu apply (GitLab part needs GitLab up —
 *      init.sh starts the compose zone first)
 */

# Certs dir lives outside the cluster lifecycle AND outside the worktree —
# next to the tofu states (ADR-0030 §3)
locals {
  certs_dir = pathexpand("~/.local/state/bigbug/certs")
}

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.16"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.35"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    harbor = {
      source  = "goharbor/harbor"
      version = "~> 3.12"
    }
    keycloak = {
      source  = "keycloak/keycloak"
      version = "~> 5.0"
    }
    gitlab = {
      source  = "gitlabhq/gitlab"
      version = "~> 17.0"
    }
  }
}

provider "kubernetes" {
  config_path    = var.kubeconfig_path
  config_context = var.kubeconfig_context
}

provider "helm" {
  kubernetes {
    config_path    = var.kubeconfig_path
    config_context = var.kubeconfig_context
  }
}

provider "harbor" {
  url      = "https://harbor.local"
  username = "admin"
  password = "Harbor12345"
}

provider "keycloak" {
  client_id = "admin-cli"
  username  = var.keycloak_admin_username
  password  = var.keycloak_admin_password
  url       = var.keycloak_url
}

# ── GitLab base setup (config root merged 2026-10-23, ADR-0033) ──────────────
# group bigbug-mirrors, backend service-account user, group membership.
# Provider config lives inside modules/gitlab (module vars drive it).
# GitLab PAT bootstrap (init.sh, gitlab-rails runner) is a documented
# imperative exception from IaC (ADR-0033 §PAT).
module "gitlab" {
  source = "./modules/gitlab"

  gitlab_url     = var.gitlab_url
  gitlab_token   = var.gitlab_token
  gitlab_ca_cert = var.gitlab_ca_cert != "" ? pathexpand(var.gitlab_ca_cert) : ""

  mirrors_group_name = var.mirrors_group_name

  backend_user_name     = var.backend_user_name
  backend_user_username = var.backend_user_username
  backend_user_email    = var.backend_user_email
  backend_user_password = var.backend_user_password
}

# ── Harbor installation (ns, TLS secrets, chart) — issue #58 ────────────────
module "harbor_init" {
  source = "./modules/harbor_init"

  providers = {
    kubernetes = kubernetes
    helm       = helm
  }

  certs_dir = local.certs_dir
}

# ── Keycloak installation (ns, TLS/admin secrets, CNPG CR, chart) — #57 ─────
module "keycloak_init" {
  source = "./modules/keycloak_init"

  providers = {
    kubernetes = kubernetes
    helm       = helm
  }

  certs_dir               = local.certs_dir
  keycloak_hostname       = var.keycloak_hostname
  keycloak_admin_username = var.keycloak_admin_username
  keycloak_admin_password = var.keycloak_admin_password
  cnpg_storage_size       = var.cnpg_storage_size
}

# ── Keycloak config (realm/clients/roles/users) — migrated from config root ──
module "keycloak_conf" {
  source = "./modules/keycloak_conf"

  providers = {
    keycloak = keycloak
  }

  keycloak_url            = var.keycloak_url
  keycloak_admin_username = var.keycloak_admin_username
  keycloak_admin_password = var.keycloak_admin_password
  realm_name              = var.realm_name

  backend_client_id     = var.backend_client_id
  backend_client_secret = var.backend_client_secret

  frontend_client_id     = var.frontend_client_id
  frontend_redirect_uris = var.frontend_redirect_uris

  harbor_client_id                 = var.harbor_client_id
  harbor_client_secret             = var.harbor_client_secret
  harbor_redirect_uris             = var.harbor_redirect_uris
  harbor_post_logout_redirect_uris = var.harbor_post_logout_redirect_uris
  harbor_root_url                  = var.harbor_root_url

  test_user_username = var.test_user_username
  test_user_password = var.test_user_password
  test_user_email    = var.test_user_email
}

# ── Harbor config (projects/robots/registries/replications/webhooks +
#    OIDC auth) — migrated from the deprecated config root; issues #58/#62 ────
module "harbor_conf" {
  source = "./modules/harbor_conf"

  providers = {
    harbor = harbor
  }

  harbor_password    = "Harbor12345"
  oidc_client_secret = var.harbor_client_secret
}
