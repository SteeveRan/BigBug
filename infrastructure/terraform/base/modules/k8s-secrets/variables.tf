/**
 * @file variables.tf
 * @description Inputs for the k8s-secrets module (ADR-0024, issue #56).
 */

variable "namespace" {
  description = "Namespace where secrets are created (matches base layer ns bigbug)"
  type        = string
  default     = "bigbug"
}

variable "cnpg_app_secret_name" {
  description = "CNPG Cluster CR name — credentials read from <name>-app secret (operator convention)"
  type        = string
  default     = "bigbug-dev"
}
