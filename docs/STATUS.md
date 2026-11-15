# Project status — 14 November 2026

## Executive status

## Application correctness release gate — 15 November 2026

**Status: PASS at code, unit-regression, static-analysis and Terraform-validation level.** Source of truth remains `solo/amit-monday`; no teammate branch or PR was merged.

The application audit and fixes completed on this branch include:

- Weekly metrics now exclude attendance records on weekends and holidays from every numerator.
- Employee create/deactivate, attendance override, settings updates, and face-template offboarding commit the relevant DynamoDB state change and audit record transactionally.
- Settings updates use a strongly consistent read and monotonically increasing version check; overrides reject stale concurrent writes. Recognition and daily finalization increment the attendance row version on every mutation, so same-second concurrent writes cannot bypass optimistic locking. Daily missing-clock-out finalization is idempotent.
- Recognition attendance writes include an employee-active condition in the same transaction, closing the deactivation/scan race.
- A late-arriving clock-out clears the stale `missing_clock_out` flag, including after the daily job has finalized the date.
- Exhausted scan failures reconcile the strongly consistent attendance base table if the date-index GSI has not caught up.
- Admin offboarding can be retried after partial failure without exposing FaceIds; enrollment capacity and attendance pagination now track current UI state.
- Regression coverage was added for transaction failures, concurrency, deactivation races, eventual GSI consistency, offboarding retries, stale flags and enrollment capacity.

**Final consolidated CI evidence:** run [43679052434](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43679052434), commit `0aa6aa527b57347d60b68b6d66d54734410f21f3`. Both jobs passed: **116 Python tests**, Ruff, region consistency, browser JavaScript syntax/CSP, shell syntax, workflow YAML, IAM/security template validations, Terraform formatting, and Terraform init/validate for recognition, data, foundation, access, dev, prod and billing.

**Important boundary:** this is not a claim that live AWS authorization, real Rekognition behavior, or physical-browser performance has been measured. The browser application passed repository-level JavaScript syntax/CSP checks and its UI state fixes have regression review; the deployed Cognito/API/camera browser matrix plus the 20-scan p95 latency acceptance test require the approved dev stack and remain Part 2 acceptance checks. No AWS resources have been provisioned, no remote backend initialized, and no Terraform plan or apply run. AWS writes remain separately approval-gated.


The solo application and the T01–T38 deployment-security and region-guard task chain have been consolidated into `solo/amit-monday`. The T01–T15, T17 and T31–T37 implementation tasks are complete at the code/documentation level with historical CI evidence recorded in their task PRs. T16 and T18 remain blocked on repository-administrator and owner-controlled AWS-account information/actions.

The region-consistency implementation is complete on this branch: `config/deployment.json` is the canonical AWS region manifest; Terraform provider roots read it; the deployment workflow and local Terraform wrapper export it for the S3 backend; Lambda clients use the Lambda-reserved `AWS_REGION`; contracts and examples are aligned; CI rejects any noncanonical AWS region literal, regional ARN or regional endpoint. The full consolidated CI run 43622495235 passed on commit `65f82c6597bd9705c334b5cb2f6b3bfc528c946d` (27 Python/security steps and 21 Terraform formatting/validation steps).

**No AWS resources have been provisioned.** No OIDC provider, IAM roles, execution boundaries, state bucket, KMS key or budget resources have been created. No remote Terraform backend initialization, Terraform plan or apply has been run. Every AWS mutation remains approval-gated.

Target region: `us-east-1`, sourced from `config/deployment.json`. Target account: the owner's existing AWS account; the exact 12-digit account ID has not been verified in this session.

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

The task PR CI runs are historical evidence for their respective commits. The final consolidated CI passed on head `8bae76d`: Python/security 27/27 and Terraform 21/21. The merge into `solo/amit-monday` has also triggered a fresh post-merge CI run; its final result is being checked. IAM templates have not been attached to AWS roles. IAM Access Analyzer and live AWS authorization tests have not been performed.

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

The GitHub connector cannot inspect or configure Actions environment secrets/protection settings, and branch-protection reads returned 403. Their actual existence and values remain unverified. Two guarded GitHub CLI helpers exist: `scripts/configure_github_environments.sh` (six exact environments, allowed branches and independent reviewers) and `scripts/configure_branch_protection.sh` (PR reviews, CI checks and protected branches). Both default to dry-run and require an explicit `--apply`; neither has been executed. A pre-deployment review found and fixed escaped Bash variable expansions in the environment helper; a new automated dry-run test verifies that all six environment names and their branch restrictions are emitted. Environment AWS variables/secrets remain intentionally unset until the AWS account inventory and bootstrap create the roles, bucket and boundaries.

**Owner action:** provide the GitHub username of an independent reviewer, run both helpers' dry-runs, inspect the output, then run their `--apply` modes from an authenticated repository-admin GitHub CLI session. Populate AWS role/account/bucket variables and age keys only after approved bootstrap. Provide confirmation or an authorized read-only verification path. The helper correction and regression test passed consolidated CI run [43679609707](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43679609707), commit `b9850db6f78a2605e351c0f3febe91268976c661` (117 Python tests; both CI jobs passed).

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

1. Complete T16: configure and verify the six GitHub environments, their branch restrictions, environment variables/secrets and independent apply reviewers. The current GitHub connector cannot configure or verify these settings; repository-admin action is required.
2. Complete T18 read-only verification: run `bash scripts/aws_preflight_readonly.sh` with an approved read-only AWS profile; verify the account ID, OIDC provider, state bucket, two boundaries, six roles and policy documents; choose a globally unique state bucket suffix.
3. Render the exact account-specific bucket policy, OIDC trust policies, boundaries and all 26 managed policy documents. Perform static and AWS-side policy validation; present the exact resource/action inventory and obtain explicit approval before any AWS write.
4. After separate bootstrap approval, create only the approved missing state bucket/OIDC provider/boundaries/roles/policies; verify all settings with read-only calls.
5. Initialize the dev backend only after its separate approval, run the dev plan, present the complete plan and obtain explicit apply approval. Apply only the reviewed saved plan.
6. Complete dev integration/privacy/performance/browser acceptance before a separately approved production plan/apply.
7. Promote the approved solo release to `develop` only through a reviewed PR. Keep teammate PR #2 separate throughout.

T19–T24 and T25–T30 remain release, deployment and operational acceptance work. Phase B is not fully closed until the repository-admin and owner-controlled blockers are resolved.

## Safety boundary

No AWS resources, IAM roles, OIDC provider, permissions boundaries, state bucket or KMS keys have been created by this work. No remote backend initialization, Terraform plan or Terraform apply has been run. Any AWS mutation requires an exact written plan and separate explicit owner approval before execution.
