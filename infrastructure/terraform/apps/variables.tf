/**
 * @file variables.tf
 * @description Input variables for the apps root.
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

variable "keycloak_hostname" {
  description = "External hostname of Keycloak (ingress host, ADR-0022 addressing)"
  type        = string
  default     = "keycloak.local"
}

variable "keycloak_admin_username" {
  description = "Keycloak bootstrap admin username (only used on first DB init)"
  type        = string
  default     = "admin"
}

variable "keycloak_admin_password" {
  description = "Keycloak bootstrap admin password (only used on first DB init)"
  type        = string
  default     = "admin"
}
