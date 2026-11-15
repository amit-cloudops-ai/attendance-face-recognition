# Production environment

This root wires the shared foundation, data/automation, recognition and access modules with `env=prod`. Production DynamoDB tables have deletion protection enabled. It exports the same route map and deployment outputs as the dev root.

## Prerequisites

- Complete the one-time state-bucket and GitHub OIDC bootstrap described in `infra/bootstrap/README.md`.
- Create `backend.hcl` from `backend.hcl.example` and `terraform.tfvars` from `terraform.tfvars.example`. Both are ignored by Git. The tfvars file must include the matching prod execution boundary ARN.
- From the repository root, export `AWS_PROFILE=default` and `EXPECTED_AWS_ACCOUNT_ID=924422830139` before using the local wrapper. The wrapper verifies STS identity; the provider restricts operations to `var.account_id`.
- The GitHub deployment path uses the `prod-plan` and `prod-apply` environments and the solo-owner approval checkpoint; verify their settings before use.

Before any remote backend initialization or plan, run from the repository root:

```bash
export AWS_PROFILE=default
export EXPECTED_AWS_ACCOUNT_ID=924422830139
```

## Two-pass first deployment

1. The initial values use localhost for Cognito callback/logout and raw-bucket CORS so the first reviewed plan can create the CloudFront distribution without a dependency cycle.
2. After the first approved apply, read `site_url` from Terraform outputs. Replace localhost in `callback_urls`, `logout_urls` and `allowed_origins` with that exact HTTPS origin, then create and review a second plan/apply. This enables Cognito redirects and browser-to-S3 presigned POST uploads on the production domain.

## Commands

```bash
bash scripts/terraform.sh -chdir=infra/envs/prod init -backend-config=backend.hcl
bash scripts/terraform.sh -chdir=infra/envs/prod validate
bash scripts/terraform.sh -chdir=infra/envs/prod plan -var-file=terraform.tfvars -out=tfplan
```

Do not run `terraform apply` without explicit release approval and a reviewed plan. No resources are provisioned by validation or plan.
