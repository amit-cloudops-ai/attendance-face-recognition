# Data and automation Terraform module

Creates the five contract tables (employees, attendance with `date-index`, scan-results with TTL, config, audit), Part B Lambda functions, Asia/Kolkata daily/weekly EventBridge Scheduler schedules, least-privilege IAM, 30-day log groups and CloudWatch error/throttle alarms.

## Inputs

The caller supplies the shared KMS key, raw and reports bucket names, reports bucket ARN, deterministic Rekognition collection ID, common Lambda layer, SNS alerts topic and common environment variables (`TZ_NAME`, `LOG_LEVEL`).

## Outputs

- `tables`: typed table names and ARNs consumed by the recognition module.
- `api_routes`: employee, attendance and report routes consumed by the access module.

## Safety

This module only defines infrastructure. Run `terraform init` and `terraform validate` for static validation; do not run `terraform apply` without explicit deployment approval. The module packages Python handlers from `services/data/<function>/` and uses the shared `attendance_common` layer.
