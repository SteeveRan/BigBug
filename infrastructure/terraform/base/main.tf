/**
 * @file main.tf
 * @description Base in-cluster entities for the bigbug-dev kind cluster (ADR-0029).
 *
 * Scope: platform layer only — ingress controller, operators, their CRDs.
 * App instances (Harbor, keycloakx, app chart) live in ../apps (separate state).
 *
 * Prerequisite: kind cluster `bigbug-dev` created by ../kind/bootstrap.sh
 * (cluster + /etc/hosts stay imperative per ADR-0029).
 *
 * Layout (one file per logical unit, for reviewability):
 *   ingress.tf — haproxy-ingress (cluster ingress controller)
 *   cnpg.tf    — CNPG operator + Postgres cluster
 *   valkey.tf  — Valkey cache (deployment + service)
 *   secrets.tf — app k8s Secrets (module k8s-secrets, ADR-0024)
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
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
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

# Shared namespace for all base workloads below.
resource "kubernetes_namespace" "bigbug" {
  metadata { name = "bigbug" }
}
