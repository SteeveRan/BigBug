/**
 * @file ingress.tf
 * @description haproxy-ingress — cluster ingress controller (ingressClass
 *              default). Host :80/:443 -> nodePort 30080/30443 via kind
 *              extraPortMappings.
 */

resource "helm_release" "haproxy_ingress" {
  name             = "haproxy-ingress"
  repository       = "https://haproxytech.github.io/helm-charts"
  chart            = "kubernetes-ingress"
  version          = "1.54.3" # latest chart; Renovate bumps
  namespace        = "haproxy-ingress"
  create_namespace = true

  values = [file("${path.module}/values/haproxy-ingress.yaml")]
}
