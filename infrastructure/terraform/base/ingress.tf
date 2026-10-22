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
  namespace        = "haproxy-ingress"
  create_namespace = true

  set {
    name  = "controller.ingressClassResource.default"
    value = "true"
  }

  # Must match extraPortMappings in ../kind/kind-config.yaml
  set {
    name  = "controller.service.nodePorts.http"
    value = "30080"
  }
  set {
    name  = "controller.service.nodePorts.https"
    value = "30443"
  }
}
