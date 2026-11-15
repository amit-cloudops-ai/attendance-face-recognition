# Phase B — Deployment readiness and AWS access design

**Solo application branch:** `solo/amit-monday`  
**Application baseline:** `solo/amit-monday`  
**Scope:** Complete the deployment-security implementation and prepare an approval-gated development deployment. This document does not authorize AWS resource creation, IAM policy attachment, remote backend initialization, Terraform plan or Terraform apply.

## Verified deployment baseline

- Target AWS account: `924422830139`, verified by read-only STS using profile `default` on 14 November 2026.
- Canonical deployment region: `us-east-1`, declared only in `config/deployment.json`.
- Dev, prod and billing state keys are isolated: `attendance/dev/terraform.tfstate`, `attendance/prod/terraform.tfstate`, `attendance/billing/terraform.tfstate`.
- Terraform S3 native lock files are enabled (`use_lockfile = true`); Terraform is pinned to 1.10.5 in CI.
- Terraform providers load the region from the canonical manifest. The S3 backend receives the same value through `scripts/terraform.sh` locally and the deployment workflow in GitHub Actions.
- Lambda SDK clients use the Lambda-reserved `AWS_REGION`; the local/test fallback is the canonical region.
- CI includes a region-consistency gate intended to fail on conflicting region literals, stale regional endpoints, or Terraform roots that bypass the manifest. The gate is not considered complete until the consolidation branch's own CI passes.
- The manual deployment workflow uses GitHub OIDC, operation-specific plan/apply environments, encrypted saved-plan artifacts using `age`, exact plan commit/branch/run provenance and explicit environment gates.
- Dev workflow runs only from `develop`; prod and billing run only from `main`. The release branch must be reviewed and promoted through a PR before deployment workflow dispatch.

## Phase B implementation status

The task chain T01–T15, T17 and T31–T37 has implementation/documentation and historical CI evidence recorded in `docs/TASKS.md` and `docs/STATUS.md`. This includes:

- Per-handler runtime IAM reconciliation and environment-specific runtime permissions boundaries.
- Terraform provider IAM action mapping for foundation, data, recognition and access modules.
- Separate dev/prod plan and apply policies with exact environment resource/state scope.
- S3 state-bucket security specification and native lockfile permissions.
- Exact GitHub OIDC subjects and operation-specific deployment environments.
- Encrypted Terraform plan artifact provenance, one-day retention and cleanup.
- Terraform policy-template validation and provider lockfiles.
- Scheduler trust hardening, CloudFront KMS scope, DynamoDB KMS ViaService access and isolated billing roles.

T16 and T18 remain blocked on repository-admin and owner approval gates. T38 (canonical region manifest and drift-prevention gate) is implemented; the latest solo-owner governance and audit-fix PR CI must pass before this branch is treated as release-ready.

## Security design requirements

1. Plan roles may refresh/read infrastructure and access only their matching state/lock paths. They must not mutate application infrastructure.
2. Apply roles may mutate only resources in their matching environment root. They must not receive broad account administration.
3. Dev, prod and billing roles must never access each other's Terraform state or lock objects.
4. `iam:PassRole` must be limited to exact application execution-role ARNs and the correct service principal.
5. Every Terraform-created Lambda and Scheduler role must receive the exact pre-created environment permissions boundary. Apply roles may attach the boundary but must not edit/delete its policy or create an unbounded role.
6. The public repository must not upload cleartext Terraform plans. Plans are encrypted with environment-specific age recipients; private identities exist only as matching apply-environment secrets.
7. GitHub environments must enforce exact branch restrictions and the repository owner's manual approval checkpoint for apply operations. Self-review is allowed in the solo-owner model; this is not independent separation of duties.
8. Billing actions remain isolated to the billing role pair. In particular, account-level `aws-portal:ModifyBilling` must never be attached to dev/prod roles.
9. No AWS write, role assumption, backend initialization, plan or apply may occur before the corresponding owner approval.

## Remaining owner/repository-administrator gates

### T16 — GitHub environment configuration

Create and verify six exact environments: `dev-plan`, `dev-apply`, `prod-plan`, `prod-apply`, `billing-plan`, `billing-apply`. Configure environment-scoped `AWS_ROLE_ARN`, account/state bucket values, separate age recipients and apply-only private age identity secrets. Restrict dev environments to `develop`; restrict prod and billing to `main`. Apply environments require the repository owner's manual approval checkpoint, with self-review allowed. No teammate reviewer is required.

The current GitHub connection cannot inspect or configure environment settings/secrets or branch protection. This remains an explicit repository-admin task. The agreed solo-owner model uses owner-only apply checkpoints and no independent review.

### T18 — exact account-specific bootstrap plan

The account ID is verified as `924422830139`. The read-only preflight in `us-east-1` returned `NoSuchEntity` for the expected GitHub OIDC provider and six expected roles, no matching runtime boundary policies, and no bucket matching `attendance-tf-state-924422830139-*`. Treat boundary/policy visibility as unconfirmed where IAM read permissions may affect results. No AWS resources or policies were changed. The final state bucket suffix and exact rendered bootstrap inventory still require owner review.

## Manual bootstrap inventory — proposal only

| Resource | Count | Proposed identity |
|---|---:|---|
| S3 state bucket | 1 | `attendance-tf-state-<account-id>-<approved-suffix>` |
| IAM OIDC provider | 1 | `token.actions.githubusercontent.com`; reuse if present |
| Runtime permissions boundaries | 2 | `attendance-dev-execution-boundary`, `attendance-prod-execution-boundary` |
| GitHub plan/apply roles | 6 | dev-plan, dev-apply, prod-plan, prod-apply, billing-plan, billing-apply |
| Managed policy templates | 26 | 22 dev/prod plan/apply policies + 4 billing policies |
| GitHub environments | 6 | Exact names listed under T16 |

The bucket must be in `us-east-1`, with all four S3 Block Public Access settings enabled, versioning, SSE-S3 default encryption, BucketOwnerEnforced ownership and a TLS-only deny policy. It must not have Object Lock or automatic state expiration.

The role/policy inventory, exact trust documents, rendered policy JSON and bucket policy are documented in `docs/MANUAL-AWS-BOOTSTRAP-PLAN.md`, `docs/STATE-BUCKET-BOOTSTRAP.md` and `infra/policies/`. These remain templates until the account ID is verified and the owner approves the exact inventory.

## Read-only account verification before bootstrap

After the owner supplies or authorizes an authenticated AWS CLI session, run `bash scripts/aws_preflight_readonly.sh` with read-only permissions. It verifies STS identity/region, inspects the OIDC provider, two boundary policies, six role trust policies/attachments and, when `TF_STATE_BUCKET` is supplied, bucket location/ownership/public-access/versioning/encryption/policy. Record exact ARNs and distinguish "not found" from "access denied". Do not create missing resources during this pass.

The live read-only AWS inventory has now been run against account `924422830139`. No writes were performed. A repository connection alone is not proof of AWS account access; the STS result is the verified identity evidence.

## Deployment sequence after gates are satisfied

1. Complete T16 GitHub environment and branch-protection configuration.
2. Verify the AWS account ID and run the read-only inventory described above.
3. Choose the globally unique state bucket suffix and render the exact bootstrap resource/policy inventory.
4. Present the full bootstrap plan to the owner and obtain explicit approval for the listed AWS mutations.
5. Bootstrap only the approved state bucket/OIDC provider/permissions boundaries/roles/policies; reuse existing compatible resources rather than duplicating them.
6. Verify every created/attached resource using read-only calls and record the exact ARNs.
7. Initialize the dev backend and generate a dev plan only after separate approval. Review the complete plan, cost and resource actions with the owner; obtain explicit apply approval before applying that exact saved plan.
8. Complete dev authentication, upload/recognition, attendance, reports, alarms, privacy, deletion, latency and browser acceptance.
9. Production and billing operations require their own exact plan review and separate approval. Production remains blocked until dev acceptance and a separately approved production plan/apply by the owner.

## Safety boundary

No AWS resources have been created by this preparation. No IAM roles or policies have been created/attached, no OIDC provider or state bucket has been created, no remote backend has been initialized, and no Terraform plan or apply has been run. Any AWS mutation requires an exact written plan and separate explicit owner approval.
