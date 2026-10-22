/**
 * @file main.tf
 * @description Base in-cluster entities for the bigbug-dev kind cluster (ADR-0024).
 *
 * Scope: platform layer only — ingress controller, operators, their CRDs.
 * App instances (Harbor, keycloakx, app chart) live in ../apps (separate state).
 *
 * Prerequisite: kind cluster `bigbug-dev` created by ../kind/bootstrap.sh
 * (cluster + /etc/hosts stay imperative per ADR-0024).
 */

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.16"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.35"
    }
  }
}

provider "kubernetes" {
  config_path    = var.kubeconfig_path
  config_context = var.kubeconfig_context
}

provider "helm" {
  kubernetes {
    config_path    = var.kubeconfig_path
    config_context = var.kubeconfig_context
  }
}

# ──────────────────────────────────────────────────────────────────────────────
# haproxy-ingress — cluster ingress controller (ingressClass default)
# host :80/:443 -> nodePort 30080/30443 via kind extraPortMappings
# ──────────────────────────────────────────────────────────────────────────────
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
