/**
 * @file main.tf
 * @description Terraform provider configuration for Keycloak module
 * @provider mrparkers/keycloak ~> 4.0
 */

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    keycloak = {
      source  = "mrparkers/keycloak"
      version = "~> 4.0"
    }
  }
}
