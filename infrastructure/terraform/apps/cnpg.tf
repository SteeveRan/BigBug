/**
 * @file cnpg.tf
 * @description Dedicated Postgres Cluster CR for Keycloak (ADR-0029: app
 *              instances live in apps; issue #57 — "cluster postgres отдельным
 *              CR"). One cluster `keycloak` in ns `keycloak`, database
 *              `keycloak`, owner `keycloak`. The app DB cluster (bigbug) is
 *              a separate CR — I6.
 *
 * First apply on a fresh cluster requires the CRDs from base (operator helm
 * release) — apply base first, see main.tf header.
 *
 * Operator-generated secret (consumers read creds from it, operator stays
 * source of truth): `keycloak-app` in ns `keycloak` — keys user/password/
 * host/port/dbname/uri/jdbc-uri. RW service: keycloak-rw.keycloak.svc:5432.
 *
 * Dev stand: single instance, no HA (ADR-0022). Deleting the cluster (kind
 * teardown) drops all postgres data — acceptable for dev.
 */

resource "kubernetes_manifest" "cnpg_cluster_keycloak" {
  depends_on = [kubernetes_namespace.keycloak]

  manifest = {
    apiVersion = "postgresql.cnpg.io/v1"
    kind       = "Cluster"
    metadata = {
      name      = "keycloak"
      namespace = "keycloak"
    }
    spec = {
      instances = 1
      bootstrap = {
        initdb = {
          database = "keycloak"
          owner    = "keycloak"
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
