# Development environment

This root wires the shared foundation, data/automation, recognition and access modules. It exports the combined API route map, Cognito details and CloudFront site URL.

## Recommended first deployment

For the first dev deployment, follow the ordered [solo local dev bootstrap](../../../docs/DEPLOYMENT-RUNBOOK.md#1-solo-local-dev-bootstrap-owner-operated-path). It covers the read-only account preflight, API Gateway import, dev execution boundary, state bucket, ignored local backend file, concurrency quota check, first apply, required CloudFront second apply, Cognito users, SNS confirmation and consent-gated smoke test.

The target account for this dev environment is `924422830139` in `us-east-1`. Run Terraform through `bash scripts/terraform.sh` as the approved `Amit-admin` profile. Do not use direct Terraform commands that bypass the canonical-region wrapper.

## Local files

Copy `backend.hcl.example` to `backend.hcl` and set the final state bucket name. Copy `terraform.tfvars.example` to `terraform.tfvars`, replace the API ID placeholder with the real 10-character API Gateway ID, and set the alert email. Both files must remain ignored by Git.

The default Lambda concurrency reservations total 19 and require an account concurrency quota of at least 29 to retain 10 unreserved executions. If the quota is lower, set selected `lambda_reserved_concurrency` values to `null` or request an increase before applying.

## Cognito and CloudFront

The initial callback and logout URLs use localhost. After the first apply, add the exact CloudFront HTTPS origin to `allowed_origins`, its `/callback.html` URL to `callback_urls`, and its root URL to `logout_urls`. Run a reviewed second plan/apply. Cognito login and browser-to-S3 uploads from the deployed site are not expected to work until this second apply is complete.

## Safety

No AWS resources are created by Terraform init, validate or plan. The first and second applies are owner-approved AWS writes. Never use `-auto-approve`; inspect each saved plan before applying. Keep production separate and blocked until dev acceptance is complete.
