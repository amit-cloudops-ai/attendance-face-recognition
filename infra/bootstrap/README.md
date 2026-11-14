# One-time infrastructure bootstrap

This folder documents manual prerequisites only. No bootstrap resources are provisioned by application Terraform modules.

## Canonical region

The only canonical deployment-region setting is `config/deployment.json` (`aws_region: us-east-1`). Terraform provider roots read that file. The S3 backend receives the same region through `scripts/terraform.sh` locally or the deployment workflow in GitHub Actions. Do not add a separate backend/provider region literal.

Use the wrapper for every local Terraform command. It rejects conflicting `AWS_REGION` or `AWS_DEFAULT_REGION` values:

```bash
scripts/terraform.sh -chdir=infra/envs/dev init -input=false -backend-config=backend.hcl
scripts/terraform.sh -chdir=infra/envs/dev validate
scripts/terraform.sh -chdir=infra/envs/dev plan -input=false
```

The backend examples intentionally omit `region`; the wrapper exports it from the canonical manifest. Never run `terraform init` against the remote backend until the owner has separately approved it.

## 1. Terraform state bucket

The proposed bucket name is:

`attendance-tf-state-<12-digit-account-id>-<approved-unique-suffix>`

The name must be globally unique and must be confirmed available before bootstrap. Create it in `us-east-1` only after approval, with:

- S3 Block Public Access fully enabled (all four settings)
- Versioning enabled
- Default SSE-S3 (AES256) encryption
- BucketOwnerEnforced object ownership
- TLS-only deny bucket policy
- No Object Lock and no automatic state expiration

Dev, prod and billing use isolated state keys and native S3 lockfiles:

- `attendance/dev/terraform.tfstate`
- `attendance/prod/terraform.tfstate`
- `attendance/billing/terraform.tfstate`

See `docs/STATE-BUCKET-BOOTSTRAP.md` for the exact specification.

## 2. GitHub Actions OIDC provider

Use issuer `https://token.actions.githubusercontent.com` and audience `sts.amazonaws.com`. Reuse an existing matching provider. Create it only if read-only inspection proves it is absent and the owner approves.

## 3. Runtime permissions boundaries

Create only after review and approval:

- `attendance-dev-execution-boundary`
- `attendance-prod-execution-boundary`

These boundaries cap Lambda and Scheduler runtime permissions. They do not grant permissions by themselves. GitHub apply roles may attach the exact boundary but must not edit/delete its managed policy or create an unbounded runtime role.

## 4. GitHub deployment roles

Six separate roles are required:

- `attendance-github-dev-plan`
- `attendance-github-dev-apply`
- `attendance-github-prod-plan`
- `attendance-github-prod-apply`
- `attendance-github-billing-plan`
- `attendance-github-billing-apply`

The plan roles are read-only for infrastructure; the only state writes are lockfile operations. Apply roles are restricted to their environment's resource and state scope. Billing roles are isolated from dev/prod and contain the dedicated budget/billing permissions only.

Every OIDC trust policy must require audience `sts.amazonaws.com` and the exact repository/environment subject. Do not use wildcard repository, branch or environment subjects.

## 5. GitHub environments and variables

Create these exact environments:

- `dev-plan` and `dev-apply` — branch `develop`
- `prod-plan` and `prod-apply` — branch `main`
- `billing-plan` and `billing-apply` — branch `main`

Apply environments require an independent reviewer and self-review prevention. Each environment defines its own `AWS_ROLE_ARN`. Configure account/state bucket and environment-specific values as described in `docs/GITHUB-ENVIRONMENT-SETUP.md`.

Plan environments receive only their public `TF_PLAN_AGE_RECIPIENT`. Apply environments receive the matching private `TF_PLAN_AGE_IDENTITY` secret. Never store private age identities in repository variables, source control, artifacts or logs. Dev, prod and billing use separate age key pairs.

## 6. Manual deployment workflow

The workflow is `.github/workflows/deploy.yml`. It is manual-only and uses GitHub OIDC with short-lived credentials. It loads the region from `config/deployment.json`, initializes the selected remote state root, and supports plan then apply of the exact encrypted plan artifact. Apply verifies the successful plan run, workflow path, branch, commit and attempt before decrypting and applying.

The deployment workflow has not been run. GitHub environment variables, secrets, reviewer settings and branch restrictions have not been verified by the current repository connection.

## Safety gate

The first AWS interaction must be read-only: verify the active STS account, inspect existing OIDC provider, bucket, boundaries, roles, trust policies and policy attachments. Distinguish missing resources from access-denied responses. Do not create duplicates.

The exact account ID and final bucket suffix remain unverified. The bootstrap inventory and rendered policies must be presented to the owner for explicit approval before any AWS write. State-bucket creation, IAM/OIDC bootstrap, remote backend initialization, Terraform plan and Terraform apply are separate approval-gated actions.
