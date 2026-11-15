# Project operations scripts

## Canonical region and safe Terraform wrapper

`config/deployment.json` is the single region source. Run local Terraform commands through `bash scripts/terraform.sh`; the wrapper loads the canonical region, rejects conflicting `AWS_REGION`/`AWS_DEFAULT_REGION` values and exports the same value to Terraform's S3 backend. CI validates the region manifest and all regional ARN/endpoint references with `scripts/check_region_consistency.py`.

Example (only after the owner approves remote backend initialization):

```bash
bash scripts/terraform.sh -chdir=infra/envs/dev init -input=false -backend-config=backend.hcl
```

## GitHub Actions environment setup

\`configure_github_environments.sh\` creates/updates the six exact deployment environments, enforces their single allowed branch and configures independent reviewers. It is dry-run by default and requires GitHub CLI authenticated as a repository administrator plus an independent reviewer with repository access.

\`\`\`bash
bash scripts/configure_github_environments.sh
bash scripts/configure_github_environments.sh --apply
\`\`\`

The apply mode changes GitHub environment protection and deployment-branch settings. Review the dry-run output first. It does not populate AWS role/account/bucket variables, age recipients or private age identity secrets; those values must be added only after the approved AWS bootstrap creates the corresponding resources.

## Branch protection

\`configure_branch_protection.sh\` is dry-run by default. It requires PRs and the `python` and `terraform-fmt` checks, but sets mandatory approvals to zero so the solo owner can merge after CI. It also configures conversation resolution, admin enforcement and force-push/deletion restrictions for \`main\`, \`develop\` and \`solo/amit-monday\`.

\`\`\`bash
bash scripts/configure_branch_protection.sh
bash scripts/configure_branch_protection.sh --apply
\`\`\`

Run the dry-run first and inspect the exact changes. Apply mode requires GitHub CLI authenticated as a repository administrator. The required check contexts are the current CI job names \`python\` and \`terraform-fmt\`; verify these names in GitHub after applying.

## Read-only AWS bootstrap inventory

`scripts/aws_preflight_readonly.sh` verifies the authenticated STS identity and inspects the GitHub OIDC provider, runtime boundaries, six deployment roles and (when `TF_STATE_BUCKET` is supplied) state-bucket controls. It contains no create/update/delete/attach operations. Access-denied results are reported as unknown, not as proof that a resource is absent. The script has not been run against the owner's AWS account in this session.

Run it only with an intentionally selected AWS profile and read-only permissions:

```bash
AWS_PROFILE=<approved-profile> bash scripts/aws_preflight_readonly.sh
TF_STATE_BUCKET=<known-candidate-bucket> AWS_PROFILE=<approved-profile> bash scripts/aws_preflight_readonly.sh
```

## E2E smoke test

`e2e_smoke.sh` exercises a deployed dev stack without creating infrastructure. It creates one test employee, enrolls three JPEG photos, performs at least 20 kiosk upload/recognition cycles, verifies duplicate-scan debounce and queries the resulting attendance record. Its cleanup trap deactivates the test employee and deletes indexed face templates; the attendance/audit history remains.

## Safety requirements

- Run against **dev only**, never production.
- Use a consenting test participant and set `CONSENT_CONFIRMED=YES`.
- Do not put biometric photos or tokens in Git, screenshots, logs or shared shell history.
- Photos must be JPEGs between 1 KB and 1 MB. Supply three varied enrollment photos and a scan photo of the same consenting participant.
- Use an admin token and a kiosk-group token from the dev Cognito user pool.
- The test employee ID and email must be unique.

## Required environment

```bash
export API_BASE="https://<dev-api-or-cloudfront-origin>/api"
export ADMIN_TOKEN="<short-lived admin access token>"
export KIOSK_TOKEN="<short-lived kiosk access token>"
export EMPLOYEE_ID="E2E20261114"
export EMPLOYEE_NAME="Consent-based test participant"
export EMPLOYEE_EMAIL="unique-test-address@example.com"
export ENROLL_PHOTO_1="/secure/local/photo-1.jpg"
export ENROLL_PHOTO_2="/secure/local/photo-2.jpg"
export ENROLL_PHOTO_3="/secure/local/photo-3.jpg"
export SCAN_PHOTO="/secure/local/scan.jpg"
export CONSENT_CONFIRMED="YES"
```

Optional: `SHIFT_START`, `SHIFT_END`, `DEPARTMENT`, and `RUNS` (minimum 20; default 20).

Run:

```bash
bash scripts/e2e_smoke.sh
```

The reported p95 measures API request, S3 upload and recognition polling only. It does **not** include browser camera capture or result rendering, so it is not standalone evidence for SPEC N01. Complete the browser/device matrix in `docs/FRONTEND.md` separately.
