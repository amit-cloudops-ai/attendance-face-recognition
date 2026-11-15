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
| T16 | Reconcile GitHub environment variables, secrets and protection rules | BLOCKED | Exact names/scopes documented; actual environment secrets, reviewers and branch restrictions must be configured and verified by repository admin |
| T17 | Add or verify infrastructure template linting in CI | DONE | No CloudFormation/SAM source exists; Terraform and JSON policy templates are validated; CI fails if unlinted CloudFormation/SAM is introduced |
| T18 | Produce exact manual bootstrap change plan | BLOCKED | Bootstrap plan documented; exact AWS account ID, globally unique state bucket suffix and owner approval are required before finalizing mutation inventory |
| T19 | Open solo-only deployment-readiness PR to develop | TODO | T16/T18 and required security/CI gates resolved; PR contains only approved solo implementation; teammate PRs remain separate |
| T20 | Review and obtain approval for dev Terraform plan | TODO | State bucket and OIDC bootstrap separately approved; full dev plan shown and explicitly approved before apply |
| T21 | Deploy and validate dev environment | TODO | Explicit apply approval; smoke/integration checks, Cognito/CORS/CloudFront validation and rollback readiness evidenced |
| T22 | Complete privacy, deletion, latency and browser acceptance | TODO | Raw-image deletion evidence, consent checks, 20-scan p95, Chrome/Android and Safari/iOS checks |
| T23 | Prepare production release review | TODO | Dev acceptance complete, security/cost evidence, rollback plan and separate production approval |
| T24 | Deploy production after explicit approval | TODO | Exact production plan reviewed and approved; production apply and post-deploy checks evidenced |

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

| T38 | Establish canonical AWS region manifest and CI drift prevention | DONE | Access-module endpoints, Cognito issuer, KMS ViaService and S3 upload URL consume the root's canonical region input; DynamoDB KMS actions exist only in the KMS key policy; regression checks enforce both; follow-up CI run 43679979477 passed (118 Python tests, both jobs successful) or legacy region reference |

## Phase C — release and operations

| ID | Task | Status | Acceptance criteria |
|---|---|---|---|
| T25 | Establish operational runbooks and incident response | TODO | Alert ownership, severity, triage, recovery, escalation and rollback documented |
| T26 | Verify budget alarms and cost guardrails | TODO | Budgets, thresholds, notification paths and expected monthly cost documented and tested |
| T27 | Verify backup, restore and disaster recovery procedures | TODO | Recovery objectives, backup configuration and restore test evidence recorded |
| T28 | Add dependency and container/code supply-chain checks | TODO | Dependency scanning and pinned/reviewed CI actions with actionable failure policy |
| T29 | Complete end-to-end release documentation | TODO | Architecture, deployment, configuration, operator and user documentation agree with implementation |
| T30 | Conduct final production readiness review | TODO | All release acceptance evidence reviewed; remaining risks accepted by owner |

## Task execution notes

- T01–T09 and T31–T36 are complete with CI evidence recorded in docs/STATUS.md and the corresponding PRs.
- T10 dev apply policies: PR #18; CI run 43617809368 passed.
- T11 prod plan policies: PR #19; CI run 43617967197 passed.
- T12 prod apply policies: PR #20; CI run 43618294918 passed.
- T13 state bucket bootstrap specification: PR #21; CI run 43618372200 passed.
- T14 GitHub OIDC hardening: PR #22; CI run 43618685801 passed.
- T15 encrypted plan artifact lifecycle: PR #23; CI run 43618692691 passed.
- T16 GitHub environment setup: PR #24; documentation is ready, but actual GitHub environment settings cannot be inspected or configured by the current connector. Repository-admin action is required.
- T17 template linting: PR #25; CI run 43619026006 passed. No CloudFormation/SAM templates exist; Terraform and JSON policy templates are validated in CI.
- T18 manual bootstrap plan: PR #26; plan is documented and CI run 43619095037 passed. Exact account ID, globally unique bucket suffix and owner approval remain required.
- T37 implementation is complete: billing plan/apply policy and OIDC trust templates, isolated billing workflow path and six-environment documentation are validated by CI run 43620012088. PR #27.
- T38 is complete and merged into `solo/amit-monday`: canonical region manifest, Terraform provider loading, backend wrapper/workflow export, contract/example updates, Moto fixture alignment and repository-wide region drift guard. Consolidated CI run 43622637663 passed all 27 Python/security steps and all 21 Terraform formatting/validation steps on head commit `8bae76d788074e9c0d47d886fe355fddbcff709f`.
- Consolidation PR #28 was merged into `solo/amit-monday` at merge commit `a43adea001009004597e19e1c04c14079205865a`. It contains the T01–T38 security and region-guard work. The individual task PRs remain historical and may remain open; do not merge teammate PRs or promote to `main`/`develop` without the required T16/T18 gates and owner direction.
- No AWS resources, OIDC provider, IAM roles, boundaries, state bucket or KMS keys have been created. No remote backend init, Terraform plan or apply has been run. PR #28 merge did not provision AWS resources.
