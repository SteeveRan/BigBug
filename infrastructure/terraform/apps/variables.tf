/**
 * @file variables.tf
 * @description Input variables for the BigBug app-infra root.
 */

variable "kubeconfig_path" {
  description = "Path to kubeconfig of the target cluster"
  type        = string
  default     = "~/.kube/config"
}

variable "kubeconfig_context" {
  description = "kubeconfig context to use (kind-bigbug-dev for dev)"
  type        = string
  default     = "kind-bigbug-dev"
}

variable "cnpg_storage_size" {
  description = "CNPG cluster storage size (dev default)"
  type        = string
  default     = "5Gi"
}

variable "backend_client_id" {
  description = "OIDC client ID for BigBug backend (client lives in infra-apps/keycloak_conf)"
  type        = string
  default     = "bigbug-backend"
}

variable "backend_client_secret" {
  description = "OIDC client secret for BigBug backend (must match keycloak_conf in infra-apps)"
  type        = string
  sensitive   = true
  default     = "bigbug-backend-secret"
}
