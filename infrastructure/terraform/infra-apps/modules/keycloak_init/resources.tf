/**
 * @file resources.tf
 * @description Keycloak install resources: ns, TLS + admin secrets, CNPG
 *              Cluster CR, keycloakx release.
 */

resource "kubernetes_namespace" "keycloak" {
  metadata { name = "keycloak" }
}

# TLS termination secret for the keycloakx ingress (ADR-0030)
resource "kubernetes_secret_v1" "tls_keycloak" {
  metadata {
    name      = "tls-keycloak-local"
    namespace = kubernetes_namespace.keycloak.metadata[0].name
  }

  type = "kubernetes.io/tls"

  data = {
    "tls.crt" = file("${var.certs_dir}/keycloak.local/tls.crt")
    "tls.key" = file("${var.certs_dir}/keycloak.local/tls.key")
  }
}

# KC_BOOTSTRAP_ADMIN_* (Keycloak 26) — takes effect on first (empty) DB init
resource "kubernetes_secret_v1" "keycloak_admin" {
  metadata {
    name      = "keycloak-admin-credentials"
    namespace = kubernetes_namespace.keycloak.metadata[0].name
  }

  data = {
    username = var.keycloak_admin_username
    password = var.keycloak_admin_password
  }
}

# Dedicated Postgres Cluster CR for Keycloak (issue #57). First apply on a
# fresh cluster requires the CNPG CRDs from base — apply base first.
# Operator-generated secret `keycloak-app` stays the source of DB creds.
resource "kubernetes_manifest" "cnpg_cluster_keycloak" {
  depends_on = [kubernetes_namespace.keycloak]

  manifest = {
    apiVersion = "postgresql.cnpg.io/v1"
    kind       = "Cluster"
    metadata = {
      name      = "keycloak"
      namespace = kubernetes_namespace.keycloak.metadata[0].name
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

resource "helm_release" "keycloakx" {
  depends_on = [kubernetes_manifest.cnpg_cluster_keycloak, kubernetes_secret_v1.keycloak_admin]

  name             = "keycloakx"
  repository       = "https://codecentric.github.io/helm-charts"
  chart            = "keycloakx"
  version          = "7.4.0" # appVersion keycloak 26.8.1; Renovate bumps
  namespace        = kubernetes_namespace.keycloak.metadata[0].name
  create_namespace = false # ns keycloak is tofu-managed above

  values = [templatefile("${path.module}/values/keycloakx.yaml", {
    keycloak_hostname = var.keycloak_hostname
  })]

  wait = true
}
