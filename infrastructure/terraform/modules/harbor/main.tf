/**
 * @file main.tf
 * @description Terraform provider configuration for Harbor module
 * @provider goharbor/harbor ~> 3.12
 */

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    harbor = {
      source  = "goharbor/harbor"
      version = "~> 3.12"
    }
  }
}

provider "harbor" {
  url      = var.harbor_url
  username = var.harbor_username
  password = var.harbor_password
}
