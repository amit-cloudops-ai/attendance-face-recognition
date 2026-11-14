# Runtime execution-role permissions boundaries

This directory contains environment-specific AWS IAM permissions-boundary templates for the Lambda and EventBridge Scheduler execution roles.

## Files

- `execution-role-boundary-dev.json.tftpl` — dev-only resource ARNs and KMS alias.
- `execution-role-boundary-prod.json.tftpl` — prod-only resource ARNs and KMS alias.

The templates use Terraform template interpolation for `${account_id}`. They are not attachable until rendered with the verified 12-digit AWS account ID. The target region is fixed to `us-east-1`.

## Security model

A permissions boundary is a maximum-permissions control, not a grant. These policies define the union of runtime permissions that any application Lambda or Scheduler role may receive. Each role's own inline policy remains responsible for granting only its handler-specific operations.

The boundary allow-list includes:
- Exact environment DynamoDB table ARNs and the attendance date-index ARN.
- Raw S3 `captures/*` and `enroll/*` object prefixes, and report-bucket `reports/*` objects.
- The environment KMS key only when it carries `alias/attendance-<env>` and the request is made through S3 or SQS in `us-east-1`.
- The environment Rekognition collection; `DetectFaces` uses `Resource: "*"` because AWS does not support resource-level permissions for that action.
- The two encrypted recognition DLQs for producer/consumer operations. The failure-processor redrive target is deliberately excluded from direct Lambda role queue access.
- The environment alerts topic for `sns:Publish`.
- Only the daily and weekly Lambda functions for Scheduler `lambda:InvokeFunction`.
- Log stream creation and log event writes to the environment's Lambda log groups.

The boundary does not allow IAM role/policy management, `iam:PassRole`, STS role assumption, resource provisioning, bucket listing, table deletion, log-group creation, or KMS key administration. No boundary self-management path is included.

## Rendering and validation

Render each file with Terraform's `templatefile` function or an equivalent trusted template renderer, supplying the actual account ID. Validate the rendered JSON and review every ARN before creating the customer-managed IAM policy. Do not store credentials in this repository.

Example Terraform expression:

```hcl
locals {
  dev_boundary_policy = templatefile(
    "${path.module}/execution-role-boundary-dev.json.tftpl",
    { account_id = var.account_id }
  )
}
```

The current repository does not create or attach these managed policies. Bootstrap remains a separately reviewed, explicitly approved manual operation. Do not create policies or attach boundaries until the owner approves the exact bootstrap plan.

## Evidence and limitations

- Runtime action/resource union is based on the data and recognition handler audits in `docs/IAM-LEAST-PRIVILEGE-INVENTORY.md`.
- AWS KMS conditions `kms:ResourceAliases` and `kms:ViaService` are documented for IAM policies; S3 and SQS are supported `kms:ViaService` integrations.
- Static JSON/template validation does not prove live AWS authorization. Validate the rendered policy with IAM Access Analyzer and an approved non-production deployment before relying on it.


## Dev Terraform plan-role policies

The dev plan role uses three separate customer-managed policy templates so each remains below the IAM managed-policy size limit:

- `github-plan-dev-core.json.tftpl` — read-only DynamoDB, IAM role/inline-policy, Lambda, Scheduler, SQS, Rekognition, CloudWatch, SNS and Budget reads.
- `github-plan-dev-edge.json.tftpl` — read-only KMS, S3 bucket/object metadata, Cognito, API Gateway v2 and CloudFront reads.
- `github-plan-dev-state.json.tftpl` — dev state object read and S3 native lockfile lifecycle.

Render with:
- `account_id`: verified 12-digit AWS account ID.
- `state_bucket`: exact bootstrap-created S3 state bucket name.

The plan role receives no infrastructure create/update/delete permissions. The only write/delete actions are `s3:PutObject` and `s3:DeleteObject` on `attendance/dev/terraform.tfstate.tflock`, because the S3 backend must acquire and release its state lock. The state object itself is read-only. The state bucket list operation is restricted to the dev state and lock prefixes. No prod state key or prod resource ARN is present.

The plan policies intentionally include `s3:ListBucket` on the three dev application buckets because the reviewed AWS provider v6.73.0 `aws_s3_bucket` refresh path performs HeadBucket, which is authorized by `s3:ListBucket`. This reveals object-key metadata, not object contents; no raw-bucket object read permission is granted to the plan role.

Cognito pool IDs and CloudFront distribution IDs are service-generated. The templates use service-supported resource ARN patterns and tag conditions where available. Some CloudFront policy families do not support resource tags; their read actions are restricted to the corresponding CloudFront resource family and remain read-only. API Gateway v2 IDs are also service-generated, and the provider configuration does not tag each authorizer/integration/route/stage child independently. The dev plan policy therefore grants only the `apigateway:GET` verb over the `/apis` resource family; this is read-only but can expose metadata for other APIs in the account/region. A post-bootstrap tightening task should replace the wildcard API ID with the generated dev API ID where operationally practical.

The templates are policy source, not an AWS deployment. CI renders them with a dummy account/bucket, validates JSON, checks the 6,144-character managed-policy limit, rejects infrastructure mutation actions from core/edge policies, and ensures dev state permissions cannot reach prod keys. The exact account and state bucket values must be reviewed before bootstrap.
