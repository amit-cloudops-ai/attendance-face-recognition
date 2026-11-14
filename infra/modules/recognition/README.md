# Recognition Terraform module

This module owns the Part A resources: six Python 3.12 Lambdas, one Rekognition collection, the raw-bucket event notifications, two encrypted SQS DLQs, per-function IAM roles, 30-day log groups and CloudWatch alarms.

## Inputs

The caller supplies the shared KMS key, raw bucket, DynamoDB table names/ARNs, common Lambda layer, alerts topic, AWS account ID and common environment variables. `common_env` must include `TZ_NAME`, `LOG_LEVEL` and `BUCKET_REPORTS`; the module supplies the contract table names, `BUCKET_RAW`, `ENV` and `COLLECTION_ID`.

## Outputs

- `api_routes`: four API routes consumed by the access module.
- `collection_id`: Rekognition collection identifier.
- `recognize_function_name`: recognition worker name.

## Safety

This module only defines infrastructure. Do not run `terraform apply` as part of local validation. Apply is a separate, explicitly approved deployment action after the foundation and data modules are ready.

The module packages each handler from `services/recognition/<function>/` and relies on the supplied `attendance_common` layer. It intentionally defines the raw bucket notification in one resource for both `captures/` and `enroll/` prefixes.
