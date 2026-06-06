/**
 * @file main.tf
 * @description OpenTofu/Terraform provider configuration for Keycloak
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

provider "keycloak" {
  client_id = "admin-cli"
  username  = var.keycloak_admin_username
  password  = var.keycloak_admin_password
  url       = var.keycloak_url
}
