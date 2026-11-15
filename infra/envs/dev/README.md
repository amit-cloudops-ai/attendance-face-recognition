# Development environment

This root wires the shared foundation, data/automation, recognition and access modules. The frontend is already part of the access module; Terraform generates and uploads `web/config.json`.

## Prerequisites

1. Complete the reviewed AWS bootstrap plan and create the state bucket and dev execution boundary only after explicit owner approval.
2. Copy `backend.hcl.example` to `backend.hcl` in this directory and replace the placeholder state bucket with the approved bucket name.
3. Copy `terraform.tfvars.example` to `terraform.tfvars`. Set the verified account ID, matching dev boundary ARN and alert email.
4. Set the expected account for the local wrapper. From the repository root:

```bash
export AWS_PROFILE=default
export EXPECTED_AWS_ACCOUNT_ID=924422830139
```

The wrapper verifies STS identity before remote backend initialization, plan or apply. The AWS provider also restricts dev/prod provider operations to `var.account_id`.

## Commands

Run from the repository root. Do not run remote backend initialization or a plan until the owner has approved those separate gates.

```bash
bash scripts/terraform.sh -chdir=infra/envs/dev init -backend-config=backend.hcl
bash scripts/terraform.sh -chdir=infra/envs/dev validate
bash scripts/terraform.sh -chdir=infra/envs/dev plan -var-file=terraform.tfvars
```

Do not run `apply` without a separate explicit approval of the exact reviewed plan.

## Cognito and CloudFront first deployment

The initial callback/logout/origin values use localhost so the first approved apply can create CloudFront. After that apply, read the `site_url` output. Replace the localhost callback/logout URLs and `allowed_origins` with the exact HTTPS CloudFront origin, then produce and review a second plan before a separately approved apply.

Do not create a local `web/config.json` for Terraform deployment. The generated file is owned by the dedicated `aws_s3_object.frontend_config` resource and is excluded from the generic frontend fileset.

