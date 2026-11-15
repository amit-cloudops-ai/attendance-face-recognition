import {
  to = module.access.aws_apigatewayv2_api.http
  id = var.api_id
}

module "foundation" {
  source = "../../modules/foundation"

  env                = var.env
  account_id         = var.account_id
  alert_email        = var.alert_email
  raw_upload_origins = var.allowed_origins
}

module "data" {
  source = "../../modules/data"

  env                         = var.env
  account_id                  = var.account_id
  execution_role_boundary_arn = var.execution_role_boundary_arn
  kms_key_arn                 = module.foundation.kms_key_arn
  raw_bucket_name             = module.foundation.raw_bucket_name
  reports_bucket_name         = module.foundation.reports_bucket_name
  reports_bucket_arn          = module.foundation.reports_bucket_arn
  collection_id               = module.foundation.collection_id
  layer_arn                   = module.foundation.layer_arn
  alerts_topic_arn            = module.foundation.alerts_topic_arn
  common_env                  = module.foundation.common_env
}

module "recognition" {
  source = "../../modules/recognition"

  env                         = var.env
  execution_role_boundary_arn = var.execution_role_boundary_arn
  account_id                  = var.account_id
  kms_key_arn                 = module.foundation.kms_key_arn
  raw_bucket_name             = module.foundation.raw_bucket_name
  raw_bucket_arn              = module.foundation.raw_bucket_arn
  tables                      = module.data.tables
  layer_arn                   = module.foundation.layer_arn
  alerts_topic_arn            = module.foundation.alerts_topic_arn
  common_env                  = module.foundation.common_env
}

module "access" {
  source = "../../modules/access"

  region                          = local.deployment_region
  env                             = var.env
  account_id                      = var.account_id
  kms_key_id                      = module.foundation.kms_key_id
  raw_bucket_name                 = module.foundation.raw_bucket_name
  web_bucket_name                 = module.foundation.web_bucket_name
  web_bucket_arn                  = module.foundation.web_bucket_arn
  web_bucket_regional_domain_name = module.foundation.web_bucket_regional_domain_name
  api_routes                      = merge(module.recognition.api_routes, module.data.api_routes)
  callback_urls                   = var.callback_urls
  logout_urls                     = var.logout_urls
  allowed_origins                 = var.allowed_origins
}
