/**
 * @file main.tf
 * @description BigBug APP infrastructure root (ADR-0029): namespace `bigbug`,
 *              CNPG Postgres Cluster, Redis CR, app secrets, TLS secrets
 *              (module bigbug_init, issue #59). The app itself runs via the
 *              charts/bigbug helm release (applied by make dev-up, #61).
 *
 *              Split from the old `apps` root (now `../infra-apps`): app-infra
 *              changes must not require apply-runs of the infra root and
 *              compete with other worktrees over its state/locks.
 *
 * Prerequisite (in order):
 *   1. certs for *.local + host trust — ../../kind/certs.sh && trust-host.sh
 *   2. kind cluster `bigbug-dev` — ../../kind/bootstrap.sh
 *   3. base layer — cd ../base && tofu apply
 *   4. infra-apps (Keycloak/Harbor; keycloak_oidc secret needs the backend
 *      client) — cd ../infra-apps && tofu apply
 *   5. this root: tofu init && tofu apply
 */

# Certs dir lives outside the cluster lifecycle AND outside the worktree —
# next to the tofu states (ADR-0030 §3)
locals {
  certs_dir = pathexpand("~/.local/state/bigbug/certs")
}

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.35"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "kubernetes" {
  config_path    = var.kubeconfig_path
  config_context = var.kubeconfig_context
}

# ── BigBug app infra (ns bigbug: CNPG, Redis CR, secrets, TLS) — #59 ─────────
module "bigbug_init" {
  source = "./modules/bigbug_init"

  providers = {
    kubernetes = kubernetes
  }

  certs_dir             = local.certs_dir
  cnpg_storage_size     = var.cnpg_storage_size
  backend_client_id     = var.backend_client_id
  backend_client_secret = var.backend_client_secret
}
