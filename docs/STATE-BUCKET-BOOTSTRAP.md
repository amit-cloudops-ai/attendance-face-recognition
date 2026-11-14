# Terraform state bucket bootstrap specification

**Status:** specification only. No AWS API call, resource creation, remote backend initialization, Terraform plan or apply has been performed.

## Purpose and naming

Create one dedicated S3 bucket for Terraform state in the existing AWS account and us-east-1 region. The proposed name is:

attendance-tf-state-<12-digit-account-id>-<approved-unique-suffix>

S3 bucket names are globally unique, so the suffix must be selected and checked before bootstrap. The final bucket name is supplied through the GitHub variable TF_STATE_BUCKET and rendered into the IAM state policy templates through state_bucket.

## Backend state keys

| Root | State object | Lock object |
|---|---|---|
| Dev | attendance/dev/terraform.tfstate | attendance/dev/terraform.tfstate.tflock |
| Prod | attendance/prod/terraform.tfstate | attendance/prod/terraform.tfstate.tflock |
| Billing | attendance/billing/terraform.tfstate | attendance/billing/terraform.tfstate.tflock |

All roots target us-east-1, set encrypt = true, and use native S3 lockfiles with use_lockfile = true. The environment lockfiles are committed and CI uses terraform init -lockfile=readonly; remote backend init remains disabled in CI.

## Required bucket configuration

1. **Region:** us-east-1.
2. **Versioning:** Enabled. Preserve previous state versions for recovery; do not configure automatic noncurrent-version expiration in the initial bootstrap.
3. **Default encryption:** SSE-S3 (AES256). Terraform's encrypt = true enables server-side encryption; no separate KMS key is required for backend state.
4. **Block Public Access:** all four settings enabled: BlockPublicAcls, IgnorePublicAcls, BlockPublicPolicy and RestrictPublicBuckets.
5. **Object ownership:** BucketOwnerEnforced; ACLs disabled.
6. **Bucket policy:** deny all S3 actions over the bucket and its objects when aws:SecureTransport=false. Do not add public allow statements.
7. **No object lock:** Terraform's native .tflock mechanism is used; S3 Object Lock is not part of this design.
8. **No automatic state expiration:** state and noncurrent versions are recovery material. Deletion requires an explicit recovery/retention decision.

## Proposed bootstrap policy

The only bucket-policy statement required initially is the TLS-only deny. It applies to both the bucket ARN and bucket-arn/*:

- Sid: DenyInsecureTransport
- Effect: Deny
- Principal: *
- Action: s3:*
- Resources: arn:aws:s3:::<final-state-bucket-name> and arn:aws:s3:::<final-state-bucket-name>/*
- Condition: Bool aws:SecureTransport = false

Default SSE-S3 encryption is configured at the bucket level. The bucket policy deliberately does not require a client-supplied encryption header, because S3 default encryption applies when an object upload omits that header.

## Least-privilege state access

The plan and apply policies are split by environment:

- Plan: GetObject on that environment's state object; GetObject/PutObject/DeleteObject only on its .tflock; ListBucket restricted to the state and lock prefixes.
- Apply: GetObject/PutObject on that environment's state object; GetObject/PutObject/DeleteObject only on its .tflock; ListBucket restricted to the state and lock prefixes.
- No dev policy references prod state; no prod policy references dev state.
- The billing root has a separate state key. A dedicated billing plan/apply role policy must be created before billing deployment; environment plan/apply roles must not receive access to the billing state key.

The plan/apply templates include GetBucketLocation and GetBucketVersioning on the state bucket. No state KMS permissions are required for SSE-S3.

## Manual bootstrap sequence (not executed)

1. Confirm the 12-digit AWS account ID and us-east-1 region from the owner's authenticated AWS identity.
2. Choose a globally unique bucket suffix and confirm the final bucket name is available.
3. Present the exact bucket name, configuration, policy JSON and bootstrap IAM permissions to the owner for approval.
4. Only after approval, create the bucket and apply ownership controls, all four public-access-block settings, versioning, default SSE-S3 encryption and the TLS-only bucket policy.
5. Verify with read-only S3 API calls: bucket location, ownership controls, public access block, versioning, encryption and policy.
6. Render the dev/prod plan/apply state policies with the final bucket name; validate JSON and exact state/lock paths.
7. Configure TF_STATE_BUCKET in the four GitHub environments. Only after the owner separately approves deployment preparation may remote terraform init be run.

## Rollback and recovery

Do not delete the state bucket as a rollback mechanism. Disable the GitHub deployment environments or remove role access, preserve the bucket and all object versions, and recover a prior state version only through a reviewed recovery procedure. Do not delete a lock object while a Terraform operation may still be active.

## Cost and operational notes

State files and lockfiles are small and infrequently accessed. Expected storage/request charges should be negligible for this workload, but the exact amount depends on retained state versions and account pricing. Versioning is intentionally enabled without automatic expiration to preserve recovery options.

## Approval boundary

This specification is not authorization to create the bucket. Bucket creation, IAM role creation, OIDC provider creation, remote backend initialization, Terraform plan and Terraform apply all remain separate approval-gated actions.
