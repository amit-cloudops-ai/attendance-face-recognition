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
| T04 | Reconcile data Lambda runtime IAM permissions | TODO | Every SDK call mapped to exact action/resource; no unused permissions or unjustified KMS grants |
| T05 | Finalize dev/prod execution-role permissions boundaries | TODO | Two environment-specific boundary documents, least-privilege union, explicit deny/guardrails, no self-management path |
| T06 | Verify Terraform provider IAM actions for foundation module | TODO | Create/read/update/delete/tag operations mapped to exact IAM actions and resource scopes |
| T07 | Verify Terraform provider IAM actions for data and recognition modules | TODO | All provider operations mapped, including Lambda, IAM, DynamoDB, Scheduler, SQS, Rekognition and CloudWatch |
| T08 | Verify Terraform provider IAM actions for access module | TODO | Cognito, API Gateway v2, CloudFront, S3 and Lambda permission operations mapped |
| T09 | Build dev plan-role policy | TODO | Read-only planning permissions, dev-only state/lock access, no resource mutation |
| T10 | Build dev apply-role policy | TODO | Exact dev resource permissions, boundary enforcement and exact iam:PassRole scopes |
| T11 | Build prod plan-role policy | TODO | Read-only planning permissions, prod-only state/lock access, no resource mutation |
| T12 | Build prod apply-role policy | TODO | Exact prod resource permissions, boundary enforcement and exact iam:PassRole scopes |
| T13 | Review Terraform state bucket bootstrap specification | TODO | Versioning, public access block, SSE-S3, ownership controls, TLS-only bucket policy, state/lock object scope documented |
| T14 | Audit GitHub OIDC trust and deployment workflow permissions | TODO | Exact audience/subjects, branch/environment gates, token permissions, role separation and no static credentials |
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
- T02 is the next active task: validate the KMS key policy for Lambda asynchronous failure destinations.
- Do not reorder or mark tasks complete without evidence.
- The task board is a plan, not proof that implementation or AWS validation has occurred.
