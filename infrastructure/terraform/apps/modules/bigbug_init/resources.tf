/**
 * @file resources.tf
 * @description App resources in ns `bigbug`: namespace, CNPG Cluster CR,
 *              Redis CR (redis-operator from base), app secrets (ADR-0024),
 *              TLS secrets + CA-bundle (ADR-0030 §5/§4).
 */

resource "kubernetes_namespace" "bigbug" {
  metadata { name = "bigbug" }
}

# ── CNPG Postgres Cluster (DB `bigbug`) ──────────────────────────────────────
# Same sizing as the keycloak cluster (#57). Operator-generated secret
# `bigbug-dev-app` is the source of DB creds; the helm-chart contract secret
# below is a projection of it (never a manual copy).
resource "kubernetes_manifest" "cnpg_cluster_bigbug" {
  depends_on = [kubernetes_namespace.bigbug]

  manifest = {
    apiVersion = "postgresql.cnpg.io/v1"
    kind       = "Cluster"
    metadata = {
      name      = "bigbug-dev"
      namespace = kubernetes_namespace.bigbug.metadata[0].name
    }
    spec = {
      instances = 1
      bootstrap = {
        initdb = {
          database = "bigbug"
          owner    = "bigbug"
          # Post-init: app role may create per-worktree DBs (multi-agent
          # discipline — make dev-db-create / migrate-check.sh, issue #62).
          postInitSQL = [
            "ALTER ROLE bigbug CREATEDB",
          ]
        }
      }
      storage = {
        size = var.cnpg_storage_size
      }
      resources = {
        requests = {
          cpu    = "100m"
          memory = "256Mi"
        }
        limits = {
          memory = "512Mi"
        }
      }
    }
  }
}

# ── Redis cache instance (redis-operator from base) ──────────────────────────
resource "kubernetes_manifest" "redis_cache" {
  depends_on = [kubernetes_namespace.bigbug]

  manifest = {
    apiVersion = "redis.redis.opstreelabs.in/v1beta2"
    kind       = "Redis"
    metadata = {
      name      = "bigbug-cache"
      namespace = kubernetes_namespace.bigbug.metadata[0].name
    }
    spec = {
      kubernetesConfig = {
        image           = "quay.io/opstree/redis:v7.0.15"
        imagePullPolicy = "IfNotPresent"
        resources = {
          requests = {
            cpu    = "50m"
            memory = "64Mi"
          }
          limits = {
            memory = "128Mi"
          }
        }
      }
      storage = {
        volumeClaimTemplate = {
          spec = {
            accessModes = ["ReadWriteOnce"]
            resources = {
              requests = {
                storage = "1Gi"
              }
            }
          }
        }
      }
    }
  }
}

# ── App secrets (ADR-0024 §1 table) ──────────────────────────────────────────
# DB credentials: NOT a manual copy — project the operator-owned fields of the
# CNPG-generated secret `bigbug-dev-app` into the helm-chart contract secret.
data "kubernetes_secret_v1" "cnpg_app" {
  depends_on = [kubernetes_manifest.cnpg_cluster_bigbug]

  metadata {
    name      = "bigbug-dev-app"
    namespace = kubernetes_namespace.bigbug.metadata[0].name
  }
}

locals {
  db_user     = data.kubernetes_secret_v1.cnpg_app.data["user"]
  db_password = data.kubernetes_secret_v1.cnpg_app.data["password"]
  db_host     = "bigbug-dev-rw.${kubernetes_namespace.bigbug.metadata[0].name}.svc"
  db_port     = data.kubernetes_secret_v1.cnpg_app.data["port"]
  db_name     = data.kubernetes_secret_v1.cnpg_app.data["dbname"]

  database_url = "postgresql+asyncpg://${local.db_user}:${local.db_password}@${local.db_host}:${local.db_port}/${local.db_name}"
}

resource "kubernetes_secret_v1" "db_credentials" {
  metadata {
    name      = "bigbug-db-credentials"
    namespace = kubernetes_namespace.bigbug.metadata[0].name
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

resource "kubernetes_secret_v1" "fernet_key" {
  metadata {
    name      = "bigbug-fernet-key"
    namespace = kubernetes_namespace.bigbug.metadata[0].name
  }

  data = {
    ENCRYPTION_KEY = local.fernet_key
  }
}

# Backend OIDC client credentials (client lives in ../keycloak_conf)
resource "kubernetes_secret_v1" "keycloak_oidc" {
  metadata {
    name      = "bigbug-keycloak-oidc"
    namespace = kubernetes_namespace.bigbug.metadata[0].name
  }

  data = {
    client_id     = var.backend_client_id
    client_secret = var.backend_client_secret
  }
}

# ── TLS secrets + CA bundle (ADR-0030 §5/§4) ─────────────────────────────────
# Termination secrets for the app chart ingress; ingress references them, pods
# stay http. The CA bundle (public certs, ConfigMap) is mounted into the
# backend pod with REQUESTS_CA_BUNDLE so verify_ssl=True works (ADR-0030 §4).
resource "kubernetes_secret_v1" "tls_api" {
  metadata {
    name      = "tls-api-local"
    namespace = kubernetes_namespace.bigbug.metadata[0].name
  }

  type = "kubernetes.io/tls"

  data = {
    "tls.crt" = file("${var.certs_dir}/api.local/tls.crt")
    "tls.key" = file("${var.certs_dir}/api.local/tls.key")
  }
}

resource "kubernetes_secret_v1" "tls_app" {
  metadata {
    name      = "tls-app-local"
    namespace = kubernetes_namespace.bigbug.metadata[0].name
  }

  type = "kubernetes.io/tls"

  data = {
    "tls.crt" = file("${var.certs_dir}/app.local/tls.crt")
    "tls.key" = file("${var.certs_dir}/app.local/tls.key")
  }
}

resource "kubernetes_config_map_v1" "ca_bundle" {
  metadata {
    name      = "bigbug-ca-bundle"
    namespace = kubernetes_namespace.bigbug.metadata[0].name
  }

  # Single CA (certs.sh: all host certs are signed by it — ADR-0030 §2
  # rev. 2026-10-24). The entrypoint merges this with the system roots
  # into the pod's SSL_CERT_FILE/REQUESTS_CA_BUNDLE bundle.
  data = {
    "ca-bundle.crt" = file("${var.certs_dir}/ca.crt")
  }
}
