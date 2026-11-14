terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 6.73.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "= 2.8.1"
    }
  }

  backend "s3" {
    key          = "attendance/dev/terraform.tfstate"
    encrypt      = true
    use_lockfile = true
  }
}

locals {
  deployment_region = jsondecode(file("${path.module}/../../../config/deployment.json")).aws_region
}

provider "aws" {
  region = local.deployment_region
}
