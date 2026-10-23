/**
 * @file main.tf
 * @description Terraform provider configuration for Keycloak module
 * @provider keycloak/keycloak ~> 5.0
 */

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    keycloak = {
      source  = "keycloak/keycloak"
      version = "~> 5.0"
    }
  }
}
