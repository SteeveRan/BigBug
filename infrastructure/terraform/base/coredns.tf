/**
 * @file coredns.tf
 * @description CoreDNS Corefile with *.local hosts entries (ADR-0030 known
 *              tail: pods cannot resolve ingress hostnames — the host resolver
 *              answers .local with a synthetic `localhost` CNAME → pods hit
 *              themselves). Fix: hosts block pointing ingress hostnames at the
 *              HOST address (docker network gateway, where docker-proxy listens
 *              on 80/443 for kind extraPortMappings). The IP is discovered,
 *              not hardcoded — see data.external.kind_gateway.
 *
 * The ConfigMap is kubeadm-owned (no helm release); tofu adopts it as-is.
 * Full Corefile = kubeadm default + hosts block — keep in sync on k8s bumps.
 */

data "external" "kind_gateway" {
  program = ["${path.module}/scripts/kind-gateway.sh"]
}

locals {
  ingress_host = data.external.kind_gateway.result.gateway
}

# Kubeadm (kind) creates kube-system/coredns at cluster start; adopting it
# declaratively — import block is a no-op once the resource is in state.
import {
  to = kubernetes_config_map_v1.coredns
  id = "kube-system/coredns"
}

resource "kubernetes_config_map_v1" "coredns" {
  metadata {
    name      = "coredns"
    namespace = "kube-system"
    labels = {
      "k8s-app" = "kube-dns"
    }
  }

  data = {
    Corefile = <<-EOF
      .:53 {
          errors
          health {
             lameduck 5s
          }
          ready
          kubernetes cluster.local in-addr.arpa ip6.arpa {
             pods insecure
             fallthrough in-addr.arpa ip6.arpa
             ttl 30
          }
          prometheus :9153
          forward . /etc/resolv.conf {
             max_concurrent 1000
          }
          cache 30 {
             disable success cluster.local
             disable denial cluster.local
          }
          loop
          reload
          loadbalance
          hosts {
              ${local.ingress_host} keycloak.local
              ${local.ingress_host} harbor.local
              ${local.ingress_host} app.local
              ${local.ingress_host} api.local
              ${local.ingress_host} gitlab.local
              fallthrough
          }
      }
    EOF
  }
}
