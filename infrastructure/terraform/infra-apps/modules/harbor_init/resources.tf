/**
 * @file resources.tf
 * @description Harbor install resources: ns, TLS secrets, chart release.
 */

resource "kubernetes_namespace" "harbor" {
  metadata { name = "harbor" }
}

# TLS termination secret for the harbor ingress (ADR-0030 §5)
resource "kubernetes_secret_v1" "tls_harbor" {
  metadata {
    name      = "tls-harbor-local"
    namespace = kubernetes_namespace.harbor.metadata[0].name
  }

  type = "kubernetes.io/tls"

  data = {
    "tls.crt" = file("${var.certs_dir}/harbor.local/tls.crt")
    "tls.key" = file("${var.certs_dir}/harbor.local/tls.key")
  }
}

# chart contract: exactly the `ca.crt` key — keycloak.local cert mounted into
# core/jobservice/registry trust stores for oidc_verify_cert (ADR-0030 §4)
resource "kubernetes_secret_v1" "harbor_ca_bundle" {
  metadata {
    name      = "harbor-ca-bundle"
    namespace = kubernetes_namespace.harbor.metadata[0].name
  }

  data = {
    "ca.crt" = file("${var.certs_dir}/keycloak.local/tls.crt")
  }
}

resource "helm_release" "harbor" {
  depends_on = [kubernetes_namespace.harbor]

  name             = "harbor"
  repository       = "https://helm.goharbor.io"
  chart            = "harbor"
  version          = var.harbor_chart_version # Renovate bumps
  namespace        = kubernetes_namespace.harbor.metadata[0].name
  create_namespace = false # ns harbor is tofu-managed above

  values = [file("${path.module}/values/harbor.yaml")]

  wait    = true
  timeout = 600
}
