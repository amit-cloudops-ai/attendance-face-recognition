# Deployment runbook

**Status:** repository instructions only. This runbook does not authorize AWS writes, remote backend initialization, Terraform planning or applying.

## 1. Deployment model

The only supported release workflow is the manual GitHub Actions workflow at `.github/workflows/deploy.yml`.

| Target | Release branch | Plan environment | Apply environment | State key |
|---|---|---|---|---|
| Dev | `develop` | `dev-plan` | `dev-apply` | `attendance/dev/terraform.tfstate` |
| Prod | `main` | `prod-plan` | `prod-apply` | `attendance/prod/terraform.tfstate` |
| Billing | `main` | `billing-plan` | `billing-apply` | `attendance/billing/terraform.tfstate` |

The workflow uses short-lived GitHub OIDC credentials, an account-specific S3 state bucket, S3 native lockfiles and age-encrypted saved plans. CI uses `terraform init -backend=false`; it must never initialize the remote backend.

## 2. Before any deployment

1. Verify the release commit and the full CI run on that exact commit. Required evidence includes Python unit/contract/integration/security tests, Ruff, region consistency, browser JavaScript/CSP checks, shell syntax, policy/template checks, Terraform formatting, provider lockfiles and validation of all modules and roots.
2. Verify the six GitHub environments, exact branch restrictions, environment variables, plan-only public age recipients, apply-only private age identity secrets, independent reviewers and self-review prevention. Protect workflow, Terraform and policy paths with CODEOWNERS review.
3. Run `bash scripts/aws_preflight_readonly.sh` using an explicitly approved read-only AWS profile. Confirm the 12-digit STS account ID, `us-east-1`, OIDC provider, two runtime boundaries, six role trust/attachments and state bucket configuration. AccessDenied is an unknown state, not evidence of absence.
4. Select a candidate state bucket suffix and run `python scripts/render_bootstrap_inventory.py --suffix <suffix> --profile default`. Review the generated account ID, bucket name, six OIDC trust policies, two boundaries, 26 managed policies and TLS-only bucket policy.
5. Present the exact bootstrap resource/action plan for approval. Bootstrap approval, remote backend initialization, Terraform plan and Terraform apply are separate approvals. Never infer one approval from another.

## 3. Local reproducibility gate

Run these commands only after the owner intentionally connects the local checkout and selects the intended branch. They do not require AWS credentials and do not create AWS resources.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt

ruff check .
pytest -q
python scripts/check_region_consistency.py
bash -n scripts/e2e_smoke.sh
bash -n scripts/terraform.sh
bash -n scripts/aws_preflight_readonly.sh
bash -n scripts/configure_github_environments.sh
bash -n scripts/configure_branch_protection.sh

terraform fmt -check -diff -recursive infra

terraform -chdir=infra/modules/recognition init -backend=false -input=false
terraform -chdir=infra/modules/recognition validate
terraform -chdir=infra/modules/data init -backend=false -input=false
terraform -chdir=infra/modules/data validate
terraform -chdir=infra/modules/foundation init -backend=false -input=false
terraform -chdir=infra/modules/foundation validate
terraform -chdir=infra/modules/access init -backend=false -input=false
terraform -chdir=infra/modules/access validate

terraform -chdir=infra/envs/dev init -backend=false -input=false -lockfile=readonly
terraform -chdir=infra/envs/dev validate
terraform -chdir=infra/envs/prod init -backend=false -input=false -lockfile=readonly
terraform -chdir=infra/envs/prod validate
terraform -chdir=infra/billing init -backend=false -input=false -lockfile=readonly
terraform -chdir=infra/billing validate
```

The CI toolchain is pinned to Ubuntu 26.04, Python 3.12.16, Terraform 1.10.5 and age 1.2.1-1build1. Python test/lint dependencies are pinned in `requirements-dev.txt`; CI runs the SHA-pinned PyPA pip-audit action against that full dependency list. GitHub Actions are pinned to full commit SHAs and Dependabot checks GitHub Actions and Python dependencies weekly. Use the committed provider lockfiles; do not run `terraform init -upgrade` as part of a deployment.

## 4. Account-specific read-only preparation

After local access is intentionally connected, use the profile explicitly selected by the owner:

```bash
aws sts get-caller-identity --profile default
bash scripts/aws_preflight_readonly.sh
python scripts/render_bootstrap_inventory.py --suffix <owner-approved-suffix> --profile default
```

The preflight and renderer are read-only with respect to AWS. The renderer's S3 HeadBucket check is a point-in-time observation, not a bucket reservation. Inspect the complete output before any bootstrap action.

## 5. Bootstrap and backend initialization

After separate explicit approval of the exact bootstrap plan, create only the approved missing resources and verify them read-only. The expected inventory is one state bucket, one OIDC provider if absent, two runtime boundaries, six plan/apply roles and their 26 managed policy attachments. Do not duplicate compatible existing resources.

Only after a separate backend-initialization approval should the remote backend be initialized. The workflow provides the state bucket, canonical region, encryption and native lockfile configuration. Never run an unreviewed `terraform apply`.

## 6. Plan and apply procedure

1. Merge the approved dev release to `develop` through a reviewed PR.
2. Dispatch the deployment workflow with `environment=dev`, `operation=plan`.
3. Download and inspect the encrypted plan through the approved review process. Confirm create/update/delete/replacement actions, IAM changes, cost implications and data-loss risks.
4. If and only if the plan is approved, dispatch `environment=dev`, `operation=apply` and supply the successful plan run ID. GitHub's `dev-apply` environment approval is an additional gate.
5. The workflow verifies the plan run, exact commit and branch, downloads the artifact from that run, decrypts it with the apply-only identity, verifies the assumed AWS account and state-bucket prefix, and applies only the saved plan.
6. Record the workflow run IDs, commit SHA, plan review, approval and post-apply verification.

A new commit requires a new plan. Do not apply a saved plan from a different commit, branch, environment or workflow attempt.

## 7. Post-deployment acceptance

Run the consent-gated smoke flow with a test employee and explicitly consented test images. The script requires at least 20 scans and verifies enrollment, matching, attendance persistence and cleanup. Its p95 measures API/upload/recognition round-trip; it does not measure physical camera capture or browser rendering. Complete separate Chrome/Android and Safari/iOS camera tests, real Cognito login/group authorization, raw-image deletion, face offboarding, DLQ recovery, alarm delivery, budget notifications and a restore drill.

Production remains blocked until dev acceptance evidence is reviewed and a separate production plan and approval are complete.
