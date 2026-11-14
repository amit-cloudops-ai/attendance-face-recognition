# Project status — 14 November 2026

## Executive status

The solo application and the T01–T37 deployment-security task chain have been consolidated on the release-preparation branch. The T01–T15, T17 and T31–T37 implementation tasks are complete at the code/documentation level with historical CI evidence recorded in their task PRs. T16 and T18 remain blocked on repository-administrator and owner-controlled AWS-account information/actions.

The region-consistency implementation is complete on this branch: `config/deployment.json` is the canonical AWS region manifest; Terraform provider roots read it; the deployment workflow and local Terraform wrapper export it for the S3 backend; Lambda clients use the Lambda-reserved `AWS_REGION`; contracts and examples are aligned; CI rejects any noncanonical AWS region literal, regional ARN or regional endpoint. The full consolidated CI run 43622495235 passed on commit `65f82c6597bd9705c334b5cb2f6b3bfc528c946d` (27 Python/security steps and 21 Terraform formatting/validation steps).

**No AWS resources have been provisioned.** No OIDC provider, IAM roles, execution boundaries, state bucket, KMS key or budget resources have been created. No remote Terraform backend initialization, Terraform plan or apply has been run. Every AWS mutation remains approval-gated.

Target region: `us-east-1`, sourced from `config/deployment.json`. Target account: the owner's existing AWS account; the exact 12-digit account ID has not been verified in this session.

## Source of truth and branch discipline

- Repository: `amit-cloudops-ai/attendance-face-recognition`.
- Governance: `AGENTS.md`, `docs/TASKS.md` and `docs/CHATGPT_PROJECT_INSTRUCTIONS.md`.
- Application baseline: `solo/amit-monday`.
- Security task chain: `ai/T01-repository-governance` through `ai/T37-billing-roles`, including T31–T36 cross-cutting tasks.
- Current consolidation branch: `release/phase-b-region-guard`, created from `ai/T37-billing-roles`. It contains the stacked task work and the new region-consistency changes.
- Draft consolidation PR #28 is open from `release/phase-b-region-guard` into `solo/amit-monday`: https://github.com/amit-cloudops-ai/attendance-face-recognition/pull/28. It is mergeable and not merged. The task PRs remain open and unmerged; PR #28 is the single consolidation path. Nothing is promoted to `develop` or `main`.
- Teammate Part B PR #2 remains separate and untouched. Do not merge teammate work into the solo release.

## Completed security implementation

| Work | Scope | Evidence |
|---|---|---|
| T01–T05, T31 | Governance, async DLQ KMS, recognition/data runtime IAM, runtime region selection and execution boundaries | PRs #3–#8; CI runs 43611844694, 43612039939, 43612245039, 43612668343, 43612832683, 43613054015 |
| T06–T08 | Terraform provider IAM action mapping for foundation, data/recognition and access modules | PRs #9–#11; CI runs 43613487881, 43614059591, 43615508377 |
| T09–T12 | Dev/prod plan and apply policy sets, split managed policies, state isolation, exact PassRole scopes and runtime boundaries | PRs #12, #18–#20; CI runs 43615873597, 43617809368, 43617967197, 43618294918 |
| T13–T15 | State-bucket security specification, OIDC trust and encrypted plan-artifact provenance | PRs #21–#23; CI runs 43618372200, 43618685801, 43618692691 |
| T17 | Terraform/JSON policy template linting and guard for future SAM/CloudFormation | PR #25; CI run 43619026006 |
| T32–T36 | Scheduler trust isolation, provider lockfiles, billing isolation, CloudFront KMS scope and DynamoDB KMS authorization | PRs #13–#17; CI runs 43616332197, 43616787686, 43617044959, 43617191177 |
| T37 | Dedicated billing plan/apply policy and OIDC roles, isolated billing state root | PR #27; CI run 43620012088 |

The task PR CI runs are historical evidence for their respective commits. The consolidated branch has now passed its own full CI on commit `65f82c6`; the final documentation/status-only commits are being rechecked. IAM templates have not been attached to AWS roles. IAM Access Analyzer and live AWS authorization tests have not been performed.

## Region-consistency implementation

- Canonical value: `config/deployment.json` → `aws_region: us-east-1`.
- Dev, prod and billing Terraform providers load the canonical manifest rather than carrying separate provider-region literals.
- S3 backend region is supplied from the same manifest through `scripts/terraform.sh` locally and the deployment workflow in GitHub Actions.
- Lambda SDK clients use the Lambda-reserved `AWS_REGION`; the local/test fallback remains `us-east-1`.
- Contracts are amended to v1.1 for the region-only change. SPEC is amended to v1.1; functional scope and acceptance criteria are unchanged.
- Frontend runtime examples, Cognito domain examples, raw-bucket endpoints, architecture decision log and cost assumptions are aligned.
- Moto test fixtures are aligned to the target region.
- CI runs `scripts/check_region_consistency.py`, which checks the manifest, Terraform roots, backend configuration, all repository text for noncanonical region tokens, regional ARNs/endpoints and Lambda region selection. The local Terraform wrapper and GitHub deployment workflow also run the full gate before proceeding.
- Full CI run 43622495235 passed on commit `65f82c6`.

No system can guarantee that a future contributor never writes an incorrect region, but the new automated gate is designed to fail every pull request/push that reintroduces a conflicting region into tracked project files.

## Remaining Phase B blockers

### T16 — GitHub environment variables, secrets and protections

**Status: BLOCKED — repository administrator action required.**

The required environments are `dev-plan`, `dev-apply`, `prod-plan`, `prod-apply`, `billing-plan` and `billing-apply`. Each must have the correct environment-scoped `AWS_ROLE_ARN`, account/bucket values, plan-only age recipient, apply-only private age identity secret, branch restriction and independent apply reviewer.

The GitHub connector cannot inspect or configure Actions environment secrets/protection settings, and branch-protection reads returned 403. Their actual existence and values remain unverified.

**Owner action:** configure the six environments using `docs/GITHUB-ENVIRONMENT-SETUP.md` and provide confirmation or an authorized read-only verification path.

### T18 — exact manual AWS bootstrap plan

**Status: BLOCKED — account identity and owner approval required.**

The plan enumerates:
- One dedicated S3 state bucket in `us-east-1`, with a globally unique account-specific name.
- One GitHub Actions OIDC provider, reused if already present.
- Two pre-created runtime permissions boundaries (dev and prod).
- Six GitHub plan/apply roles across dev, prod and billing.
- 26 managed policy templates/attachments across the three isolated roots.
- Six matching GitHub environments and the required variables/secrets.
- Read-only existence checks, bootstrap order, rollback and approval gates.

The exact 12-digit AWS account ID, final bucket suffix and current resource inventory are not known. A read-only inventory script now exists at `scripts/aws_preflight_readonly.sh`, but it has not been run against the owner's account. The bootstrap plan must be rendered with verified account values and presented to the owner before any write operation.

**Owner action:** provide/confirm the account ID and final bucket suffix, run or authorize read-only inventory, then review and explicitly approve the exact resource and policy inventory. Approval for bootstrap writes and approval for Terraform plan/apply remain separate.

## IAM design limitations requiring explicit review

- API Gateway v2 child-resource paths remain scoped to the `/apis/*` resource family until the generated API ID can be pinned.
- Some AWS create APIs require `Resource: "*"`; request-tag, function and service conditions are used where supported.
- Billing's `aws-portal:ModifyBilling` is account-level and cannot be scoped to an individual budget ARN. It is isolated to the billing-apply role, main branch and independent reviewer gate; it must never be attached to dev/prod roles.
- Static template validation does not prove live AWS authorization. Rendered policies still require IAM Access Analyzer/review and a controlled dev deployment.

## Exact bootstrap inventory — not executed

| Category | Count | Names/scope |
|---|---:|---|
| S3 state bucket | 1 | `attendance-tf-state-<account-id>-<approved-suffix>` |
| IAM OIDC provider | 1 | `token.actions.githubusercontent.com` |
| Runtime permissions boundaries | 2 | `attendance-dev-execution-boundary`, `attendance-prod-execution-boundary` |
| GitHub plan/apply roles | 6 | dev-plan, dev-apply, prod-plan, prod-apply, billing-plan, billing-apply |
| Managed policy templates | 26 | 22 dev/prod plan/apply + 4 billing plan/apply |
| GitHub environments | 6 | dev-plan, dev-apply, prod-plan, prod-apply, billing-plan, billing-apply |

The exact role trust documents, managed policy JSON, account IDs and bucket name must be rendered and reviewed before creation. Existing resources must be inspected first; no duplicate provider, bucket, role or policy should be created.

## Next sequence

1. Owner-review draft PR #28 and merge it into `solo/amit-monday` when approved. Do not promote to `develop` or `main` yet.
2. Complete T16: configure and verify the six GitHub environments, variables, secrets, branch restrictions and independent reviewers.
3. Complete T18 read-only verification: run `bash scripts/aws_preflight_readonly.sh` with an approved read-only AWS profile; verify the account ID and existing resource inventory; choose the state bucket suffix.
4. Render the exact account-specific bootstrap plan and all trust/policy documents; present them and obtain explicit approval before any AWS write.
5. Only after separate approval, bootstrap the approved state bucket/OIDC/roles/boundaries/policies. Verify the result using read-only calls.
6. Initialize the dev backend only after its separate approval, generate a dev plan, present the complete plan and obtain explicit apply approval.
7. Complete dev integration/privacy/performance/browser acceptance before a separately approved production plan/apply.
8. Keep teammate PR #2 separate throughout.

T19–T24 and T25–T30 remain release, deployment and operational acceptance work. Phase B is not fully closed until the repository-admin and owner-controlled blockers are resolved.

## Safety boundary

No AWS resources, IAM roles, OIDC provider, permissions boundaries, state bucket or KMS keys have been created by this work. No remote backend initialization, Terraform plan or Terraform apply has been run. Any AWS mutation requires an exact written plan and separate explicit owner approval before execution.
