# One-time infrastructure bootstrap

This folder documents manual prerequisites only. No bootstrap resources are provisioned by application Terraform modules.

## 1. Terraform state bucket

In the target AWS account, create `attendance-tfstate-<account_id>` in `ap-south-1` with:

- S3 Block Public Access fully enabled
- Versioning enabled
- Default encryption enabled
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
- `TF_STATE_BUCKET`, `AWS_ACCOUNT_ID`, `ALERT_EMAIL`
- `COGNITO_CALLBACK_URLS`, `COGNITO_LOGOUT_URLS`, `ALLOWED_ORIGINS` (each a non-empty JSON array of strings)

The manual workflow is `.github/workflows/deploy.yml`. Trigger it from `develop` for dev or `main` for prod, choose `plan` first, review the uploaded plan artifact, then trigger `apply` and supply the successful plan run ID. Apply downloads and uses that exact saved plan; stale plans fail safely. Production runs are gated by the `prod` environment reviewer. The workflow uses GitHub OIDC and short-lived credentials; never store AWS access keys.

## Safety gate

The bootstrap steps above are intentionally manual. Normal CI runs Python tests, Ruff, browser syntax/CSP checks, Terraform formatting and static validation. The deployment workflow is manual-only and has not been run. No AWS resources have been provisioned from this repository work. Any `apply` must follow an explicitly approved plan.
