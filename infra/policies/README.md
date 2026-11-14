# Runtime execution-role permissions boundaries

This directory contains environment-specific AWS IAM permissions-boundary templates for the Lambda and EventBridge Scheduler execution roles.

## Files

- `execution-role-boundary-dev.json.tftpl` — dev-only resource ARNs and KMS alias.
- `execution-role-boundary-prod.json.tftpl` — prod-only resource ARNs and KMS alias.

The templates use Terraform template interpolation for `${account_id}`. They are not attachable until rendered with the verified 12-digit AWS account ID. All regional ARNs must match the canonical region in `config/deployment.json` (`us-east-1`); CI checks regional ARNs and service endpoints for drift.

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
- AWS KMS conditions `kms:ResourceAliases` and `kms:ViaService` are documented for IAM policies; S3, SQS and SNS are included as the runtime forward-access integrations used by this project.
- Static JSON/template validation does not prove live AWS authorization. Validate the rendered policy with IAM Access Analyzer and an approved non-production deployment before relying on it.


## Dev Terraform plan-role policies

The dev plan role uses three separate customer-managed policy templates so each remains below the IAM managed-policy size limit:

- `github-plan-dev-core.json.tftpl` — read-only DynamoDB, IAM role/inline-policy, Lambda, Scheduler, SQS, Rekognition, CloudWatch and SNS reads. Billing reads are isolated to the dedicated billing plan role.
- `github-plan-dev-edge.json.tftpl` — read-only KMS, S3 bucket/object metadata, Cognito, API Gateway v2 and CloudFront reads.
- `github-plan-dev-state.json.tftpl` — dev state object read and S3 native lockfile lifecycle.

Render with:
- `account_id`: verified 12-digit AWS account ID.
- `state_bucket`: exact bootstrap-created S3 state bucket name.

The plan role receives no infrastructure create/update/delete permissions. The only write/delete actions are `s3:PutObject` and `s3:DeleteObject` on `attendance/dev/terraform.tfstate.tflock`, because the S3 backend must acquire and release its state lock. The state object itself is read-only. The state bucket list operation is restricted to the dev state and lock prefixes. No prod state key or prod resource ARN is present.

The plan policies intentionally include `s3:ListBucket` on the three dev application buckets because the reviewed AWS provider v6.73.0 `aws_s3_bucket` refresh path performs HeadBucket, which is authorized by `s3:ListBucket`. This reveals object-key metadata, not object contents; no raw-bucket object read permission is granted to the plan role.

Cognito pool IDs and CloudFront distribution IDs are service-generated. The templates use service-supported resource ARN patterns and tag conditions where available. Some CloudFront policy families do not support resource tags; their read actions are restricted to the corresponding CloudFront resource family and remain read-only. API Gateway v2 IDs are also service-generated, and the provider configuration does not tag each authorizer/integration/route/stage child independently. The dev plan policy therefore grants only the `apigateway:GET` verb over the `/apis` resource family; this is read-only but can expose metadata for other APIs in the account/region. A post-bootstrap tightening task should replace the wildcard API ID with the generated dev API ID where operationally practical.

The templates are policy source, not an AWS deployment. CI renders them with a dummy account/bucket, validates JSON, checks the 6,144-character managed-policy limit, rejects infrastructure mutation actions from core/edge policies, and ensures dev state permissions cannot reach prod keys. The exact account and state bucket values must be reviewed before bootstrap.


## DynamoDB customer-managed KMS key deployment permissions

The data module creates all five tables with the foundation customer-managed key. The final key policy therefore includes the AWS-documented DynamoDB model:

- Account principals can use the key for DynamoDB only when `kms:CallerAccount` matches the account and `kms:ViaService` is `dynamodb.us-east-1.amazonaws.com`. The statement grants `kms:Encrypt`, `kms:Decrypt`, `kms:ReEncrypt*`, `kms:GenerateDataKey*`, `kms:CreateGrant` and `kms:DescribeKey`.
- The direct `dynamodb.amazonaws.com` metadata statement is intentionally omitted because AWS documents it in the AWS-managed-key example, not the customer-managed-key policy example.
- Deployment identities still need matching IAM permissions. `infra/policies/github-apply-dev-dynamodb-kms.json.tftpl` and the prod equivalent scope cryptographic actions to the environment alias and DynamoDB ViaService. `kms:CreateGrant` is separate and requires `kms:GrantIsForAWSResource=true`.

AWS source: [DynamoDB encryption at rest usage notes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/encryption.usagenotes.html). These are policy templates only; they have not been attached to any AWS identity.


## Dev Terraform apply-role policy set (T10)

The dev apply role is intentionally split into multiple customer-managed policies so each remains below the IAM managed-policy size ceiling:

- `github-apply-dev-core.json.tftpl` — SQS queues, Scheduler group/schedules, CloudWatch log groups/alarms, and raw-bucket notification configuration.
- `github-apply-dev-data.json.tftpl` — exact five DynamoDB table ARNs and the attendance date GSI.
- `github-apply-dev-lambda.json.tftpl` — exact 14 Lambda function ARNs, Lambda invoke configuration/permissions, failure-processor event-source mapping, and the versioned common layer.
- `github-apply-dev-iam.json.tftpl` — exact 14 Lambda role ARNs plus the two Scheduler role ARNs; role creation requires the exact dev execution boundary; PassRole is separated by Lambda and Scheduler service.
- `github-apply-dev-foundation.json.tftpl` — KMS key/alias lifecycle, S3 bucket configuration, SNS topic/subscription and Lambda layer publish.
- `github-apply-dev-access.json.tftpl` — Cognito, API Gateway v2, CloudFront, web bucket policy and frontend objects.
- `github-apply-dev-state.json.tftpl` — dev state read/write and dev lockfile lifecycle only.
- `github-apply-dev-dynamodb-kms.json.tftpl` — DynamoDB customer-managed-key crypto and grant permissions via DynamoDB.

All templates use `account_id` and the state policy uses `state_bucket`. Each rendered policy is checked against the 6,144-character IAM managed-policy limit. CI rejects production ARNs/state paths and account billing permissions in the dev apply set.

**Least-privilege caveats requiring explicit bootstrap review:**

- `logs:DescribeLogGroups`, Rekognition `CreateCollection`, Lambda `CreateEventSourceMapping`, CloudFront create APIs, Cognito `CreateUserPool`, and some API Gateway create operations require `Resource: "*"` or service-defined collection paths. These are narrowed with request/resource tag or function-ARN conditions where the AWS service supports them.
- API Gateway v2 child-resource APIs do not expose independent resource tags in this configuration. The dev apply policy can manage API Gateway v2 API paths in `us-east-1`; after the first API is created, replace the API ID wildcard with the generated dev API ID if AWS authorization semantics allow it.
- CloudFront OAC/cache/origin-request/response-header policy create actions have no resource ARN at creation. Their subsequent read/update/delete operations are restricted to the corresponding CloudFront resource families.
- KMS key ARN IDs are service-generated; key operations use the project alias condition. The DynamoDB key permissions are separately scoped to the matching environment alias and `kms:ViaService`.

These are policy templates for review, not attached roles. No AWS resources or IAM policies have been created. The dev apply role still requires a separately reviewed GitHub OIDC trust, a pre-created permissions boundary, and the manual bootstrap gate.


## Production Terraform plan-role policies (T11)

The prod plan role mirrors the dev plan role with production-only resource tags, ARNs and state paths:

- `github-plan-prod-core.json.tftpl`
- `github-plan-prod-edge.json.tftpl`
- `github-plan-prod-state.json.tftpl`

The production state object is read-only. Only `attendance/prod/terraform.tfstate.tflock` receives Get/Put/Delete for native S3 backend locking. The prod plan policy contains no dev resource ARNs or dev state path, and contains no infrastructure mutation actions. As with dev, API Gateway v2 GET permissions remain at the API path family because child API resources are not independently tagged in this configuration. CI checks the prod action set, policy size, exact Scheduler group, and dev/prod state/resource separation.


## Production Terraform apply-role policy set (T12)

The production apply role mirrors the dev split with production-only role ARNs, service resource ARNs, environment tags, KMS alias and state key:

- `github-apply-prod-core.json.tftpl`
- `github-apply-prod-data.json.tftpl`
- `github-apply-prod-lambda.json.tftpl`
- `github-apply-prod-iam.json.tftpl`
- `github-apply-prod-foundation.json.tftpl`
- `github-apply-prod-access.json.tftpl`
- `github-apply-prod-state.json.tftpl`
- `github-apply-prod-dynamodb-kms.json.tftpl`

The prod role requires the exact prod execution boundary; PassRole is limited to the exact prod Lambda and Scheduler roles and service principals. The prod state object is Get/Put only; the prod lockfile is the only state path that receives Get/Put/Delete. The policy set contains no dev resource/state paths and no AWS Budgets or account billing actions. CI renders and validates each policy, checks managed-policy size, exact role/boundary/KMS conditions, state isolation and service-specific function constraints.


## Billing plan/apply policies (T37)

- github-plan-billing-core.json.tftpl: budgets:ViewBudget on the exact dev/prod budget ARNs and aws-portal:ViewBilling on Resource=*.
- github-plan-billing-state.json.tftpl: billing state GetObject and billing .tflock lifecycle only.
- github-apply-billing-core.json.tftpl: budgets:ModifyBudget/ViewBudget on the exact dev/prod budget ARNs plus account-level aws-portal:ModifyBilling/ViewBilling.
- github-apply-billing-state.json.tftpl: billing state Get/Put and billing .tflock lifecycle only.

The billing role pair is distinct from the dev/prod plan/apply roles. Account-level billing permissions must never be attached to environment roles. Billing OIDC subjects are billing-plan and billing-apply, both restricted to main. The billing root is selected by the deployment workflow as infra/billing and uses the attendance/billing state key.
