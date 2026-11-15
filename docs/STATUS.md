# Project status — 15 November 2026

## Executive status

## AWS readiness follow-up — PR #34

**Status: IMPLEMENTATION COMPLETE; FINAL CI GATE IN PROGRESS; NOT YET MERGED INTO THE RELEASE CANDIDATE.**

- Release candidate PR #33 currently has base branch `solo/amit-monday` and head branch `release/aws-readiness-candidate` (baseline head `008d78c`). Follow-up PR #34 is isolated on `fix/aws-readiness-bootstrap`, based on that release branch and targeting it. No changes were made to `main`, `develop` or teammate PR #2.
- The follow-up corrects the current Ruff failure, fixes the employee API integration-test stubs, and fixes a real DynamoDB double-serialization defect in employee CRUD, attendance overrides, settings, face deletion and scan transactions.
- Dev/prod Terraform examples now use the correct callback path, complete required variables and the owner-provided dev account ID `924422830139`. CI checks the callback path, API ID shape, boundary ARN, dev account ID and frontend `config.json` exclusion.
- Lambda reserved concurrency is configurable per environment, retaining the current defaults (19 reserved executions) while allowing individual values to be `null` when account quota is insufficient.
- The runbook now contains a solo local dev bootstrap path with exact order, account/region, state-bucket controls, first/second apply, SNS/Cognito steps and troubleshooting. The OIDC/GitHub Actions pipeline (T16/T18) is optional for the first dev deployment.
- GitHub environment and branch-protection helpers/docs now use the agreed solo-owner model: zero mandatory external approvals and owner self-review allowed. No live GitHub environment settings have been changed or verified.

**CI evidence:** exact-head workflow run [43689281495](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43689281495) passed both jobs on commit `4f433c85e2804571d40651a6825f2d5e2ef06924`. Python: **137 passed in 18.30s**, zero skipped; Ruff, region consistency, frontend/Terraform contract checks, JavaScript/CSP, syntax checks for every `scripts/*.sh`, workflow YAML, IAM/security policy validation, encrypted-plan and bootstrap-plan checks all passed. Terraform formatting passed, and backend-free init/validate passed for recognition, data, foundation, access, dev, prod and billing. This follow-up status-only commit will trigger another exact-head CI run; the new run is linked from PR #34.

**AWS boundary:** no AWS resource creation, IAM mutation, remote backend initialization, Terraform plan or apply has been performed. The owner-provided account ID `924422830139` has not been verified against STS in this session. IAM policy effectiveness, live Cognito/Rekognition behavior and deployed browser/camera performance remain unverified.

**Next action:** complete the exact-head CI run, then review and merge PR #34 into `release/aws-readiness-candidate`. Only after that candidate is green should the owner begin the separately approved local dev bootstrap in `docs/DEPLOYMENT-RUNBOOK.md`.
## Application correctness release gate — 15 November 2026

**Baseline status: PASS at code, unit-regression, static-analysis and Terraform-validation level on `solo/amit-monday`; this is not an AWS deployment-readiness pass.** No teammate branch or PR was merged.

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


The solo application and the T01–T38 deployment-security and region-guard task chain have been consolidated into `solo/amit-monday`. The T01–T15, T17 and T31–T37 implementation tasks are complete at the code/documentation level with historical CI evidence recorded in their task PRs. T16 and T18 are optional owner/admin gates for the later OIDC pipeline; they do not block the solo local first dev deployment.

The canonical region guard is established on `solo/amit-monday`: `config/deployment.json` is the single region manifest, Terraform roots and wrappers use it, Lambda clients use the Lambda-reserved `AWS_REGION`, and CI rejects conflicting region literals/endpoints. A follow-up review then found that `infra/modules/access` still duplicated the region in Cognito, JWT, CSP and S3 URL settings, and that DynamoDB KMS actions were incorrectly placed in an S3 bucket policy. PR #31 corrects both and passed its own CI run 43680111003 (118 Python tests and both jobs); those corrections are integrated into PR #33 and await combined CI.

**No AWS resources have been provisioned.** No OIDC provider, IAM roles, execution boundaries, state bucket, KMS key or budget resources have been created. No remote Terraform backend initialization, Terraform plan or apply has been run. Every AWS mutation remains approval-gated.

Target region: `us-east-1`, sourced from `config/deployment.json`. Target account ID provided by the owner: `924422830139`; the authenticated STS identity has not been verified in this session.

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

The required environments are `dev-plan`, `dev-apply`, `prod-plan`, `prod-apply`, `billing-plan` and `billing-apply`. Each must have the correct environment-scoped `AWS_ROLE_ARN`, account/bucket values, plan-only age recipient, apply-only private age identity secret and branch restriction. The solo-owner model has zero mandatory external approvals and allows owner self-review.

The GitHub connector cannot inspect or configure Actions environment secrets/protection settings, and branch-protection reads returned 403. Their actual existence and values remain unverified. The guarded helpers `scripts/configure_github_environments.sh` and `scripts/configure_branch_protection.sh` default to dry-run and require an explicit `--apply`. PR #34 aligns the helper and docs with the solo-owner model: no independent reviewer is required and self-review is allowed. Dry-run regression tests cover the six environments and zero-approval branch protection. Neither helper has been executed against the live repository settings. Environment AWS variables/secrets remain unset until approved bootstrap.

**Owner action for the optional pipeline:** run both helpers' dry-runs, inspect the exact branch restrictions and zero-approval solo-owner settings, then run their `--apply` modes from an authenticated repository-admin GitHub CLI session if/when the OIDC pipeline is enabled. Populate AWS role/account/bucket variables and age keys only after approved bootstrap. No reviewer username is required.

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

No read-only STS inventory has been run against the owner's AWS account in this release-readiness pass. The owner-provided account ID is `924422830139`; STS identity, state bucket, OIDC provider, runtime boundaries and six deployment roles remain unverified. Do not treat repository CI or the renderer's unit tests as evidence of live AWS account state.

A new renderer, `scripts/render_bootstrap_inventory.py`, now derives the account ID from the authenticated profile, checks a proposed state bucket name with read-only S3 HeadBucket, and writes the 6 OIDC trust policies, 2 runtime boundaries, 28 managed policy documents and TLS-only bucket policy to a local ignored directory. It fails closed on unresolved template variables, invalid JSON, managed-policy size overflow, unknown bucket availability and unexpected template counts. It performs no AWS writes, remote backend initialization or Terraform plan/apply. Its implementation and regression tests passed consolidated CI run [43680426827](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43680426827), commit `2188ac56088dfa40b3d4f52b095b23a7259780d0`: **125 Python tests** and both CI jobs, including Terraform formatting/init/validation.

**Owner action:** after the repository-side gate is ready and local checkout is intentionally connected, choose the globally unique bucket suffix, run `bash scripts/aws_preflight_readonly.sh` and the renderer using the approved profile, inspect the generated manifest and all 37 policy documents, then review and explicitly approve the exact resource and policy inventory. A successful HeadBucket 404 is only a point-in-time observation, not a reservation. Approval for bootstrap writes and approval for Terraform plan/apply remain separate.

## IAM design limitations requiring explicit review

- API Gateway v2 child-resource paths remain scoped to the `/apis/*` resource family until the generated API ID can be pinned.
- Some AWS create APIs require `Resource: "*"`; request-tag, function and service conditions are used where supported.
- Billing's `aws-portal:ModifyBilling` is account-level and cannot be scoped to an individual budget ARN. It is isolated to the billing-apply role and main branch; explicit owner approval is required, with no mandatory independent reviewer in the solo-owner phase; it must never be attached to dev/prod roles.
- Static template validation does not prove live AWS authorization. Rendered policies still require IAM Access Analyzer/review and a controlled dev deployment.

## Exact bootstrap inventory — not executed

| Category | Count | Names/scope |
|---|---:|---|
| S3 state bucket | 1 | `attendance-tf-state-<account-id>-<approved-suffix>` |
| IAM OIDC provider | 1 | `token.actions.githubusercontent.com` |
| Runtime permissions boundaries | 2 | `attendance-dev-execution-boundary`, `attendance-prod-execution-boundary` |
| GitHub plan/apply roles | 6 | dev-plan, dev-apply, prod-plan, prod-apply, billing-plan, billing-apply |
| Managed policy templates | 28 | 22 dev/prod plan/apply + 4 billing plan/apply + 2 temporary CloudFront bootstrap policies |
| GitHub environments | 6 | dev-plan, dev-apply, prod-plan, prod-apply, billing-plan, billing-apply |

The exact role trust documents, managed policy JSON, account IDs and bucket name must be rendered and reviewed before creation. Existing resources must be inspected first; no duplicate provider, bucket, role or policy should be created.

## Next sequence

1. For the first dev deployment, follow the solo local path in `docs/DEPLOYMENT-RUNBOOK.md`: verify STS identity, create the API/boundary/state bucket only after separate approval, write the ignored backend file, check Lambda quota, then review and approve the first plan/apply.
2. Add the CloudFront origin to `allowed_origins`, `callback_urls` and `logout_urls`, review and approve the required second apply, then confirm SNS and create Cognito admin/kiosk users.
3. Run the consent-gated E2E smoke test and complete dev integration/privacy/performance/browser acceptance.
4. For the optional OIDC pipeline only, complete T16/T18: configure the six GitHub environments and exact branch restrictions (zero required external approvals; owner self-review allowed), verify STS identity and live inventory, render all 37 policy documents and obtain separate owner approval for each AWS mutation.
5. Add pipeline roles/environments after local dev acceptance; promote to `develop` only through a reviewed PR. Keep teammate PR #2 separate throughout.

## Phase C operational readiness

- `docs/DEPLOYMENT-RUNBOOK.md` now records local reproducibility commands, read-only preflight, bootstrap approvals, exact plan/apply workflow and post-deployment acceptance.
- `docs/OPERATIONS-RUNBOOK.md` now documents alarm triage, DLQ handling, biometric offboarding, budget response, PITR/versioned-object restore and rollback.
- `docs/ARCHITECTURE.md` deployment steps were corrected to the current six-environment OIDC model; the former two-role/two-environment procedure was obsolete.
- T25 is still in progress because operational ownership and a live incident/alert drill are not verified.
- T26 is still in progress: dev/prod USD 15 monthly budgets with 80%/100% actual-cost notifications exist in Terraform, but email delivery and live cost behavior are untested.
- T27 is still in progress: five DynamoDB tables have PITR and the reports/state buckets are intended to be versioned, but no restore drill has been performed.
- T28 is in progress: CI now pins all GitHub Actions to full commit SHAs, pins the complete Python test dependency set, runs SHA-pinned pip-audit, enforces pinning, and Dependabot checks GitHub Actions/Python dependencies weekly. Container scanning and broader SBOM/provenance checks remain open.
- T29 remains in progress until local reproduction and a full cross-document consistency review are evidenced.
- T30 remains TODO until all release gates are reviewed.

T19–T24 and the live portions of T25–T30 remain release, deployment and operational acceptance work. The first local dev deployment is no longer blocked on OIDC/GitHub environment setup, but it still requires owner-approved AWS bootstrap writes, reviewed Terraform plans and live acceptance.

## Safety boundary

No AWS resources, IAM roles, OIDC provider, permissions boundaries, state bucket or KMS keys have been created by this work. No remote backend initialization, Terraform plan or Terraform apply has been run. Any AWS mutation requires an exact written plan and separate explicit owner approval before execution.
