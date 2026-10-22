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
