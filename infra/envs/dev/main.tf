module "foundation" {
  source = "../../modules/foundation"

  env         = var.env
  account_id  = var.account_id
  alert_email = var.alert_email
}

module "data" {
  source = "../../modules/data"

  env                 = var.env
  kms_key_arn         = module.foundation.kms_key_arn
  raw_bucket_name     = module.foundation.raw_bucket_name
  reports_bucket_name = module.foundation.reports_bucket_name
  reports_bucket_arn  = module.foundation.reports_bucket_arn
  collection_id       = module.foundation.collection_id
  layer_arn           = module.foundation.layer_arn
  alerts_topic_arn    = module.foundation.alerts_topic_arn
  common_env          = module.foundation.common_env
}

module "recognition" {
  source = "../../modules/recognition"

  env              = var.env
  account_id       = var.account_id
  kms_key_arn      = module.foundation.kms_key_arn
  raw_bucket_name  = module.foundation.raw_bucket_name
  raw_bucket_arn   = module.foundation.raw_bucket_arn
  tables           = module.data.tables
  layer_arn        = module.foundation.layer_arn
  alerts_topic_arn = module.foundation.alerts_topic_arn
  common_env       = module.foundation.common_env
}
