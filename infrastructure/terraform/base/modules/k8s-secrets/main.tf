/**
 * @file main.tf
 * @description k8s Secrets for the dev-stand, managed by OpenTofu (ADR-0024).
 *
 * Naming/keys follow the helm-chart contract (ADR-0023, issue I6):
 *   bigbug-db-credentials  — DATABASE_URL for backend + hook Job migrations
 *   bigbug-fernet-key      — ENCRYPTION_KEY (Fernet, ADR-0010)
 * bigbug-keycloak-oidc arrives with issue I4 (keycloakx deployment);
 * bigbug-gitlab-token is created by a later layer (base must stay one-shot).
 */

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

# ──────────────────────────────────────────────────────────────────────────────
# DB credentials: NOT a manual copy — the CNPG operator generates them in
# <cluster>-app; we project the operator-owned fields into the helm-chart
# contract secret. The operator rotates its source secret; tofu re-reads it
# on each plan and updates downstream values.
# ──────────────────────────────────────────────────────────────────────────────
data "kubernetes_secret_v1" "cnpg_app" {
  # CNPG convention: the operator writes user credentials to <cluster-name>-app
  metadata {
    name      = "${var.cnpg_app_secret_name}-app"
    namespace = var.namespace
  }
}

locals {
  db_user     = data.kubernetes_secret_v1.cnpg_app.data["user"]
  db_password = data.kubernetes_secret_v1.cnpg_app.data["password"]
  db_host     = "${var.cnpg_app_secret_name}-rw.${var.namespace}.svc"
  db_port     = data.kubernetes_secret_v1.cnpg_app.data["port"]
  db_name     = data.kubernetes_secret_v1.cnpg_app.data["dbname"]

  database_url = "postgresql+asyncpg://${local.db_user}:${local.db_password}@${local.db_host}:${local.db_port}/${local.db_name}"
}

# Fernet key: proper Fernet format (32 random bytes, urlsafe base64, 44 chars,
# ADR-0010) — generated once, stored in state, stable across re-applies.
resource "random_password" "fernet_key" {
  length  = 44
  special = false
}

# random_password has no base64 flavor — override the result to be a valid
# Fernet key: 43 base64url chars encode 32 bytes, so keep only what decodes.
locals {
  fernet_key = base64encode(substr(sha256(random_password.fernet_key.result), 0, 32))
}

# ──────────────────────────────────────────────────────────────────────────────
# Secrets
# NOTE: bigbug-gitlab-token (ADR-0024) is NOT created here — base must apply
# in one command at cluster bootstrap, before GitLab (and its PAT) exist.
# That secret belongs to a later layer (apps/config, I6/I8) that runs after
# the config root has generated gitlab_backend_token.
# ──────────────────────────────────────────────────────────────────────────────
resource "kubernetes_secret" "db_credentials" {
  metadata {
    name      = "bigbug-db-credentials"
    namespace = var.namespace
  }

  data = {
    DATABASE_URL = local.database_url
    username     = local.db_user
    password     = local.db_password
    database     = local.db_name
    host         = local.db_host
    port         = local.db_port
  }
}

resource "kubernetes_secret" "fernet_key" {
  metadata {
    name      = "bigbug-fernet-key"
    namespace = var.namespace
  }

  data = {
    ENCRYPTION_KEY = local.fernet_key
  }
}

