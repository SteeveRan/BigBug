/**
 * @file keycloak.tf
 * @description Keycloak (keycloakx chart, codecentric) in ns `keycloak` — issue #57.
 *
 * DB: CNPG database `keycloak` (not embedded H2) — credentials come straight
 * from the operator-generated secret `keycloak-app` (no copy, no #56 module
 * needed for Keycloak itself).
 *
 * Admin bootstrap: KC_BOOTSTRAP_ADMIN_* env (Keycloak 26) — secret is
 * tofu-managed and only takes effect on first (empty) DB init.
 *
 * Endpoint: https://keycloak.local — TLS terminates on haproxy-ingress with
 * the `tls-keycloak-local` secret (certs from ../../kind/certs.sh, ADR-0030);
 * pod-to-pod stays http. Harbor OIDC (oidc_verify_cert: true) verifies this
 * cert via the harbor-ca-bundle secret.
 * http.relativePath "/" keeps URLs identical to the retired compose setup
 * (no /auth prefix).
 *
 * Ordering: helm release depends_on the Cluster CR; the chart's dbchecker
 * init container waits for Postgres readiness itself.
 */

resource "kubernetes_secret_v1" "tls_keycloak" {
  metadata {
    name      = "tls-keycloak-local"
    namespace = "keycloak"
  }

  type = "kubernetes.io/tls"

  data = {
    "tls.crt" = file("${path.module}/../../kind/certs/keycloak.local/tls.crt")
    "tls.key" = file("${path.module}/../../kind/certs/keycloak.local/tls.key")
  }
}

resource "kubernetes_secret_v1" "keycloak_admin" {
  metadata {
    name      = "keycloak-admin-credentials"
    namespace = "keycloak"
  }

  data = {
    username = var.keycloak_admin_username
    password = var.keycloak_admin_password
  }
}

resource "helm_release" "keycloakx" {
  depends_on = [kubernetes_manifest.cnpg_cluster_keycloak, kubernetes_secret_v1.keycloak_admin]

  name             = "keycloakx"
  repository       = "https://codecentric.github.io/helm-charts"
  chart            = "keycloakx"
  version          = "7.4.0" # appVersion keycloak 26.8.1; Renovate bumps
  namespace        = "keycloak"
  create_namespace = false # ns keycloak is tofu-managed above

  values = [templatefile("${path.module}/values/keycloakx.yaml", {
    keycloak_hostname = var.keycloak_hostname
  })]

  wait = true
}
