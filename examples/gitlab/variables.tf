/**
 * @file variables.tf
 * @description Input variables for the GitLab OpenTofu configuration.
 */

variable "gitlab_url" {
  description = "GitLab instance URL (e.g. http://localhost:8080)"
  type        = string
  default     = "http://localhost:8080"
}

variable "gitlab_token" {
  description = "GitLab root personal access token for initial provider authentication"
  type        = string
  sensitive   = true
}

variable "mirrors_group_name" {
  description = "GitLab group name for mirror repositories"
  type        = string
  default     = "bigbug-mirrors"
}

variable "backend_token_name" {
  description = "Name for the backend PAT"
  type        = string
  default     = "bigbug-backend-token"
}

variable "backend_token_expires_at" {
  description = "Expiration date for backend PAT (ISO 8601 format)"
  type        = string
  default     = "2027-12-31"
}

variable "backend_token_scopes" {
  description = "Scopes for the backend PAT"
  type        = list(string)
  default     = ["api", "read_repository", "write_repository"]
}
