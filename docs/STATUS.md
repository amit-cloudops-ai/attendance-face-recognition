# Project status — 14 November 2026

## Executive status

The solo application and the T01–T38 deployment-security and region-guard task chain have been consolidated into `solo/amit-monday`. The T01–T15, T17 and T31–T37 implementation tasks are complete at the code/documentation level with historical CI evidence recorded in their task PRs. T16 and T18 remain blocked on repository-administrator and owner-controlled AWS-account information/actions.

The region-consistency implementation is complete on this branch: `config/deployment.json` is the canonical AWS region manifest; Terraform provider roots read it; the deployment workflow and local Terraform wrapper export it for the S3 backend; Lambda clients use the Lambda-reserved `AWS_REGION`; contracts and examples are aligned; CI rejects any noncanonical AWS region literal, regional ARN or regional endpoint. The full consolidated CI run 43622495235 passed on commit `65f82c6597bd9705c334b5cb2f6b3bfc528c946d` (27 Python/security steps and 21 Terraform formatting/validation steps).

**No AWS resources have been provisioned.** No OIDC provider, IAM roles, execution boundaries, state bucket, KMS key or budget resources have been created. No remote Terraform backend initialization, Terraform plan or apply has been run. Every AWS mutation remains approval-gated.

Target region: `us-east-1`, sourced from `config/deployment.json`. Read-only STS verification on 14 November 2026 confirmed AWS account `924422830139`, IAM user `Amit-admin`, through the `default` profile. This is the verified target account for the next planning step; no AWS mutation was performed.

## Source of truth and branch discipline

- Repository: `amit-cloudops-ai/attendance-face-recognition`.
- Governance: `AGENTS.md`, `docs/TASKS.md` and `docs/CHATGPT_PROJECT_INSTRUCTIONS.md`.
- Application baseline: `solo/amit-monday`.
- Security task chain: `ai/T01-repository-governance` through `ai/T37-billing-roles`, including T31–T36 cross-cutting tasks.
- Consolidation PR #28 from `release/phase-b-region-guard` into `solo/amit-monday` was merged successfully at `a43adea001009004597e19e1c04c14079205865a`. The merged head was `8bae76d788074e9c0d47d886fe355fddbcff709f`. Nothing is promoted to `develop` or `main`.
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

The task PR CI runs are historical evidence for their respective commits. The consolidated solo baseline CI passed on head `8bae76d`: Python/security 27/27 and Terraform 21/21. The solo baseline's later CI run 43623141820 also passed. PR #29 contains additional audit fixes and its latest CI result must be checked before merge. IAM templates have not been attached to AWS roles. IAM Access Analyzer and live AWS authorization tests have not been performed.

## Full pre-deployment audit — PR #29

**Audit status: IN PROGRESS.** This audit is being performed against the integrated solo release and the current fix branch. The changes below are in PR #29 and are not yet merged into `solo/amit-monday`.

### Static issues found and corrections prepared

| Finding | Correction in PR #29 | Verification still required |
|---|---|---|
| DynamoDB `kms:ViaService` statement was placed in the S3 web-bucket policy, not the KMS key policy | Moved the DynamoDB use statement into the actual KMS key policy; separated `CreateGrant` and constrained it with `kms:GrantIsForAWSResource=true`; added CI structural checks | Terraform validate and IAM Access Analyzer/live authorization in dev |
| Access module duplicated `us-east-1` literals | Uses `data.aws_region.current.name` from the configured provider | Terraform validate and region guard |
| Local wrappers and deployment workflow used `python` | Switched to `python3` | Local Ubuntu execution and GitHub CI |
| Deployment workflow did not assert the assumed AWS account | Added read-only STS check against `TF_VAR_account_id` before backend initialization | GitHub workflow plan run after approved bootstrap |
| Lambda application logs were not explicitly configured as JSON | Added JSON logging configuration and explicit 30-day log group references | Terraform validate and sample CloudWatch log inspection |
| Contract tests did not verify Terraform API route parity | Added static contract tests for route map/document parity, handler existence and JWT route authorization; clarified the `record_scan(request_id)` contract | Latest pytest run; expand payload-shape contract coverage |
| E2E smoke did not verify raw-image deletion or AWS account identity | Added STS account guard, per-object deletion checks and empty raw-prefix checks | Run only against dev after deployment, with a consenting participant |
| Solo-owner instructions conflicted with old reviewer/Part A/B/C instructions | Updated governance helpers, CODEOWNERS, AI instructions and deployment docs | GitHub settings dry-run and owner verification |
| Preflight checked bootstrap resources but not application resource-name collisions | Expanded read-only inventory to inspect project-prefixed S3, IAM, Lambda, DynamoDB, KMS, Rekognition, Cognito, API Gateway, SQS, SNS, Scheduler, CloudWatch, Budgets and CloudFront resources | Run expanded script; current AWS inventory output is still incomplete |

### Acceptance evidence status

| Requirement | Current status |
|---|---|
| N01 — browser capture-to-result p95 | NOT VERIFIED; API-path smoke timing is supplemental and excludes camera/rendering |
| N02 — raw image deletion within 10 minutes | Test strengthened; NOT RUN against dev |
| N03 — KMS encryption and TLS-only policies | Static Terraform/policy review only; no live resource verification |
| N04 — least-privilege runtime IAM | Static call-site review only; no IAM Access Analyzer/live authorization test |
| N05 — no public buckets / CloudFront-only web access | Static configuration only; no deployed bucket policy verification |
| N06 — clean checkout Terraform deployment | NOT RUN; no remote backend init, plan or apply |
| N07 — PR governance and branch protection | Helper scripts revised; GitHub environment/branch settings NOT APPLIED or verified |
| N08 — alarms and notifications | Terraform definitions exist; no alarm trigger test; SNS subscription confirmation pending |
| N09 — cost | Estimate only; saved Pricing Calculator estimate absent; budget scope is blocked (see T26) |
| N10 — JSON logs and 30-day retention | JSON logging configuration added in PR #29; no sample CloudWatch logs observed |
| N11 — Chrome/Android/Safari/iOS matrix | NOT RUN; browser matrix remains blank |

### Remaining limitations

- `tests/contract` now has static API route contract checks, but it does not yet assert every Lambda's full request/response and DynamoDB/S3 side-effect shapes. `tests/integration` remains empty.
- The expanded AWS inventory has not been executed. The earlier read-only run verified STS account `924422830139` and inspected bootstrap resources only; it did not check all application resource-name collisions.
- The local Ubuntu checkout cannot be inspected from GitHub. The owner must pull the audited branch and run the prescribed local checks.
- No AWS write, remote backend initialization, Terraform plan or apply has been performed.

## Region-consistency implementation

- Canonical value: `config/deployment.json` → `aws_region: us-east-1`.
- Dev, prod and billing Terraform provider roots load the canonical manifest; the access module now derives regional endpoints from the configured provider region rather than hardcoding a second region literal.
- S3 backend region is supplied from the same manifest through `scripts/terraform.sh` locally and the deployment workflow in GitHub Actions.
- Lambda SDK clients use the Lambda-reserved `AWS_REGION`; the local/test fallback remains `us-east-1`.
- Contracts are amended to v1.2: canonical region alignment plus explicit optional `request_id` argument for exactly-once scan processing and deterministic offboarding audit IDs. SPEC is v1.2; external HTTP request/response shapes remain unchanged.
- Frontend runtime examples, Cognito domain examples, raw-bucket endpoints, architecture decision log and cost assumptions are aligned.
- Moto test fixtures are aligned to the target region.
- CI runs `scripts/check_region_consistency.py`, which checks the manifest, Terraform roots, backend configuration, all repository text for noncanonical region tokens, regional ARNs/endpoints and Lambda region selection. The local Terraform wrapper and GitHub deployment workflow also run the full gate before proceeding.
- Full CI run 43622495235 passed on commit `65f82c6`.

No system can guarantee that a future contributor never writes an incorrect region, but the new automated gate is designed to fail every pull request/push that reintroduces a conflicting region into tracked project files.

## Remaining Phase B blockers

### T16 — GitHub environment variables, secrets and protections

**Status: BLOCKED — repository administrator action required.**

The required environments are `dev-plan`, `dev-apply`, `prod-plan`, `prod-apply`, `billing-plan` and `billing-apply`. Each must have the correct environment-scoped `AWS_ROLE_ARN`, account/bucket values, plan-only age recipient, apply-only private age identity secret and exact deployment-branch restriction.

The agreed governance model is **solo-owner**: the repository owner is the sole manual reviewer on apply environments, with self-review allowed. This is an owner checkpoint, not independent separation of duties. No teammate or second GitHub username is required. Branch protection requires PRs, CI checks, conversation resolution and protection against force-push/deletion, but does not require an independent approval or latest-push approval.

The GitHub connector cannot inspect or configure Actions environment secrets/protection settings, and branch-protection reads returned 403. Their actual existence and values remain unverified. The guarded helpers `scripts/configure_github_environments.sh` and `scripts/configure_branch_protection.sh` have been revised for this model. Both default to dry-run and require an explicit `--apply`; neither has been executed. Environment AWS variables/secrets remain intentionally unset until the AWS bootstrap is approved and creates the roles, bucket and boundaries.

**Owner action:** run both helpers' dry-runs, inspect the output, then decide whether to run their `--apply` modes from an authenticated repository-admin GitHub CLI session. Populate AWS role/account/bucket variables and age keys only after approved bootstrap. Provide confirmation or an authorized read-only verification path.

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

The exact account ID is now verified as `924422830139` through read-only STS in `us-east-1`. The read-only inventory completed on 14 November 2026 using profile `default`: GitHub OIDC `GetOpenIDConnectProvider` returned `NoSuchEntity`; the six expected GitHub roles returned `NoSuchEntity`; neither runtime boundary policy was returned; and no bucket matching `attendance-tf-state-924422830139-*` was found. The script labels these findings as unconfirmed where permissions could affect visibility. No matching project state bucket candidate was identified, and no AWS resource or policy was changed. The inventory output is recorded in the current conversation; the account-specific plan must use the verified account ID and clearly distinguish confirmed absence from unconfirmed visibility.

**Owner action:** choose/approve a globally unique state bucket suffix, review the exact resource and policy inventory rendered for account `924422830139`, and explicitly approve any bootstrap writes. Approval for bootstrap writes, Terraform backend initialization and Terraform plan/apply remain separate gates.

## IAM design limitations requiring explicit review

- API Gateway v2 child-resource paths remain scoped to the `/apis/*` resource family until the generated API ID can be pinned.
- Some AWS create APIs require `Resource: "*"`; request-tag, function and service conditions are used where supported.
- Billing's `aws-portal:ModifyBilling` is account-level and cannot be scoped to an individual budget ARN. It is isolated to the billing-apply role, main branch and owner approval checkpoint; it must never be attached to dev/prod roles.
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

1. Complete T16: configure and verify the six GitHub environments, their branch restrictions, environment variables/secrets and owner approval checkpoints. The current GitHub connector cannot configure or verify these settings; repository-admin action is required.
2. Complete T18 read-only verification: run `bash scripts/aws_preflight_readonly.sh` with an approved read-only AWS profile; verify the account ID, OIDC provider, state bucket, two boundaries, six roles and policy documents; choose a globally unique state bucket suffix.
3. Render the exact account-specific bucket policy, OIDC trust policies, boundaries and all 26 managed policy documents. Perform static and AWS-side policy validation; present the exact resource/action inventory and obtain explicit approval before any AWS write.
4. After separate bootstrap approval, create only the approved missing state bucket/OIDC provider/boundaries/roles/policies; verify all settings with read-only calls.
5. Initialize the dev backend only after its separate approval, run the dev plan, present the complete plan and obtain explicit apply approval. Apply only the reviewed saved plan.
6. Complete dev integration/privacy/performance/browser acceptance before a separately approved production plan/apply.
7. Promote the approved solo release to `develop` only through a reviewed PR. Keep teammate PR #2 separate throughout.

T19–T24 and T25–T30 remain release, deployment and operational acceptance work. Phase B is not fully closed until the repository-admin and owner-controlled blockers are resolved.

## Safety boundary

No AWS resources, IAM roles, OIDC provider, permissions boundaries, state bucket or KMS keys have been created by this work. No remote backend initialization, Terraform plan or Terraform apply has been run. Any AWS mutation requires an exact written plan and separate explicit owner approval before execution.
