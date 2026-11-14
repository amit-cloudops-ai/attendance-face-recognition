output "kms_key_arn" {
  description = "Shared KMS key ARN."
  value       = aws_kms_key.attendance.arn
}

output "raw_bucket_name" {
  description = "Private raw biometric bucket name."
  value       = aws_s3_bucket.raw.bucket
}

output "raw_bucket_arn" {
  description = "Private raw biometric bucket ARN."
  value       = aws_s3_bucket.raw.arn
}

output "reports_bucket_name" {
  description = "Versioned reports bucket name."
  value       = aws_s3_bucket.reports.bucket
}

output "reports_bucket_arn" {
  description = "Versioned reports bucket ARN."
  value       = aws_s3_bucket.reports.arn
}

output "web_bucket_name" {
  description = "Private static web bucket name. CloudFront OAC policy is owned by the access module."
  value       = aws_s3_bucket.web.bucket
}

output "web_bucket_arn" {
  description = "Private static web bucket ARN."
  value       = aws_s3_bucket.web.arn
}

output "layer_arn" {
  description = "Published attendance_common Lambda layer ARN."
  value       = aws_lambda_layer_version.common.arn
}

output "alerts_topic_arn" {
  description = "SNS alerts topic ARN."
  value       = aws_sns_topic.alerts.arn
}

output "collection_id" {
  description = "Deterministic Rekognition collection ID shared with the recognition module."
  value       = "attendance-${var.env}-faces"
}

output "common_env" {
  description = "Shared environment variables for Part A and Part B Lambda modules."
  value = {
    TZ_NAME        = "Asia/Kolkata"
    LOG_LEVEL      = "INFO"
    BUCKET_REPORTS = aws_s3_bucket.reports.bucket
  }
}
