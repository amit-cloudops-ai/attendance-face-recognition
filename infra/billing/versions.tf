terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 6.73.0"
    }
  }

  backend "s3" {
    key          = "attendance/billing/terraform.tfstate"
    encrypt      = true
    use_lockfile = true
  }
}

locals {
  deployment_region = jsondecode(file("${path.module}/../../config/deployment.json")).aws_region
}

provider "aws" {
  region              = local.deployment_region
  allowed_account_ids = [var.account_id]
}
