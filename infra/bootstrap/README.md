# One-time infrastructure bootstrap

This folder documents manual prerequisites only. No bootstrap resources are provisioned by application Terraform modules.

## 1. Terraform state bucket

In the target AWS account, create `attendance-tfstate-<account_id>` in `ap-south-1` with:

- S3 Block Public Access fully enabled
- Versioning enabled
- Default SSE-S3 (AES256) encryption enabled. If choosing SSE-KMS instead, configure the matching backend `kms_key_id` and KMS permissions in both environment roots and deployment roles.
- TLS-only bucket policy
- Object ownership set to bucket owner enforced
- No public access or static website hosting

The development root uses the S3 native lock file (`use_lockfile = true`), so a separate DynamoDB lock table is not required. Keep the state bucket separate from application buckets.

Copy `infra/envs/dev/backend.hcl.example` to `infra/envs/dev/backend.hcl`, replace the account ID, then run `terraform init -backend-config=backend.hcl`.

## 2. GitHub Actions OIDC provider

Create the IAM OIDC identity provider for:

- URL: `https://token.actions.githubusercontent.com`
- Audience: `sts.amazonaws.com`

Reuse the provider if it already exists in the account.

## 3. Deployment roles

Create two roles only after the deployment workflow and its exact permissions policy have been reviewed:

- `attendance-github-deploy-dev`: trust only `repo:amit-cloudops-ai/attendance-face-recognition:environment:dev`
- `attendance-github-deploy-prod`: trust only `repo:amit-cloudops-ai/attendance-face-recognition:environment:prod`

Both trust policies must require audience `sts.amazonaws.com`. Do not use wildcard repository, branch or environment subjects. Do not attach `AdministratorAccess`; the deploy policy must be scoped to the resources and actions required by the reviewed Terraform plan.

## 4. GitHub environments and variables

Create GitHub Environments:

- `dev`: allow deployments from `develop`; no required reviewer is necessary for the dev environment.
- `prod`: allow deployments from `main`; require at least one designated reviewer.

Configure these repository/environment variables:

- `AWS_ROLE_ARN_DEV`, `AWS_ROLE_ARN_PROD`
- `TF_PLAN_AGE_RECIPIENT` (environment variable; age public recipient for the matching environment)
- `TF_STATE_BUCKET`, `AWS_ACCOUNT_ID`, `ALERT_EMAIL`
- `COGNITO_CALLBACK_URLS`, `COGNITO_LOGOUT_URLS`, `ALLOWED_ORIGINS` (each a non-empty JSON array of strings)

The manual workflow is `.github/workflows/deploy.yml`. Trigger it from `develop` for dev or `main` for prod, choose `plan` first, review the uploaded plan artifact, then trigger `apply` and supply the successful plan run ID. Apply downloads and uses that exact saved plan. It verifies the plan run succeeded on the same environment branch and exact commit SHA; stale or mismatched plans fail safely. Production runs are gated by the `prod` environment reviewer. The workflow uses GitHub OIDC and short-lived credentials; never store AWS access keys.

### Encrypt saved Terraform plans

This repository is public. GitHub Actions artifacts are readable by anyone with repository read access, and Terraform plan files can contain sensitive values in clear text. The workflow therefore encrypts the binary plan with `age` before upload and decrypts it only in the matching apply run.

Create a separate age key pair for each GitHub Environment (`dev` and `prod`) on a trusted local machine:

```bash
age-keygen -o attendance-dev-plan-identity.txt
age-keygen -o attendance-prod-plan-identity.txt
```

For each key pair:
- Copy the `# public key:` recipient from the generated file into that environment's `TF_PLAN_AGE_RECIPIENT` variable.
- Store the complete private identity file contents as that environment's `TF_PLAN_AGE_IDENTITY` secret.
- Keep the identity files outside the repository and store a protected offline backup. Never paste the private identity into a workflow variable, commit, issue, or chat.
- Use the dev recipient/identity only in the `dev` environment and the prod pair only in `prod`.

The plan artifact remains encrypted at rest in GitHub Actions and expires after one day. Only a run with access to the matching environment secret can decrypt it. The GitHub environment branch restrictions and production reviewer remain mandatory controls.

## Safety gate

The bootstrap steps above are intentionally manual. Normal CI runs Python tests, Ruff, browser syntax/CSP checks, Terraform formatting and static validation. The deployment workflow is manual-only and has not been run. No AWS resources have been provisioned from this repository work. Any `apply` must follow an explicitly approved plan.
