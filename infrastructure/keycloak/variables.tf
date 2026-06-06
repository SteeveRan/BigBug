/**
 * @file variables.tf
 * @description Input variables for the Keycloak OpenTofu configuration.
 */

variable "keycloak_url" {
  description = "Keycloak server URL (e.g. http://localhost:8180)"
  type        = string
  default     = "http://localhost:8180"
}

variable "keycloak_admin_username" {
  description = "Keycloak admin username"
  type        = string
  default     = "admin"
  sensitive   = true
}

variable "keycloak_admin_password" {
  description = "Keycloak admin password"
  type        = string
  sensitive   = true
}

variable "realm_name" {
  description = "Keycloak realm name"
  type        = string
  default     = "bigbug"
}

variable "backend_client_id" {
  description = "Backend client ID (confidential)"
  type        = string
  default     = "bigbug-backend"
}

variable "backend_client_secret" {
  description = "Backend client secret"
  type        = string
  sensitive   = true
}

variable "frontend_client_id" {
  description = "Frontend client ID (public)"
  type        = string
  default     = "bigbug-frontend"
}

variable "frontend_redirect_uris" {
  description = "Frontend valid redirect URIs"
  type        = list(string)
  default     = [
    "http://localhost:5173/*",
    "http://localhost:5173/sso/callback",
  ]
}

variable "test_user_username" {
  description = "Test user username"
  type        = string
  default     = "bigbug"
}

variable "test_user_password" {
  description = "Test user password"
  type        = string
  sensitive   = true
}

variable "test_user_email" {
  description = "Test user email"
  type        = string
  default     = "bigbug@example.com"
}
