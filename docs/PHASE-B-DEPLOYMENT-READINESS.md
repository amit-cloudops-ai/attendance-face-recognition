# Phase B — Deployment readiness and AWS access design

**Working branch:** `solo/amit-monday`  
**Scope:** Prepare a controlled development deployment. This document does not authorize AWS resource creation or Terraform apply.

## Current findings

### 1. Terraform state backend

Both environment roots use Terraform's S3 backend with distinct keys:

- Dev: `attendance/dev/terraform.tfstate`
- Prod: `attendance/prod/terraform.tfstate`

Both pin the native S3 lock file with `use_lockfile = true`. Terraform is constrained to >= 1.10, so the separate DynamoDB lock table is not part of this design. The shared state bucket is a manual bootstrap prerequisite and is not created by the application roots.

Required bucket controls before init:
- Block all S3 public access.
- Enable versioning.
- Enable default server-side encryption (use SSE-S3 unless a KMS key is deliberately configured in both backend blocks and role policy).
- Enforce TLS-only access.
- Set Object Ownership to Bucket owner enforced.
- Keep state bucket separate from application data buckets.
- Restrict dev and prod roles to their own state key and lock-file key.

Backend object permissions should be scoped to the exact environment key:
- `s3:GetObject` and `s3:PutObject` on that environment's state object.
- `s3:GetObject`, `s3:PutObject`, and `s3:DeleteObject` on that environment's `.tflock` object.
- `s3:ListBucket` on the state bucket, constrained by `s3:prefix` to that environment's state key and lock key.
- No permission to list or read the other environment's state.

### 2. GitHub OIDC and deployment workflow

The workflow uses short-lived GitHub OIDC credentials, with one role per environment. The trust policy subject must match the exact GitHub Environment:
- Dev: `repo:amit-cloudops-ai/attendance-face-recognition:environment:dev`
- Prod: `repo:amit-cloudops-ai/attendance-face-recognition:environment:prod`

Both trust policies must require audience `sts.amazonaws.com`. GitHub Environments must restrict deployment branches: dev to `develop`, prod to `main`; prod must require a reviewer. Do not use static AWS access keys or wildcard OIDC subjects.

The workflow deliberately permits dev deployment only from `develop` and prod only from `main`. It will not deploy directly from `solo/amit-monday`. When the solo implementation is ready, promote it through a reviewed solo-only PR into `develop`; keep teammate branches and PRs separate.

### 3. Public-repository plan artifact protection

The repository is public. GitHub Actions artifacts are available to repository readers, while Terraform saved plan files may contain sensitive values in clear text. The deployment workflow was updated to encrypt the plan with `age` before artifact upload and decrypt it only in the matching apply run.

Each GitHub Environment needs its own key pair:
- Variable: `TF_PLAN_AGE_RECIPIENT` (public recipient).
- Secret: `TF_PLAN_AGE_IDENTITY` (private identity).
- Use separate dev and prod key pairs; keep private identity backups outside the repository.

The encrypted artifact is retained for one day. The apply job still verifies that the plan came from a successful manual plan run for the same environment branch and exact commit SHA.

### 4. Deployment IAM policy — not yet approved or created

Do not attach `AdministratorAccess`. A safe policy must be derived from the full Terraform resource/action inventory and must separate the GitHub deployment role from the application execution roles.

The current Terraform roots manage resources across:
- S3, KMS, SNS, AWS Budgets and Lambda layers (foundation).
- DynamoDB, Lambda, IAM execution roles/policies, EventBridge Scheduler, CloudWatch Logs and alarms (data).
- Rekognition collections, SQS queues/redrive, Lambda async destinations/event mappings, Lambda permissions and CloudWatch alarms (recognition).
- Cognito, API Gateway v2, CloudFront, CloudFront Functions/cache/origin/response policies, S3 objects/bucket policies and Lambda invoke permissions (access).

The application execution role names follow `attendance-<env>-<function>`; the scheduler roles follow `attendance-<env>-<job>-scheduler`. The deployment policy must scope `iam:PassRole` to only these exact environment role ARNs and the required AWS service principals. Role creation/update permissions need a separate review, including whether a permissions boundary should be added to every application role before allowing CI to create or modify IAM roles.

The exact deployment policy is intentionally not guessed in this phase. It must be checked against the provider's actual create/read/update/delete calls, resource-level IAM support, tagging conditions and any `iam:PassRole` dependencies before an AWS role is created.

## Phase B gates

- [x] Inspect current backend configuration and deployment workflow.
- [x] Identify public plan-artifact exposure.
- [x] Encrypt saved Terraform plan artifacts before upload.
- [x] Document age key setup and environment isolation.
- [ ] Complete deployment-role action inventory and least-privilege policy review.
- [ ] Decide and document permissions-boundary treatment for application IAM roles.
- [ ] Confirm state bucket encryption and exact bucket policy.
- [ ] Configure GitHub dev/prod environments and variables/secrets.
- [ ] Create OIDC provider and environment-specific AWS roles (manual bootstrap; explicit approval required).
- [ ] Open reviewed solo-only PR from `solo/amit-monday` to `develop` when release candidate is ready.
- [ ] Generate and review dev plan; obtain explicit approval before apply.
- [ ] Deploy dev, complete CloudFront/Cognito/CORS second pass, then run real AWS and browser/device acceptance tests.

## Safety boundary

No AWS resources have been created, no OIDC roles have been created, no Terraform backend has been initialized against an AWS account, and no plan or apply has been run as part of this phase. The encrypted plan workflow change is committed to the solo branch but must pass CI and receive the later deployment-readiness review before use.
