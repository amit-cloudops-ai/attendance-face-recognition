# Deployment runbook

**Status:** repository instructions only. This runbook does not authorize AWS writes, remote backend initialization, Terraform planning or applying.

## 1. Solo local dev bootstrap (owner-operated path)

**Recommended for the first development deployment.** This path uses the existing AWS account through the local AWS CLI profile `Amit-admin`. It does not require the OIDC provider, six deployment roles, six GitHub environments, or promotion to `develop`. It is a dev-only path; production remains separately gated.

Target account: `924422830139`
Target region: `us-east-1`
Terraform root: `infra/envs/dev`

All steps below are instructions for the repository owner. They are not executed by this runbook or by this review. API creation, IAM policy creation, S3 bucket creation, remote backend initialization, Terraform plan and Terraform apply are separate owner-approved actions. Never proceed if the STS identity does not match the target account.

### Bootstrap order

1. **Read-only identity and account preflight.** Confirm that the selected profile resolves to the expected account, then inspect existing resources. This step must not create or modify anything:

   ```bash
   AWS_PROFILE=Amit-admin aws sts get-caller-identity --region us-east-1
   AWS_PROFILE=Amit-admin bash scripts/aws_preflight_readonly.sh
   ```

   Stop unless the returned account is `924422830139` and the region is `us-east-1`. Treat AccessDenied as unknown, not as proof that a resource is absent. Record existing OIDC, boundary, role and state-bucket resources so that none are duplicated.

2. **Create the dev API Gateway HTTP API.** First run the script in its default dry-run mode and inspect the exact account, region and API name. Only after approving that one API creation, run the second command:

   ```bash
   bash scripts/bootstrap_api_gateway.sh --env dev --account-id 924422830139 --profile Amit-admin
   bash scripts/bootstrap_api_gateway.sh --env dev --account-id 924422830139 --profile Amit-admin --apply
   ```

   Record the returned 10-character `API_ID`. If the script reports that the API already exists, stop and verify its owner, tags and configuration; do not create a duplicate. The Terraform root has an import block for this pre-created API.

3. **Create the dev Lambda execution permissions boundary.** Render the account-specific JSON locally from the tracked template and validate it before using the IAM Console:

   ```bash
   python - <<'PY'
   from pathlib import Path

   template = Path("infra/policies/execution-role-boundary-dev.json.tftpl")
   rendered = template.read_text(encoding="utf-8").replace("${account_id}", "924422830139")
   if "${account_id}" in rendered:
       raise SystemExit("Unresolved account_id placeholder")
   output = Path("/tmp/attendance-dev-execution-boundary.json")
   output.write_text(rendered + "\\n", encoding="utf-8")
   print(output)
   PY
   python -m json.tool /tmp/attendance-dev-execution-boundary.json >/dev/null
   ```

   In AWS Console, open **IAM → Policies → Create policy → JSON**, paste the rendered JSON, and create a customer-managed policy named exactly `attendance-dev-execution-boundary`. Verify its ARN is `arn:aws:iam::924422830139:policy/attendance-dev-execution-boundary`. Do not attach this boundary to the deployment user; Terraform attaches it to the application execution roles.

4. **Create the Terraform state bucket.** Choose a globally unique suffix and create `attendance-tf-state-924422830139-<suffix>` in `us-east-1`. Follow every control in [STATE-BUCKET-BOOTSTRAP.md](STATE-BUCKET-BOOTSTRAP.md): BucketOwnerEnforced object ownership, all four S3 Block Public Access settings, versioning enabled, default SSE-S3 encryption, and a bucket policy denying all non-TLS requests. Do not enable Object Lock or automatic state-version expiration. Verify the final bucket name and settings before continuing.

5. **Write the local backend configuration.** Copy the example and replace its bucket value with the exact bucket name created in step 4:

   ```bash
   cp infra/envs/dev/backend.hcl.example infra/envs/dev/backend.hcl
   ```

   The file must contain the final bucket name, `encrypt = true` and `use_lockfile = true`. Confirm it is ignored by Git:

   ```bash
   git check-ignore -v infra/envs/dev/backend.hcl
   ```

   If Git does not report it as ignored, stop and correct the ignore rule before proceeding. Never commit `backend.hcl`, `terraform.tfvars`, state files, plans, credentials or generated account-specific policy files.

6. **Check Lambda concurrency, then initialize, plan and apply locally.** Before Terraform apply, open **AWS Console → Lambda → us-east-1 → Dashboard → Account-level concurrency**. The current defaults reserve 19 executions (recognize 10, enroll 5, failure 2, daily 1, weekly 1), and AWS must retain at least 10 unreserved executions. Therefore the account quota must be at least 29 to keep all defaults. If it is lower, set one or more values in `lambda_reserved_concurrency` in the local `terraform.tfvars` to `null` (all five may be `null` on a new account), or request a quota increase and wait for approval. Do not discover this limitation during apply.

   Copy the dev example, then set the real API ID and alert email. Keep the boundary ARN and account ID exact:

   ```bash
   cp infra/envs/dev/terraform.tfvars.example infra/envs/dev/terraform.tfvars
   ```

   Run locally as the approved IAM user through the repository wrapper. The wrapper enforces the canonical region:

   ```bash
   AWS_PROFILE=Amit-admin aws sts get-caller-identity --region us-east-1
   AWS_PROFILE=Amit-admin bash scripts/terraform.sh -chdir=infra/envs/dev init -input=false -backend-config=backend.hcl
   AWS_PROFILE=Amit-admin bash scripts/terraform.sh -chdir=infra/envs/dev validate
   AWS_PROFILE=Amit-admin bash scripts/terraform.sh -chdir=infra/envs/dev plan -input=false -var-file=terraform.tfvars -out=/tmp/attendance-dev-first.tfplan
   ```

   Inspect the complete plan, especially IAM role/boundary attachments, S3 policies, KMS, Cognito, Lambda concurrency, API import and any replacement/deletion. If anything is unexpected, stop. Only after you explicitly approve that exact saved plan, apply it:

   ```bash
   AWS_PROFILE=Amit-admin bash scripts/terraform.sh -chdir=infra/envs/dev apply /tmp/attendance-dev-first.tfplan
   ```

   Do not use `-auto-approve`. The first apply creates the dev stack and imports the API created in step 2. The deployed Cognito login and browser-to-S3 upload flow are not ready until step 7.

7. **Perform the required second apply for the CloudFront origin.** Read the exact CloudFront URL from Terraform output:

   ```bash
   AWS_PROFILE=Amit-admin bash scripts/terraform.sh -chdir=infra/envs/dev output -raw site_url
   ```

   Add that exact HTTPS origin to all three values in the local `terraform.tfvars`, preserving localhost entries if they are still useful for local browser testing:
   - `allowed_origins`: add the CloudFront origin.
   - `callback_urls`: add the CloudFront URL ending in `/callback.html`.
   - `logout_urls`: add the CloudFront site root ending in `/`.

   Then create and inspect a fresh second plan and apply only that saved plan:

   ```bash
   AWS_PROFILE=Amit-admin bash scripts/terraform.sh -chdir=infra/envs/dev plan -input=false -var-file=terraform.tfvars -out=/tmp/attendance-dev-cloudfront-url.tfplan
   ```

   After reviewing and approving the second plan:

   ```bash
   AWS_PROFILE=Amit-admin bash scripts/terraform.sh -chdir=infra/envs/dev apply /tmp/attendance-dev-cloudfront-url.tfplan
   ```

   This second apply is required for Cognito Hosted UI redirects and browser-to-S3 presigned uploads from the deployed CloudFront origin. Do not skip it.

8. **Complete the manual identity and notification setup.**
   - Confirm the SNS email subscription using the confirmation link delivered to the configured alert mailbox.
   - In **AWS Console → Cognito → User pools → attendance-dev-users → Users**, create the intended dev admin and kiosk users.
   - Add the administrator user to the `admin` group and the kiosk device/user to the `kiosk` group. Use unique, controlled test identities; do not put passwords or tokens in Git or logs.

9. **Run the consent-gated end-to-end smoke test.** Follow the required environment variables and cleanup behavior in [scripts/README.md](../scripts/README.md), use only explicitly consented test data, set `CONSENT_CONFIRMED=YES`, and run:

   ```bash
   bash scripts/e2e_smoke.sh
   ```

   Review the output, verify employee deactivation and face-template cleanup, and retain only non-sensitive test evidence. The script leaves attendance/audit history; it does not delete that history.

### Optional OIDC/GitHub Actions pipeline

The six-environment OIDC pipeline (T16/T18) is optional for this first dev deployment. You do not need to create the OIDC provider, six deployment roles, 37 policy documents or six GitHub environments to use the solo local path above. Add and validate the pipeline after the dev stack is established. The local path does not require merging or promoting the candidate to `develop`; only the GitHub Actions dev pipeline is restricted to `develop`. Do not weaken or remove the existing OIDC workflow when using the local path.

---

## 2. Deployment model

The GitHub Actions OIDC workflow at `.github/workflows/deploy.yml` is the CI/CD path. The solo local dev bootstrap above is also supported for the first dev deployment.

| Target | Release branch | Plan environment | Apply environment | State key |
|---|---|---|---|---|
| Dev | `develop` | `dev-plan` | `dev-apply` | `attendance/dev/terraform.tfstate` |
| Prod | `main` | `prod-plan` | `prod-apply` | `attendance/prod/terraform.tfstate` |
| Billing | `main` | `billing-plan` | `billing-apply` | `attendance/billing/terraform.tfstate` |

Dev and prod also require a matching `API_ID` GitHub environment variable. The ID is generated by API Gateway, pre-created through the owner-approved bootstrap script, and imported into the matching Terraform state.

The workflow uses short-lived GitHub OIDC credentials, an account-specific S3 state bucket, S3 native lockfiles and age-encrypted saved plans. CI uses `terraform init -backend=false`; it must never initialize the remote backend.

## 3. Before any deployment

1. Verify the release commit and full CI run on that exact commit. Required evidence includes Python unit/contract/integration/security tests, Ruff, pip-audit, immutable action pins, region consistency, browser JavaScript/CSP checks, shell syntax, policy/template checks, Terraform formatting, provider lockfiles and validation of all modules and roots.
2. For the OIDC pipeline path only, verify the six GitHub environments, exact branch restrictions, environment variables, plan-only public age recipients and apply-only private age identity secrets. The solo-owner model requires no independent reviewer and allows owner self-review. Dev/prod require their own `API_ID` variable. The local dev path does not depend on GitHub environments.
3. Run `bash scripts/aws_preflight_readonly.sh` using an explicitly approved read-only AWS profile. Confirm the 12-digit STS account ID, `us-east-1`, OIDC provider, two runtime boundaries, six role trust/attachments and state bucket configuration. AccessDenied is an unknown state, not evidence of absence.
4. The API Gateway HTTP API must exist before the IAM inventory is rendered. The owner-approved bootstrap script creates only that one tagged API and fails closed if the expected name already exists.
5. Render the account-specific IAM inventory with the verified API ID. Review all 37 JSON documents, including the 26 permanent managed policies and two temporary create-only CloudFront bootstrap policies.
6. Present the exact API creation and IAM/state-bucket bootstrap resource/action plan for approval. API creation, IAM bootstrap, remote backend initialization, Terraform plan and Terraform apply are separate approvals. Never infer one approval from another.

## 4. Local reproducibility gate

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
bash -n scripts/bootstrap_api_gateway.sh

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

## 5. Account-specific read-only preparation

After local access is intentionally connected, use the profile explicitly selected by the owner:

```bash
aws sts get-caller-identity --profile <approved-profile>
bash scripts/aws_preflight_readonly.sh

# Dry-run only: no API is created.
bash scripts/bootstrap_api_gateway.sh \
  --env dev \
  --account-id <verified-account-id> \
  --profile <approved-profile>
```

The preflight and the bootstrap script's default mode are read-only. The renderer's S3 HeadBucket check is a point-in-time observation, not a bucket reservation. If an API with the expected name already exists, stop and verify its owner, tags and configuration; do not create a duplicate.

## 6. Bootstrap and backend initialization

1. Review the API bootstrap dry-run. Obtain explicit approval for that exact API name, account, region and environment.
2. Only after approval, rerun `scripts/bootstrap_api_gateway.sh` with `--apply`. Record the returned 10-character API ID and set it as `API_ID` in the matching GitHub environment. The dev and prod IDs must be distinct.
3. Render the IAM inventory:

   ```bash
   python scripts/render_bootstrap_inventory.py \
     --suffix <owner-approved-suffix> \
     --api-id <environment-api-id> \
     --profile <approved-profile>
   ```

   The renderer performs STS GetCallerIdentity and S3 HeadBucket only. It does not create AWS resources, initialize Terraform state or run a plan/apply. Review every rendered policy, confirm API Gateway paths contain only the exact API ID, and verify the CloudFront bootstrap policies contain Create actions only.
4. After separate approval of the exact IAM/state-bucket bootstrap plan, create only approved missing resources and verify them read-only. The expected inventory is one state bucket, one OIDC provider if absent, two runtime boundaries, six plan/apply roles, 26 permanent managed policies and two temporary CloudFront create-only policies. Do not duplicate compatible existing resources.
5. Attach the matching temporary CloudFront bootstrap policy only for the first approved environment deployment. It cannot update or delete existing CloudFront policy resources. Detach it immediately after the OAC/cache/origin-request/response-header policies are created. Future changes require a separately reviewed, time-bounded policy scoped to exact resource IDs.
6. Only after a separate backend-initialization approval should the remote backend be initialized. The workflow provides the state bucket, canonical region, encryption and native lockfile configuration. Never run an unreviewed `terraform apply`.

## 7. Plan and apply procedure

1. The pipeline path requires the approved dev release to be merged to `develop` through a PR with required CI checks. This promotion is not needed for the solo local dev path.
2. Dispatch the deployment workflow with `environment=dev`, `operation=plan`.
3. Download and inspect the encrypted plan through the approved review process. Confirm create/update/delete/replacement actions, IAM changes, cost implications and data-loss risks.
4. If and only if the plan is approved, dispatch `environment=dev`, `operation=apply` and supply the successful plan run ID. GitHub's `dev-apply` environment approval is an additional gate.
5. The workflow verifies the plan run, exact commit and branch, downloads the artifact from that run, decrypts it with the apply-only identity, verifies the assumed AWS account and state-bucket prefix, and applies only the saved plan. The temporary CloudFront create-only policy must be attached only for the first approved deployment and detached immediately after the OAC/cache/origin/response policies are created.
6. Record the workflow run IDs, commit SHA, plan review, approval and post-apply verification.

A new commit requires a new plan. Do not apply a saved plan from a different commit, branch, environment or workflow attempt.

## 8. First dev deployment troubleshooting

| Symptom | Likely cause | Corrective action |
|---|---|---|
| Terraform variable validation rejects `execution_role_boundary_arn` | The dev boundary policy is missing, has the wrong name, or belongs to another account | In IAM Console, confirm **Policies → attendance-dev-execution-boundary** exists and its ARN is exactly `arn:aws:iam::924422830139:policy/attendance-dev-execution-boundary`. Create it from the rendered template in step 3; do not weaken the Terraform validation. |
| `terraform init` says the backend bucket or `backend.hcl` cannot be found | The state bucket was not created, the local backend file is absent/misnamed, or its bucket value is wrong | Confirm `infra/envs/dev/backend.hcl` exists locally, is gitignored, and names the exact bucket created in `us-east-1`. Verify bucket versioning, encryption, public-access block and TLS-only policy against [STATE-BUCKET-BOOTSTRAP.md](STATE-BUCKET-BOOTSTRAP.md). |
| Apply fails while setting Lambda reserved concurrency | The account quota cannot accommodate 19 reserved executions while retaining the required 10 unreserved executions | Recheck **Lambda → Dashboard → Account-level concurrency** in `us-east-1`. Reduce the total reservations by setting selected `lambda_reserved_concurrency` entries to `null`, or request and wait for a quota increase. Do not remove the unreserved-concurrency safety margin. |
| Cognito returns `redirect_mismatch` | The callback URL is not an exact match for the browser redirect | Confirm the URL ends in `/callback.html`, not `/auth/callback/`, and that the exact CloudFront HTTPS callback URL is in `callback_urls`. Confirm the CloudFront logout root is in `logout_urls`, then run the reviewed second apply. |
| Kiosk upload fails with a browser CORS error | The CloudFront origin has not yet been added to the raw-bucket/API allowed origins | Add the exact CloudFront origin (scheme + host, no path) to `allowed_origins`, preserve localhost if needed, and complete the reviewed second apply. Do not use a wildcard origin. |
| A Lambda returns `AccessDenied` after deployment | The execution-role permissions boundary may deny the action even if the attached role policy allows it | Check the boundary first in **IAM → Policies → attendance-dev-execution-boundary**. Confirm the affected function's execution role has that boundary attached and that the requested action/resource is permitted. Then inspect the failing function's **CloudWatch Logs** log group for the exact denied action and resource ARN. Fix the narrow boundary or role statement; do not respond by granting broad `*` permissions. |

For every failure, preserve the exact error, request ID, function name and resource ARN while redacting tokens, credentials, employee data and biometric material. Re-run a fresh plan after any configuration or IAM change; never reuse a saved plan from before that change.

---

## 9. Post-deployment acceptance

Run the consent-gated smoke flow with a test employee and explicitly consented test images. The script requires at least 20 scans and verifies enrollment, matching, attendance persistence and cleanup. Its p95 measures API/upload/recognition round-trip; it does not measure physical camera capture or browser rendering. Complete separate Chrome/Android and Safari/iOS camera tests, real Cognito login/group authorization, raw-image deletion, face offboarding, DLQ recovery, alarm delivery, budget notifications and a restore drill.

Production remains blocked until dev acceptance evidence is reviewed and a separate production plan and approval are complete.
