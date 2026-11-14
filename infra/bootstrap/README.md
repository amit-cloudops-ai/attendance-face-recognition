# One-time infrastructure bootstrap

This folder documents manual prerequisites only. No bootstrap resources are provisioned by application Terraform modules.

## 1. Terraform state bucket

In the target AWS account, create `attendance-tfstate-<account_id>` in `us-east-1` with:

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

Create separate plan and apply roles for each environment:

- `attendance-github-plan-dev`: read-only infrastructure access plus dev state/lock access.
- `attendance-github-apply-dev`: dev resource mutation access plus dev state/lock access.
- `attendance-github-plan-prod`: read-only infrastructure access plus prod state/lock access.
- `attendance-github-apply-prod`: prod resource mutation access plus prod state/lock access.

Each role's trust policy must require audience `sts.amazonaws.com` and the exact matching environment subject: `repo:amit-cloudops-ai/attendance-face-recognition:environment:dev` or `repo:amit-cloudops-ai/attendance-face-recognition:environment:prod`. Do not use wildcard repository, branch or environment subjects. The plan role must not have resource mutation permissions. The apply role must not receive broad account administration; scope it to the reviewed Terraform resources, and restrict `iam:PassRole` to the exact environment application execution roles and required service principals.

## 4. GitHub environments and variables

Create GitHub Environments:

- `dev`: allow deployments from `develop`; no required reviewer is necessary for the dev environment.
- `prod`: allow deployments from `main`; require at least one designated reviewer.

Configure these repository/environment variables:

- `AWS_ROLE_ARN_DEV_PLAN`, `AWS_ROLE_ARN_DEV_APPLY`, `AWS_ROLE_ARN_PROD_PLAN`, `AWS_ROLE_ARN_PROD_APPLY`
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

The plan artifact remains encrypted in GitHub Actions and expires after one day. Only the matching environment's apply job receives the private identity secret, and only in the decryption step. To review the full plan locally, download the encrypted artifact from the successful plan run, then decrypt it using the matching private identity file:

```bash
PLAN_RUN_ID=123456789
gh run download "$PLAN_RUN_ID" \
  --repo amit-cloudops-ai/attendance-face-recognition \
  --name "attendance-dev-terraform-plan-$PLAN_RUN_ID" \
  --dir ./attendance-dev-plan
age --decrypt \
  --identity attendance-dev-plan-identity.txt \
  --output tfplan \
  ./attendance-dev-plan/tfplan.age
terraform show -no-color tfplan
```

Use the prod identity and artifact for production. Keep the decrypted `tfplan` file private and delete it after review; it can contain sensitive infrastructure values. The GitHub environment branch restrictions and production reviewer remain mandatory controls.

## Safety gate

The bootstrap steps above are intentionally manual. Normal CI runs Python tests, Ruff, browser syntax/CSP checks, Terraform formatting and static validation. The deployment workflow is manual-only and has not been run. No AWS resources have been provisioned from this repository work. Any `apply` must follow an explicitly approved plan.
