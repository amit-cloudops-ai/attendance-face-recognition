output "api_routes" {
  description = "Part A and Part B API route map for the Part C access module."
  value       = merge(module.recognition.api_routes, module.data.api_routes)
}

output "tables" {
  description = "DynamoDB table names and ARNs."
  value       = module.data.tables
}

output "raw_bucket_name" {
  value = module.foundation.raw_bucket_name
}

output "reports_bucket_name" {
  value = module.foundation.reports_bucket_name
}

output "web_bucket_name" {
  value = module.foundation.web_bucket_name
}

output "kms_key_arn" {
  value = module.foundation.kms_key_arn
}

output "layer_arn" {
  value = module.foundation.layer_arn
}

output "alerts_topic_arn" {
  value = module.foundation.alerts_topic_arn
}

output "collection_id" {
  value = module.foundation.collection_id
}
