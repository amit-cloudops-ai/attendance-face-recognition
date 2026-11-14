# Task board

This board is the execution queue for the attendance face-recognition project. Keep task IDs stable. Work on one task at a time, use a dedicated `ai/T##-short-description` branch, and update this board and `docs/STATUS.md` before moving to another task.

Status values: `TODO`, `IN_PROGRESS`, `BLOCKED`, `DONE`. A task is not `DONE` until its acceptance criteria are verified and evidence is recorded.

## Repository governance

| ID | Task | Status | Acceptance criteria |
|---|---|---|---|
| T01 | Restore repository working rules, task board, and ChatGPT project instructions | DONE | Governance files exist, agree with owner-approved workflow, status is accurate, CI passes |

## Phase B — deployment security and readiness

| ID | Task | Status | Acceptance criteria |
|---|---|---|---|
| T02 | Validate KMS key policy for Lambda asynchronous failure destinations | DONE | Confirm AWS service-principal model, source ARN/account conditions, encryption context and exact DLQ ARNs against AWS docs; update policy only with evidence |
| T03 | Reconcile recognition Lambda runtime IAM permissions | DONE | Every SDK call mapped to exact action/resource; Rekognition, S3, DynamoDB, SQS, KMS and logs checked |
| T04 | Reconcile data Lambda runtime IAM permissions | DONE | Every SDK call mapped to exact action/resource; no unused permissions or unjustified KMS grants |
| T05 | Finalize dev/prod execution-role permissions boundaries | DONE | Two environment-specific allow-list boundary templates cap runtime permissions; no IAM/STS self-management, PassRole or provisioning actions; CI validates rendered policy envelope, conditions and size. Boundary templates are not created or attached in AWS. |
| T06 | Verify Terraform provider IAM actions for foundation module | DONE | Create/read/update/delete/tag operations mapped to exact IAM actions and resource scopes |
| T07 | Verify Terraform provider IAM actions for data and recognition modules | DONE | All provider operations mapped, including Lambda, IAM, DynamoDB, Scheduler, SQS, Rekognition and CloudWatch |
| T08 | Verify Terraform provider IAM actions for access module | DONE | Cognito, API Gateway v2, CloudFront, S3 and Lambda permission operations mapped |
| T09 | Build dev plan-role policy | DONE | Read-only planning permissions, dev-only state/lock access, no resource mutation |
| T10 | Build dev apply-role policy | IN_PROGRESS | Exact dev resource permissions, boundary enforcement and exact iam:PassRole scopes |
| T11 | Build prod plan-role policy | IN_PROGRESS | Read-only planning permissions, prod-only state/lock access, no resource mutation |
| T12 | Build prod apply-role policy | IN_PROGRESS | Exact prod resource permissions, boundary enforcement and exact iam:PassRole scopes |
| T13 | Review Terraform state bucket bootstrap specification | IN_PROGRESS | Versioning, public access block, SSE-S3, ownership controls, TLS-only bucket policy, state/lock object scope documented |
| T14 | Audit GitHub OIDC trust and deployment workflow permissions | IN_PROGRESS | Exact audience/subjects, branch/environment gates, token permissions, role separation and no static credentials |
| T15 | Audit encrypted Terraform plan artifact lifecycle | TODO | Plan provenance, exact commit/environment binding, encryption, one-day retention, artifact access and identity handling verified |
| T16 | Reconcile GitHub environment variables, secrets and protection rules | TODO | Required names and scopes documented; private age identity is a protected secret; reviewer/branch restrictions verified |
| T17 | Add or verify infrastructure template linting in CI | TODO | Determine whether CloudFormation templates exist; run cfn-lint only on actual templates and fail CI on violations |
| T18 | Produce exact manual bootstrap change plan | TODO | Enumerated resources, names, regions, policies, costs and rollback; present to owner before any AWS mutation |
| T19 | Open solo-only deployment-readiness PR to develop | TODO | All preceding security/CI gates pass; PR contains only approved solo implementation; teammate PRs remain separate |
| T20 | Review and obtain approval for dev Terraform plan | TODO | Backend bootstrap separately approved; full dev plan shown and explicitly approved before apply |
| T21 | Deploy and validate dev environment | TODO | Explicit apply approval, smoke/integration checks, Cognito/CORS/CloudFront validation, evidence recorded |
| T22 | Complete privacy, deletion, latency and browser acceptance | TODO | Raw-image deletion evidence, consent checks, 20-scan p95, Chrome/Android and Safari/iOS checks |
| T23 | Prepare production release review | TODO | Dev acceptance complete, security/cost evidence, rollback plan and separate production approval |
| T24 | Deploy production after explicit approval | TODO | Exact production plan reviewed and approved; production apply and post-deploy checks evidenced |

## Phase B cross-cutting blocker

| ID | Task | Status | Acceptance criteria |
|---|---|---|---|
| T31 | Align all Lambda runtime AWS SDK clients with the us-east-1 deployment region | DONE | Every explicit region override/default is aligned to the deployed region; no runtime client targets ap-south-1; CI and unit tests pass |

## Phase B cross-cutting hardening

| ID | Task | Status | Acceptance criteria |
|---|---|---|---|
| T32 | Constrain EventBridge Scheduler execution-role trust policy to source account and environment schedule-group ARN | DONE | Dev/prod use separate named schedule groups; trust requires the exact environment schedule-group ARN and owning account. AWS requires a schedule-group ARN, not an individual schedule ARN.
| T33 | Pin Terraform AWS provider and commit environment lockfiles | IN_PROGRESS | Exact provider version tested in CI is pinned; dev/prod lockfiles committed with runner platform checks |
| T34 | Isolate AWS Budgets from normal deployment roles | IN_PROGRESS | Budget resources move to a separate root and dedicated role; normal apply roles do not need aws-portal:ModifyBilling |
| T35 | Scope CloudFront KMS key policy to the exact distribution | DONE | KMS key policy authorizes only the project CloudFront distribution ARN; no distribution wildcard remains |
| T36 | Add DynamoDB customer-managed-key service access and deployment KMS permissions | DONE | KMS key policy supports DynamoDB customer-managed-key ViaService authorization; dev/prod apply policies grant required KMS operations only via DynamoDB and only for the matching key |

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

- T01 is complete: governance files restored and branch CI passed on commits `be5b4e94c41f760d6bd750bf283f76dec222b2ef` and `aa293276cc8d35961ac75b6cd70ccd681105ae0f`.
- T07 is complete: provider v6.73.0 operations for DynamoDB, CloudWatch, IAM, Lambda, Scheduler, SQS, Rekognition and S3 notifications are mapped in `docs/security/DATA-RECOGNITION-PROVIDER-IAM.md`. CI run [43614059591](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43614059591) passed Python and Terraform jobs.
- T08 is complete (PR #11); T09 is complete (PR #12); T32 is complete (PR #13). T33 is complete (PR #17). T34 is complete (PR #14); T35 and T36 are complete (PRs #15–#16). T10 is now active: finish and validate the dev apply-role policy set.
- Do not reorder or mark tasks complete without evidence.
- The task board is a plan, not proof that implementation or AWS validation has occurred.
