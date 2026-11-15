# Task board

This board is the execution queue for the attendance face-recognition project. Task IDs are stable. Work is isolated on dedicated ai/T## branches and promoted through pull requests. A task is DONE only after its acceptance criteria pass and evidence is recorded.

Status values: TODO, IN_PROGRESS, BLOCKED, DONE.

## Repository governance

| ID | Task | Status | Acceptance criteria |
|---|---|---|---|
| T01 | Restore repository working rules, task board and project instructions | DONE | Governance files exist, agree with the approved workflow, status is accurate and CI passes |

## Phase B — deployment security and readiness

| ID | Task | Status | Acceptance criteria |
|---|---|---|---|
| T02 | Validate KMS key policy for Lambda asynchronous failure destinations | DONE | AWS service-principal model, source ARN/account conditions and exact DLQ ARNs checked against AWS docs |
| T03 | Reconcile recognition Lambda runtime IAM permissions | DONE | Every SDK call mapped to exact action/resource; Rekognition, S3, DynamoDB, SQS, KMS and logs checked |
| T04 | Reconcile data Lambda runtime IAM permissions | DONE | Every SDK call mapped to exact action/resource; no unused permissions or unjustified KMS grants |
| T05 | Finalize dev/prod execution-role permissions boundaries | DONE | Environment allow-list boundaries cap runtime permissions; no IAM/STS self-management, PassRole or provisioning; CI validates rendered policy |
| T06 | Verify Terraform provider IAM actions for foundation module | DONE | Create/read/update/delete/tag operations mapped to exact IAM actions and resource scopes |
| T07 | Verify Terraform provider IAM actions for data and recognition modules | DONE | Provider operations mapped for Lambda, IAM, DynamoDB, Scheduler, SQS, Rekognition, S3 and CloudWatch |
| T08 | Verify Terraform provider IAM actions for access module | DONE | Cognito, API Gateway v2, CloudFront, S3 and Lambda permission operations mapped |
| T09 | Build dev plan-role policy | DONE | Read-only planning permissions, dev-only state/lock access, no resource mutation |
| T10 | Build dev apply-role policy | DONE | Split apply policies, exact dev resources, mandatory execution boundary, exact PassRole scopes and dev-only state |
| T11 | Build prod plan-role policy | DONE | Read-only planning permissions, prod-only state/lock access, no resource mutation |
| T12 | Build prod apply-role policy | DONE | Split apply policies, exact prod resources, mandatory execution boundary, exact PassRole scopes and prod-only state |
| T13 | Review Terraform state bucket bootstrap specification | DONE | Versioning, public access block, SSE-S3, ownership controls, TLS-only policy and state/lock object scope documented |
| T14 | Audit GitHub OIDC trust and deployment workflow permissions | DONE | Exact audience/subjects, operation-specific environments, branch gates, token permissions and no static credentials |
| T15 | Audit encrypted Terraform plan artifact lifecycle | DONE | Exact workflow/run/attempt/commit binding, encryption, one-day retention, artifact access and identity cleanup |
| T16 | Reconcile GitHub environment variables, secrets and protection rules | BLOCKED | Optional OIDC pipeline only; exact environment variables/secrets and branch restrictions require repository-admin setup. Solo-owner mode has zero mandatory external approvals and allows self-review; local first dev deployment does not depend on T16 |
| T17 | Add or verify infrastructure template linting in CI | DONE | No CloudFormation/SAM source exists; Terraform and JSON policy templates are validated; CI fails if unlinted CloudFormation/SAM is introduced |
| T18 | Produce exact manual bootstrap change plan | BLOCKED | OIDC pipeline bootstrap only; owner must verify STS identity against target account 924422830139, choose a unique bucket suffix, review 6 OIDC trust policies, 2 boundaries, 28 managed policy documents and 1 generated bucket policy, then approve the exact write inventory. First dev can use the solo local path in DEPLOYMENT-RUNBOOK.md without OIDC roles/environments |
| T19 | Open solo-only deployment-readiness PR to develop | TODO | T16/T18 and required security/CI gates resolved; PR contains only approved solo implementation; teammate PRs remain separate |
| T20 | Review and obtain approval for dev Terraform plan | TODO | Local dev backend and variables are ready; full saved dev plan is shown and explicitly approved before apply. OIDC roles are not a prerequisite for the local first-dev path |
| T21 | Deploy and validate dev environment | TODO | Explicit apply approval; smoke/integration checks, Cognito/CORS/CloudFront validation and rollback readiness evidenced |
| T22 | Complete privacy, deletion, latency and browser acceptance | TODO | Raw-image deletion evidence, consent checks, 20-scan p95, Chrome/Android and Safari/iOS checks |
| T23 | Prepare production release review | TODO | Dev acceptance complete, security/cost evidence, rollback plan and separate production approval |
| T24 | Deploy production after explicit approval | TODO | Exact production plan reviewed and approved; production apply and post-deploy checks evidenced |\n| T39 | Replace hosted sign-in redirect with first-party Cognito SRP authentication | IN_PROGRESS | Branded credential form; SRP proof exchange; MFA and password-recovery challenge handling; validated token/session and admin-only redirect; unit/contract tests and CI pass; no hosted-login redirect in normal flow |

## Phase B cross-cutting hardening

| ID | Task | Status | Acceptance criteria |
|---|---|---|---|
| T31 | Align all Lambda runtime SDK clients with us-east-1 | DONE | All 14 handlers and shared helpers use Lambda AWS_REGION with us-east-1 fallback; CI and unit tests pass |
| T32 | Constrain EventBridge Scheduler execution-role trust | DONE | Separate dev/prod schedule groups; trust requires exact group ARN and source account |
| T33 | Pin Terraform providers and commit environment lockfiles | DONE | AWS 6.73.0 and archive 2.8.1 pinned; dev/prod lockfiles committed; CI uses readonly lockfile mode |
| T34 | Isolate AWS Budgets from normal deployment roles | DONE | Budgets moved to separate billing root/state; dev/prod roles have no billing permissions; dedicated billing roles tracked separately in T37 |
| T35 | Scope CloudFront KMS key policy to exact distribution | DONE | CloudFront decrypt grant uses exact distribution ARN and source account; no distribution wildcard |
| T36 | Add DynamoDB customer-managed KMS authorization | DONE | Customer-managed key policy and dev/prod apply fragments use exact DynamoDB ViaService and environment alias; CreateGrant is AWS-resource constrained |
| T37 | Build dedicated billing plan/apply policies and OIDC roles | DONE | Billing root has separate plan/apply roles, exact budgets/billing actions and separate OIDC subjects; no billing actions in environment roles |

| T38 | Establish canonical AWS region manifest and CI drift prevention | DONE | Canonical region is enforced; access-module region/KMS corrections are integrated in PR #33 and exact release-candidate CI passed |

## Phase C — release and operations

| ID | Task | Status | Acceptance criteria |
|---|---|---|---|
| T25 | Establish operational runbooks and incident response | IN_PROGRESS | Deployment and operations runbooks are drafted; operational owner assignment and live alert/incident drill remain required |
| T26 | Verify budget alarms and cost guardrails | IN_PROGRESS | Dev/prod USD 15 budgets with 80%/100% actual-cost notifications and concurrency controls are defined; live email delivery and cost behavior remain untested |
| T27 | Verify backup, restore and disaster recovery procedures | IN_PROGRESS | DynamoDB PITR, reports/state versioning and recovery steps are documented; a dev restore drill remains required |
| T28 | Add dependency and container/code supply-chain checks | IN_PROGRESS | CI pins all GitHub Actions to full commit SHAs, pins Python dependencies, runs pip-audit and enforces pins; Dependabot weekly updates are configured. Container scanning and broader SBOM/provenance checks remain open |
| T29 | Complete end-to-end release documentation | IN_PROGRESS | Obsolete deployment steps are being replaced with the six-environment workflow; local reproducibility and final cross-document review remain |
| T30 | Conduct final production readiness review | TODO | All release acceptance evidence reviewed; remaining risks accepted by owner |

## Live AWS execution notes — 15 November 2026

- WSL profile is `default`; STS identity is `arn:aws:iam::924422830139:user/Amit-admin` in account `924422830139`, region `us-east-1`.
- Existing dev HTTP API `attendance-dev-http-api` ID `7nii6lm2z2` was verified with matching project/environment/component tags; no stages, routes or integrations. Do not create a duplicate.
- Read-only preflight found no OIDC provider, six GitHub deployment roles, dev/prod execution boundary policies or account-prefixed state bucket. OIDC roles/provider are optional for local first dev deployment.
- Dev boundary JSON passed IAM Access Analyzer with zero findings; no matching local managed policy exists yet.
- Candidate state bucket `attendance-tf-state-924422830139-amit-2026-1115` had a 404 HeadBucket result at render time; recheck immediately before creation.
- Lambda quota is 10 with 10 unreserved; use `null` for all five initial dev reserved-concurrency values unless quota changes.
- Renderer produced 37 local policy documents; no IAM/S3 resources, backend initialization, Terraform plan or apply have been performed in this sequence.
- Next: create only the approved dev execution boundary and protected state bucket, verify both read-only, then prepare local backend and variables. Plan and apply remain separate approval gates.

## Task execution notes

- T01–T09 and T31–T36 are complete with CI evidence recorded in docs/STATUS.md and the corresponding PRs.
- T10 dev apply policies: PR #18; CI run 43617809368 passed.
- T11 prod plan policies: PR #19; CI run 43617967197 passed.
- T12 prod apply policies: PR #20; CI run 43618294918 passed.
- T13 state bucket bootstrap specification: PR #21; CI run 43618372200 passed.
- T14 GitHub OIDC hardening: PR #22; CI run 43618685801 passed.
- T15 encrypted plan artifact lifecycle: PR #23; CI run 43618692691 passed.
- T16 GitHub environment setup: PR #34 aligns the helper and docs with the solo-owner model (zero mandatory external approvals; self-review allowed). The six environment variables/secrets and branch restrictions remain unconfigured and are needed only for the optional OIDC pipeline.
- T17 template linting: PR #25; CI run 43619026006 passed. No CloudFormation/SAM templates exist; Terraform and JSON policy templates are validated in CI.
- T18 manual bootstrap plan: PR #32 adds the account-specific read-only renderer. The owner-provided target account is 924422830139, but STS identity, bucket suffix and live inventory still require read-only verification. The first dev local path is documented separately in PR #34.
- T37 implementation is complete: billing plan/apply policy and OIDC trust templates, isolated billing workflow path and six-environment documentation are validated by CI run 43620012088. PR #27.
- The T38 region guard and access-module region/KMS corrections are integrated into the release candidate. Exact release-candidate CI run 43689838548 passed on commit 6873a36f6eeb0a1e4cc5f32900303fb7c4714b1e.
- Consolidation PR #28 was merged into `solo/amit-monday` at merge commit `a43adea001009004597e19e1c04c14079205865a`. PR #33 is the separate combined AWS-readiness candidate; it is not merged. Do not merge it or promote to `main`/`develop` until the combined CI and remaining release gates pass.
- No AWS resources, OIDC provider, IAM roles, boundaries, state bucket or KMS keys have been created. No remote backend init, Terraform plan or apply has been run. PR #28 merge did not provision AWS resources.


## Current release-candidate integration

- PR #33 integrates the T16 helper fix (PR #30), T38 access/KMS correction (PR #31), T18 bootstrap renderer (PR #32), and new API route contract plus Moto-backed employee integration tests.
- The first combined run 43685191974 failed Ruff on the new integration test; that was corrected.
- The next combined run 43685265242 failed during collection because the first contract-test parser regex was malformed; the parser was replaced with a line-based parser and its route-key extraction corrected.
- A fresh green run on the final candidate head is mandatory. The earlier green PR runs do not replace it.
- The deployment workflow now fails closed if the OIDC role ARN, state-bucket prefix and STS caller account do not match the configured account ID.
- No AWS resources, remote backend initialization, Terraform plan or apply have been performed.
