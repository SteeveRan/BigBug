/**
 * @file harbor.tf
 * @description Harbor (goharbor chart) in ns `harbor` — issue #58.
 *
 * Endpoint: http://harbor.local via chart-managed Ingress (haproxy, port 80,
 * no TLS in dev — ADR-0022 addressing, D4). Notary/Trivy disabled (dev budget),
 * chartmuseum does not exist in chart 1.19.x (removed upstream).
 *
 * Registry usage: TLS disabled → the port is mandatory in docker commands
 * (see harbor issue #5291): `harbor.local:80`, configured as insecure-registry
 * on the host by ../kind/bootstrap.sh.
 *
 * Ordering: needs base layer (haproxy-ingress) — see main.tf header.
 */

resource "kubernetes_namespace" "harbor" {
  metadata { name = "harbor" }
}

resource "helm_release" "harbor" {
  depends_on = [kubernetes_namespace.harbor]

  name             = "harbor"
  repository       = "https://helm.goharbor.io"
  chart            = "harbor"
  version          = "1.19.4" # appVersion harbor 2.15.4; Renovate bumps
  namespace        = "harbor"
  create_namespace = false # ns harbor is tofu-managed above

  values = [file("${path.module}/values/harbor.yaml")]

  wait = true
  timeout = 600
}
