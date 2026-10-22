/**
 * @file main.tf
 * @description App instances in the bigbug-dev kind cluster (ADR-0029).
 *
 * Scope: Keycloak stack only (issue #57) — own namespace, own CNPG Postgres
 * Cluster CR, keycloakx chart release with chart-managed Ingress.
 * The app namespace `bigbug` (backend/frontend/cache/app secrets) is NOT
 * here — it belongs to the app chart (I6).
 *
 * Platform layer (ingress, operators) lives in ../base (separate state).
 * Service configuration via their APIs (realm, clients) lives in ../
 * (config root, ADR-0013).
 *
 * Prerequisite (in order):
 *   1. kind cluster `bigbug-dev` — ../kind/bootstrap.sh
 *   2. base layer (CNPG operator + CRDs) — cd ../base && tofu apply
 *   3. this root: tofu init && tofu apply
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

resource "kubernetes_namespace" "keycloak" {
  metadata { name = "keycloak" }
}
