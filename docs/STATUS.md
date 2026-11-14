# Project status — 14 November 2026

## Executive status

The solo implementation and Phase B deployment-security preparation have advanced substantially. T01–T15 and T17 are complete at the code/documentation/CI level. T16 and T18 are blocked on owner/repository-administrator actions. T37 (dedicated billing role policies) remains to be built.

**No AWS resources have been provisioned.** No OIDC provider, IAM roles, execution boundaries, state bucket, KMS key, or budget resources have been created. No remote Terraform backend initialization, Terraform plan or apply has been run. Every AWS mutation remains approval-gated.

Target region: us-east-1. Target account: the owner's existing AWS account; the exact 12-digit account ID has not been verified in this session.

## Source of truth and branch discipline

- Repository: amit-cloudops-ai/attendance-face-recognition.
- Governance: AGENTS.md, docs/TASKS.md and docs/CHATGPT_PROJECT_INSTRUCTIONS.md.
- Solo baseline: solo/amit-monday at 92e9bf53066145949bd430dd8dcbc0e7850df46d.
- Current work branch: ai/T18-manual-bootstrap-plan.
- Task work is isolated in ai/T## branches and promoted through stacked PRs. Do not commit to main/develop, alter teammate branches or merge teammate PRs.
- All task PRs are open and unmerged pending owner review. Teammate Part B PR #2 remains separate and untouched.

## Completed Phase B tasks

| Tasks | Scope | Evidence |
|---|---|---|
| T01–T05, T31 | Governance, Lambda async DLQ KMS, runtime IAM, region alignment and runtime boundaries | PRs #3–#8; CI runs 43611844694, 43612039939, 43612245039, 43612668343, 43612832683, 43613054015 |
| T06–T08 | Terraform provider IAM mapping for foundation, data/recognition and access modules | PRs #9–#11; CI runs 43613487881, 43614059591, 43615508377 |
| T09 | Dev read-only plan policies | PR #12; CI run 43615873597 |
| T32 | Environment-specific Scheduler groups and exact account/group trust | PR #13; CI run 43616332197 |
| T33 | Pin AWS provider 6.73.0/archive 2.8.1 and commit dev/prod lockfiles | PR #17; CI run 43617191177 |
| T34 | Move AWS Budgets into isolated infra/billing root and remove billing actions from normal roles | PR #14; CI run 43616787686 |
| T35–T36 | Exact CloudFront KMS distribution scope and DynamoDB customer-managed KMS ViaService authorization | PRs #15–#16; CI run 43617044959 |
| T10–T12 | Dev apply, prod plan and prod apply policy sets; split managed policies, exact resource/role/state scopes | PRs #18–#20; CI runs 43617809368, 43617967197, 43618294918 |
| T13 | Manual S3 state bucket bootstrap specification | PR #21; CI run 43618372200 |
| T14 | Operation-specific GitHub OIDC subjects, role selection and deployment workflow boundaries | PR #22; CI run 43618685801 |
| T15 | Encrypted plan artifact provenance, run-attempt binding and cleanup | PR #23; CI run 43618692691 |
| T17 | Infrastructure template lint audit and CI guard for future CloudFormation/SAM templates | PR #25; CI run 43619026006 passed |

The policy templates are not attached to AWS roles. IAM Access Analyzer and live AWS authorization tests have not been performed.

## Remaining blockers

### T16 — GitHub environment variables, secrets and protections

**Status: BLOCKED**

PR #24 contains the four-environment setup guide. The required names are dev-plan, dev-apply, prod-plan and prod-apply, with environment-scoped AWS_ROLE_ARN values, plan-only age recipients, apply-only private age identity secrets, branch restrictions and independent apply reviewers.

The GitHub connector cannot inspect or configure repository Actions environments. Branch protection API reads returned 403 Resource not accessible by integration. Actual environment existence, variable values, secret presence, reviewer assignments and branch restrictions remain unverified.

**Owner action:** configure the four environments and protection settings using docs/GITHUB-ENVIRONMENT-SETUP.md, then confirm or provide an authorized read-only verification path.

### T18 — exact manual AWS bootstrap plan

<badge color="warning">Blocked</badge>

PR #26 contains docs/MANUAL-AWS-BOOTSTRAP-PLAN.md. It enumerates the state bucket, OIDC provider, two runtime boundaries, four GitHub plan/apply roles, policy attachments, manual order, dev-first rollout, prod approval and rollback. CI run [43619095037](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43619095037), commit `f3aa1e85a6`: Python and Terraform jobs passed, including the bootstrap-plan inventory validator, all policy validators, lockfiles and environment roots.

The exact 12-digit account ID and globally unique state bucket suffix remain unknown. The bootstrap plan must be rendered with verified account values and presented to the owner before any write operation. T16 must also be resolved before role federation can be enabled.

**Owner action:** provide/confirm the account ID and approve the exact rendered resource inventory and permissions before bootstrap.

### T37 — dedicated billing deployment roles

The billing root and separate state key exist, but dedicated billing plan/apply policies and OIDC roles are not yet built. Normal dev/prod roles intentionally have no budgets:* or aws-portal:* permissions. Do not deploy infra/billing until T37 is complete.

## Deployment policy notes and residual scope

- Dev and prod plan roles are read-only for infrastructure. They can write/delete only their own S3 backend .tflock object.
- Dev/prod apply roles use separate policy sets, exact role ARNs for PassRole, exact runtime boundaries, environment-specific resources and isolated state keys.
- Billing is isolated from normal environment roles.
- DynamoDB customer-managed KMS permissions use the matching environment alias and kms:ViaService=dynamodb.us-east-1.amazonaws.com; CreateGrant also requires kms:GrantIsForAWSResource=true.
- CloudFront KMS decrypt is scoped to the exact distribution ARN.
- Scheduler trust requires the exact environment schedule-group ARN and source account.
- API Gateway v2 child-resource paths remain scoped to the /apis/* resource family until the generated API ID can be pinned. Several AWS create APIs require Resource="*" and use request-tag or function conditions where supported. These limitations are documented in infra/policies/README.md.
- The state bucket is SSE-S3 encrypted, versioned, BucketOwnerEnforced, blocked from public access and TLS-only. The bucket has not been created.

## Next sequence

1. Finish T17/T18 CI runs and open their PRs.
2. Obtain repository-admin confirmation for T16.
3. Obtain verified account ID and explicit bootstrap approval for T18.
4. Build T37 billing plan/apply roles.
5. Open T19 solo-only readiness PR to develop after all security/CI gates pass.
6. Only after separate approval, bootstrap state/OIDC/roles, run dev plan, present the exact plan and request apply approval.
7. Complete dev smoke/integration/privacy/performance/browser acceptance before a separately approved production plan/apply.

T20–T24 remain release approval gates, not completed deployment tasks. Phase B is not yet fully closed because T16/T18/T37 and the later deployment acceptance tasks remain outstanding.

## Safety boundary

No AWS resources, IAM roles, OIDC provider, permissions boundaries, state bucket or KMS keys have been created by this work. No remote backend initialization, Terraform plan or Terraform apply has been run. Any AWS mutation requires an exact written plan and separate explicit owner approval before execution.
