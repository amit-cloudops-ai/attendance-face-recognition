# Foundation Terraform module

Creates the shared KMS key, private raw/reports/web buckets, SSE-KMS bucket encryption, public-access blocks, raw-image lifecycle backstop, report-bucket versioning, common Python Lambda layer, encrypted SNS alerts topic. AWS Budgets are isolated in the separate `infra/billing` root and are not part of normal environment deployments.

## Inputs

- `env`: `dev` or `prod`
- `account_id`: 12-digit AWS account ID for globally unique bucket names
- `alert_email`: email for SNS and budget notifications; confirm the SNS subscription from the email AWS sends

## Outputs

KMS key, raw/reports/web bucket names and ARNs, common Lambda layer ARN, alerts topic ARN, deterministic Rekognition collection ID, and shared Lambda environment variables.

## Ownership boundaries

The raw bucket has no versioning and expires `captures/` and `enroll/` after one day as a safety net; handlers must delete each uploaded image immediately. The reports bucket is versioned. The web bucket remains private; the Part C access module owns its CloudFront OAC bucket policy so there is only one bucket-policy resource.

## Safety

This module only defines infrastructure. Static validation is allowed; do not run `terraform apply` without explicit deployment approval.
