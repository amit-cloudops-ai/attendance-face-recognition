# Phase B — Deployment readiness and AWS access design

**Consolidation branch:** `release/phase-b-region-guard`  
**Application baseline:** `solo/amit-monday`  
**Scope:** Complete the deployment-security implementation and prepare an approval-gated development deployment. This document does not authorize AWS resource creation, IAM policy attachment, remote backend initialization, Terraform plan or Terraform apply.

## Verified deployment baseline

- Target AWS account ID provided by the owner: `924422830139`; the authenticated STS identity still must be verified before any AWS mutation.
- Canonical deployment region: `us-east-1`, declared only in `config/deployment.json`.
- Dev, prod and billing state keys are isolated: `attendance/dev/terraform.tfstate`, `attendance/prod/terraform.tfstate`, `attendance/billing/terraform.tfstate`.
- Terraform S3 native lock files are enabled (`use_lockfile = true`); Terraform is pinned to 1.10.5 in CI.
- Terraform providers load the region from the canonical manifest. The S3 backend receives the same value through `scripts/terraform.sh` locally and the deployment workflow in GitHub Actions.
- Lambda SDK clients use the Lambda-reserved `AWS_REGION`; the local/test fallback is the canonical region.
- CI includes a region-consistency gate that fails on conflicting region literals, stale regional endpoints, or Terraform roots that bypass the manifest. A follow-up audit caught and corrected hardcoded access-module region values and a DynamoDB KMS statement incorrectly placed in an S3 bucket policy. PR #31 passed its own CI run 43680111003 (118 Python tests and both jobs); these changes are integrated in PR #33 and the combined candidate CI is still being verified.
- The manual deployment workflow uses GitHub OIDC, operation-specific plan/apply environments, encrypted saved-plan artifacts using `age`, exact plan commit/branch/run provenance and explicit environment gates. It now also verifies that the assumed role ARN, state-bucket prefix and STS caller account match the configured account ID before remote Terraform initialization.
- Dev workflow runs only from `develop`; prod and billing run only from `main`. The release branch must be reviewed and promoted through a PR before deployment workflow dispatch.

## Phase B implementation status

The task chain T01–T15, T17 and T31–T38 has implementation/documentation and CI evidence recorded in `docs/TASKS.md` and `docs/STATUS.md`. T38's follow-up corrections passed on PR #31 individually and are integrated in the isolated PR #33 release candidate; combined CI on the final candidate commit remains a release gate. This includes:

- Per-handler runtime IAM reconciliation and environment-specific runtime permissions boundaries.
- Terraform provider IAM action mapping for foundation, data, recognition and access modules.
- Separate dev/prod plan and apply policies with exact environment resource/state scope.
- S3 state-bucket security specification and native lockfile permissions.
- Exact GitHub OIDC subjects and operation-specific deployment environments.
- Encrypted Terraform plan artifact provenance, one-day retention and cleanup.
- Terraform policy-template validation and provider lockfiles.
- Scheduler trust hardening, CloudFront KMS scope, DynamoDB KMS ViaService access and isolated billing roles.

T16 and T18 remain owner/admin tasks for the optional OIDC/GitHub Actions pipeline. The first dev deployment can use the solo local bootstrap in `docs/DEPLOYMENT-RUNBOOK.md`; it does not require the OIDC provider, six deployment roles, six GitHub environments or promotion to `develop`. The access-module/KMS follow-up and readiness fixes were integrated into `release/aws-readiness-candidate` by PR #34 (squash commit `ba31ad365a75f9539ef07282bce22992899b1b97`).

## Security design requirements

1. Plan roles may refresh/read infrastructure and access only their matching state/lock paths. They must not mutate application infrastructure.
2. Apply roles may mutate only resources in their matching environment root. They must not receive broad account administration.
3. Dev, prod and billing roles must never access each other's Terraform state or lock objects.
4. `iam:PassRole` must be limited to exact application execution-role ARNs and the correct service principal.
5. Every Terraform-created Lambda and Scheduler role must receive the exact pre-created environment permissions boundary. Apply roles may attach the boundary but must not edit/delete its policy or create an unbounded role.
6. The public repository must not upload cleartext Terraform plans. Plans are encrypted with environment-specific age recipients; private identities exist only as matching apply-environment secrets.
7. GitHub environments must enforce exact branch restrictions. The agreed solo-owner model has zero mandatory external approvals and allows owner self-review; independent reviewers can be added if another trusted operator joins.
8. Billing actions remain isolated to the billing role pair. In particular, account-level `aws-portal:ModifyBilling` must never be attached to dev/prod roles.
9. No AWS write, role assumption, backend initialization, plan or apply may occur before the corresponding owner approval.

## Remaining owner/repository-administrator gates

### T16 — GitHub environment configuration

For the optional OIDC pipeline, create and verify six exact environments: `dev-plan`, `dev-apply`, `prod-plan`, `prod-apply`, `billing-plan`, `billing-apply`. Configure environment-scoped `AWS_ROLE_ARN`, account/state bucket values, separate age recipients and apply-only private age identity secrets. Restrict dev environments to `develop`; restrict prod and billing to `main`. In the solo-owner phase, require zero external approvals and allow owner self-review. This step is not needed for the first local dev deployment.

The current GitHub connection cannot inspect or configure environment settings/secrets or branch protection. These settings remain an explicit repository-admin task for the optional pipeline path.

### T18 — exact account-specific bootstrap plan

The policy templates and manual bootstrap inventory are prepared. The target account ID `924422830139` was provided by the owner but must be confirmed against STS; the final globally unique bucket name and current AWS resource inventory are not verified. The local dev path uses the runbook's smaller bootstrap sequence and does not require OIDC roles or GitHub environments. The plan must be rendered against the authenticated account and checked for existing providers, buckets, roles, policies and boundaries before any create operation is proposed.

## Manual bootstrap inventory — proposal only

| Resource | Count | Proposed identity |
|---|---:|---|
| S3 state bucket | 1 | `attendance-tf-state-<account-id>-<approved-suffix>` |
| IAM OIDC provider | 1 | `token.actions.githubusercontent.com`; reuse if present |
| Runtime permissions boundaries | 2 | `attendance-dev-execution-boundary`, `attendance-prod-execution-boundary` |
| GitHub plan/apply roles | 6 | dev-plan, dev-apply, prod-plan, prod-apply, billing-plan, billing-apply |
| Managed policy templates | 28 | 22 dev/prod plan/apply policies + 4 billing policies + 2 temporary CloudFront bootstrap policies |
| GitHub environments | 6 | Exact names listed under T16 |

The bucket must be in `us-east-1`, with all four S3 Block Public Access settings enabled, versioning, SSE-S3 default encryption, BucketOwnerEnforced ownership and a TLS-only deny policy. It must not have Object Lock or automatic state expiration.

The pipeline inventory comprises 28 managed policy documents, 2 runtime boundaries, 6 OIDC trust documents and 1 generated TLS-only bucket policy (37 policy documents total). The role/policy inventory, exact trust documents, rendered policy JSON and bucket policy are documented in `docs/MANUAL-AWS-BOOTSTRAP-PLAN.md`, `docs/STATE-BUCKET-BOOTSTRAP.md` and `infra/policies/`. These remain templates until the account ID is verified and the owner approves the exact inventory.

## Read-only account verification before bootstrap

After the owner supplies or authorizes an authenticated AWS CLI session, run `bash scripts/aws_preflight_readonly.sh` with read-only permissions. It verifies STS identity/region, inspects the OIDC provider, two boundary policies, six role trust policies/attachments and, when `TF_STATE_BUCKET` is supplied, bucket location/ownership/public-access/versioning/encryption/policy. Record exact ARNs and distinguish "not found" from "access denied". Do not create missing resources during this pass.

The repository contains no verified account ID or live AWS inventory yet. A repository connection is not proof of AWS account access.

## Deployment sequence after gates are satisfied

For the first dev deployment, follow `docs/DEPLOYMENT-RUNBOOK.md#1-solo-local-dev-bootstrap-owner-operated-path`; T16/OIDC setup is not required. For the later OIDC pipeline path only:
1. Complete T16 GitHub environment and branch-protection configuration.
2. Verify the AWS account ID against STS and run the read-only inventory described above.
3. Choose the globally unique state bucket suffix and render the exact bootstrap resource/policy inventory.
4. Present the full bootstrap plan to the owner and obtain explicit approval for the listed AWS mutations.
5. Bootstrap only the approved OIDC provider/roles/policies; reuse existing compatible resources rather than duplicating them.
6. Verify every created/attached resource using read-only calls and record the exact ARNs.
7. Initialize the dev backend and generate a dev plan only after separate approval. Review the complete plan, cost and resource actions with the owner; obtain explicit apply approval before applying that exact saved plan.
8. Complete dev authentication, upload/recognition, attendance, reports, alarms, privacy, deletion, latency and browser acceptance.
9. Production and billing operations require their own exact plan review and separate approval. Production remains blocked until dev acceptance and separate owner approval under the solo-owner model.

## Safety boundary

No AWS resources have been created by this preparation. No IAM roles or policies have been created/attached, no OIDC provider or state bucket has been created, no remote backend has been initialized, and no Terraform plan or apply has been run. Any AWS mutation requires an exact written plan and separate explicit owner approval.


## Integrated release-candidate work

PR #33 integrates PR #30 (T16 helper correction), PR #31 (T38 access-region and KMS policy correction) and PR #32 (T18 read-only bootstrap inventory renderer). It also adds an API route contract test and a Moto-backed employee API integration test. The candidate has not been merged. Its first combined CI attempts exposed Ruff and contract-test parser defects; both were corrected, and a fresh green run on the latest candidate head is required before this document can be treated as a completed gate.

The repository now includes `docs/DEPLOYMENT-RUNBOOK.md` and `docs/OPERATIONS-RUNBOOK.md`. Live AWS policy analysis, account preflight, GitHub environment configuration, restore testing, budget/alert delivery and deployed browser/camera acceptance remain unverified.
