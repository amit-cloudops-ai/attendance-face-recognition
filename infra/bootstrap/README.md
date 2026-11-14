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

- `attendance-github-deploy-dev`: trust only `repo:amit-cloudops-ai/attendance-face-recognition:ref:refs/heads/develop`
- `attendance-github-deploy-prod`: trust only `repo:amit-cloudops-ai/attendance-face-recognition:environment:prod`

Both trust policies must require audience `sts.amazonaws.com`. Do not use wildcard repository, branch or environment subjects. Do not attach `AdministratorAccess`; the deploy policy must be scoped to the resources and actions required by the reviewed Terraform plan.

## 4. GitHub configuration

After creating and reviewing the roles, configure repository secrets/variables for the role ARNs used by the deployment workflow. The workflow must use GitHub OIDC and short-lived credentials; do not store AWS access keys.

## Safety gate

The bootstrap steps above are intentionally manual. The repository's current CI runs Python tests, Ruff, Terraform formatting, initialization and validation only. It does not authenticate to AWS, create resources, or run `terraform apply`. Production role creation and any apply require explicit approval.
