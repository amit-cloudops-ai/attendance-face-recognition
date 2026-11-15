# Production acceptance and release evidence — 15 November 2026

> **Current production state supersedes the historical bootstrap snapshots below.** Those entries are retained as an audit trail, not as the current deployment status.

## Executive status

The production AWS environment is deployed in **us-east-1** and the kiosk and admin applications are live over HTTPS. The deployed release-candidate source has now been merged into `main` through PR #33. The production stack itself remains the already-running deployment; the Git merge did not apply Terraform or mutate AWS resources. The GitHub Actions production Terraform workflow has not been used for this deployment.

- Production CloudFront: https://d2l1fs6zsfo1ga.cloudfront.net
- Production kiosk: https://d2l1fs6zsfo1ga.cloudfront.net/kiosk/
- Production admin: https://d2l1fs6zsfo1ga.cloudfront.net/admin/
- Production API Gateway HTTP API: `pmd8cihlki`; endpoint `https://pmd8cihlki.execute-api.us-east-1.amazonaws.com`
- CloudFront distribution: `E3C89JGWXFNNGL` (reported Deployed and Enabled).
- AWS account: `924422830139`; region: `us-east-1`.
- Production DynamoDB tables: `attendance-prod-attendance`, `attendance-prod-audit`, `attendance-prod-config`, `attendance-prod-employees`, `attendance-prod-scan-results`.
- Rekognition collection: `attendance-prod-faces`.
- Production S3 buckets: `attendance-prod-924422830139-raw`, `attendance-prod-924422830139-reports`, `attendance-prod-924422830139-web`.
- KMS key: `arn:aws:kms:us-east-1:924422830139:key/c445d9fd-ec63-42d7-b6d2-2f03c80b62fa`.
- Alert topic: `arn:aws:sns:us-east-1:924422830139:attendance-prod-alerts`.
- Terraform remote state: `attendance-tf-state-924422830139-amit-2026-1115`, key `attendance/prod/terraform.tfstate`.

## Production acceptance results

The following functional results were explicitly confirmed by the operator on 15 November 2026. They are recorded as **operator-confirmed production acceptance**; attach screenshots/request IDs or sanitized test records where available before external submission.

| Criterion | Result | Evidence / qualification |
|---|---|---|
| F01 employee creation and face enrollment | PASS | Operator confirmed employee registration, photo upload and enrollment verification. Do not include employee names or biometric images in evidence. |
| F02 kiosk capture and face recognition | PASS | Operator confirmed successful kiosk recognition. Retain a sanitized request ID/result code if available. |
| F03–F04 clock-in, clock-out and debounce transitions | OPEN — not separately confirmed | Capture sanitized results for first scan, immediate duplicate/debounce scan and later clock-out. |
| F05–F06 unknown-face and inactive-employee handling | OPEN — not separately confirmed | Verify no attendance write for an unknown face and an inactive employee; use approved test identities only. |
| F07 daily absence report | PASS | Operator confirmed daily report acceptance. Attach the report period and sanitized S3 object key. |
| F08 weekly analytics | PASS | Operator confirmed weekly report acceptance. Attach the ISO week and sanitized S3 object key. |
| F09–F10 admin authentication, attendance and reports | PASS | Admin login and production admin workflow were confirmed working; daily and weekly reports confirmed. |
| N01 20-scan and browser acceptance | PASS — operator-confirmed | Operator confirmed 20-scan performance and browser acceptance. The numeric p95 result, 20 individual timings, browser/device/version matrix and evidence link have not yet been entered here. Do not claim a numeric p95 without the measurement output. |
| Production HTTPS and frontend delivery | PASS | CloudFront distribution reported Deployed/Enabled; live site returned HTTP 200 with security response headers in the deployment verification. |
| Cognito admin setup | PASS | Admin account was created, placed in the `admin` group and first-login password change completed; operator confirmed successful login. |
| Terraform production deployment | PASS | First apply: 1 imported, 200 added, 1 changed, 0 destroyed. Follow-up config apply: 0 added, 4 changed, 0 destroyed. No claim is made here that a clean-checkout rebuild has been completed. |

## Remaining production release gates

The following are **not yet evidenced in this status file**. Mark each PASS only after collecting the listed evidence.

| Gate | Required evidence | Current status |
|---|---|---|
| N02 raw biometric object deletion | After a production test, verify both `captures/` and `enroll/` prefixes contain no test objects within 10 minutes; record timestamps and object counts, never image contents | OPEN |
| N03 encryption and TLS | Capture live checks for all five DynamoDB tables, S3 default encryption, public-access blocks and TLS-only bucket policies; include KMS key IDs, not key material | PARTIAL — Terraform configuration and bucket controls were applied; complete live evidence bundle outstanding |
| N04 per-Lambda least privilege | Export deployed Lambda execution-role mappings and compare every attached policy/action/resource to the architecture IAM matrix; document the AWS-required `rekognition:DetectFaces` wildcard exception | OPEN |
| N05 private buckets / CloudFront-only web access | Record Block Public Access and bucket policy/OAC evidence for raw, reports and web buckets | PARTIAL — bucket security controls were applied; full live evidence bundle outstanding |
| N06 clean-checkout reproducibility | Rebuild a disposable dev environment from a clean checkout and record plan/apply/test results; do not destroy or rebuild production | OPEN |
| N07 release governance | Verify required branch protections and CI policy on `main`; confirm production release commit provenance | PARTIAL — source merged to `main` via PR #33; branch protection is currently reported disabled and must be configured/reviewed |
| N08 operational alert delivery | Verify SNS subscription confirmation and budget notification delivery; deliberately trigger one safe test alarm and record email receipt, alarm transition and reset | OPEN |
| N09 cost ceiling | The cost sheet estimates approximately USD 12–14/month for 100 employees x 2 scans/day and defines a USD 15 budget guardrail. Attach an AWS Pricing Calculator estimate and verify the deployed budget and notifications | PARTIAL — estimate exists; calculator and live notification evidence outstanding |
| N10 logging | Verify each Lambda log group has 30-day retention and inspect sanitized structured samples for absence of images, tokens and full face data | OPEN |
| N11 browser/device matrix | Operator reports acceptance passed; record exact Chrome desktop, Chrome Android and Safari iOS versions/devices and outcomes | PASS — operator-confirmed; detailed matrix evidence outstanding |
| Pilot | Whole team uses the production kiosk for at least one working day; record date/window, participant count (no names), issues and outcome | OPEN |
| Backup/restore | Complete a dev-only DynamoDB restore drill and report-object recovery check; do not restore over production | OPEN |
| Offboarding | Verify production employee deactivation, Rekognition face deletion, audit event and retained attendance history using an approved test employee | OPEN |
| DLQ recovery | Exercise a controlled dev DLQ recovery/redrive and verify idempotency and raw-image cleanup | OPEN |

## Final deliverables

- [x] Production kiosk and admin are deployed over HTTPS.
- [x] Operator-confirmed registration/enrollment, kiosk recognition, daily/weekly reports, 20-scan and browser acceptance.
- [ ] Numeric N01 p95 result and complete browser/device matrix attached.
- [ ] Security/retention/least-privilege evidence bundle attached.
- [ ] Alarm and budget notification evidence attached.
- [ ] One-working-day production pilot completed and recorded.
- [ ] Architecture diagram exported as PNG and technical design PDF generated.
- [ ] Demo video recorded from production using consenting participants and sanitized evidence.
- [ ] Cost sheet supplemented with an AWS Pricing Calculator estimate.
- [ ] README deployment instructions reconciled with the actual local Terraform production workflow.
- [x] Release candidate promoted to `main` through PR #33 after exact-head CI passed.
- [ ] Configure and verify `main` branch protection/rulesets; branch protection was reported disabled at promotion time.

## Evidence handling

Use employee test IDs only where needed. Do not commit employee names, email addresses, raw captures, face images, FaceIds, Cognito tokens, credentials, or unredacted request/response bodies. For screenshots, redact personal data and browser storage. Record each test with date/time (IST), environment, deployed commit, operator, result and a link to sanitized evidence.

---

# Project status — 15 November 2026

## Executive status

## Live AWS bootstrap progress — 15 November 2026

**Current phase: dev bootstrap resources created; IAM boundary and state bucket controls verified; final live policy-document comparison and local Terraform preparation remain.**

- Authenticated WSL AWS CLI profile: `default` (profiles present: `default`, `pdp`; no profile named `Amit-admin`). STS returned `arn:aws:iam::924422830139:user/Amit-admin`, account `924422830139`; canonical region `us-east-1`.
- The read-only preflight completed. GitHub OIDC provider and six GitHub plan/apply roles returned `NoSuchEntity`; no matching dev/prod execution boundary policies were returned; no account-prefixed Terraform state bucket was found. These are not blockers for the local first-dev deployment path.
- Existing API Gateway HTTP API `attendance-dev-http-api`, ID `7nii6lm2z2`, was verified in `us-east-1`. Its `Project=attendance`, `Environment=dev`, `Component=access` tags match. It has no stages, routes or integrations. The bootstrap script failed closed and created no duplicate.
- Account Lambda concurrency quota was previously verified as 10 with 10 unreserved executions and zero functions. The first dev `terraform.tfvars` must set all five `lambda_reserved_concurrency` values to `null` unless the quota changes; preserve the 10-unreserved-execution margin.
- The local inventory renderer succeeded using suffix `amit-2026-1115` and API ID `7nii6lm2z2`: 6 OIDC trust documents, 2 boundaries, 28 managed policy documents and 1 TLS-only bucket policy (37 total). Candidate state bucket: `attendance-tf-state-924422830139-amit-2026-1115`. Its initial `HeadBucket` returned 404; this is not a reservation and must be rechecked before creation.
- The rendered dev execution boundary passed IAM Access Analyzer `validate-policy` with `findings: []`. `iam list-policies --scope Local` returned no matching `attendance-dev-execution-boundary` policy. The generated state-bucket policy JSON parsed successfully and contains the TLS-only deny statement.
- Local preflight initially failed because WSL lacks a `python` command; the local copy was changed to `python3`, and the repository script is now corrected to use `python3`.
- Repository tracking: current head before this status update is `d810e4618a4a6567a12b2ff25f9a13d8677d925c` on `release/aws-readiness-candidate` (PR #33). Exact-head GitHub Actions CI run [43693544631](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43693544631), workflow run #1231, completed successfully on that exact commit. This supersedes the earlier CI caveat; subsequent documentation-only status updates still require their own exact-head CI evidence before any release promotion.
- **Dev IAM boundary and Terraform state bucket were created by the owner on 15 November 2026 after explicit approval.** The boundary ARN is `arn:aws:iam::924422830139:policy/attendance-dev-execution-boundary` (policy ID `ANPA5OO7E7A5XXNJSF5ZB`, version `v1`). The bucket is `attendance-tf-state-924422830139-amit-2026-1115`; read-only checks confirmed us-east-1, BucketOwnerEnforced, all four public-access blocks, versioning, AES256 default encryption and the TLS-only deny policy. The pasted policy-version output was truncated, so a complete live-vs-rendered policy document comparison remains. No remote backend initialization, Terraform plan or apply has run. The API already existed and was only inspected. GitHub OIDC setup remains optional and deferred.

**Bootstrap completed:** owner created the approved IAM boundary and state bucket. Bucket controls are verified read-only. Next: compare the complete live IAM boundary document with the rendered source, prepare ignored local backend/tfvars files, then request separate approval for remote backend initialization. Terraform plan and apply remain separately gated.


## AWS readiness follow-up — PR #34

**Status: IMPLEMENTATION MERGED INTO THE RELEASE CANDIDATE; POST-MERGE CI PASSED. A final status-only recheck is triggered by this update.**

- Release candidate PR #33 has base branch `solo/amit-monday` and head branch `release/aws-readiness-candidate`. Follow-up PR #34 has been squash-merged into the release branch as `ba31ad365a75f9539ef07282bce22992899b1b97`; PR #33 now contains the integrated fixes. No changes were made to `main`, `develop` or teammate PR #2.
- The follow-up corrects the current Ruff failure, fixes the employee API integration-test stubs, and fixes a real DynamoDB double-serialization defect in employee CRUD, attendance overrides, settings, face deletion and scan transactions.
- Dev/prod Terraform examples now use the correct callback path, complete required variables and the owner-provided dev account ID `924422830139`. CI checks the callback path, API ID shape, boundary ARN, dev account ID and frontend `config.json` exclusion.
- Lambda reserved concurrency is configurable per environment, retaining the current defaults (19 reserved executions) while allowing individual values to be `null` when account quota is insufficient.
- The runbook now contains a solo local dev bootstrap path with exact order, account/region, state-bucket controls, first/second apply, SNS/Cognito steps and troubleshooting. The OIDC/GitHub Actions pipeline (T16/T18) is optional for the first dev deployment.
- GitHub environment and branch-protection helpers/docs now use the agreed solo-owner model: zero mandatory external approvals and owner self-review allowed. No live GitHub environment settings have been changed or verified.

**CI evidence:** pre-merge exact-head workflow run [43689383499](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43689383499) passed both jobs on commit `8ca4031077c0653826ffceb9b1ef8df26cd648cc`. Python: **137 passed, zero skipped**; Ruff, region consistency, frontend/Terraform contract checks, JavaScript/CSP, syntax checks for every `scripts/*.sh`, workflow YAML, IAM/security policy validation, encrypted-plan and bootstrap-plan checks all passed. Terraform formatting passed, and backend-free init/validate passed for recognition, data, foundation, access, dev, prod and billing. Post-merge exact-head run [43689694957](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43689694957) passed both jobs on release head `9a49c05d579ed1c404e54c61bb7b119acef2c803`. Python: **137 passed in 13.77s, zero skipped**. Ruff, region/frontend contracts, JavaScript/CSP, all shell syntax checks, IAM/workflow/bootstrap checks, Terraform formatting and backend-free init/validate for all four modules and all three roots passed. That CI evidence applies to the stated historical commit only; the live-status and preflight-script commits recorded above require a fresh exact-head CI pass.

**Historical AWS boundary note:** the statements in this earlier readiness snapshot predate the live AWS bootstrap progress above. Current STS identity and the existing API have now been verified. IAM policy effectiveness beyond static Access Analyzer validation, live Cognito/Rekognition behavior and deployed browser/camera performance remain unverified.

**Next action:** owner review of PR #33. Do not merge PR #33 into `solo/amit-monday`, `develop` or `main` without separate approval. Once approved, the owner can begin the separately approved local dev bootstrap in `docs/DEPLOYMENT-RUNBOOK.md`.
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

**Important boundary:** this is not a claim that live AWS authorization, real Rekognition behavior, or physical-browser performance has been measured. The browser application passed repository-level JavaScript syntax/CSP checks and its UI state fixes have regression review; the deployed Cognito/API/camera browser matrix plus the 20-scan p95 latency acceptance test require the approved dev stack and remain Part 2 acceptance checks. At that earlier code-readiness checkpoint, no project infrastructure had been provisioned; the current live API discovery and bootstrap status are recorded at the top of this document. No remote backend initialization, Terraform plan or apply has run. AWS writes remain separately approval-gated.


The solo application and the T01–T38 deployment-security and region-guard task chain have been consolidated into `solo/amit-monday`. The T01–T15, T17 and T31–T37 implementation tasks are complete at the code/documentation level with historical CI evidence recorded in their task PRs. T16 and T18 are optional owner/admin gates for the later OIDC pipeline; they do not block the solo local first dev deployment.

The canonical region guard is established on `solo/amit-monday`: `config/deployment.json` is the single region manifest, Terraform roots and wrappers use it, Lambda clients use the Lambda-reserved `AWS_REGION`, and CI rejects conflicting region literals/endpoints. A follow-up review then found that `infra/modules/access` still duplicated the region in Cognito, JWT, CSP and S3 URL settings, and that DynamoDB KMS actions were incorrectly placed in an S3 bucket policy. PR #31 corrects both and passed its own CI run 43680111003 (118 Python tests and both jobs); those corrections are integrated into PR #33 and await combined CI.

**Historical code-readiness checkpoint:** no OIDC provider, IAM deployment roles, execution boundaries, state bucket, KMS key or budget resources had been created at that point. The existing dev API Gateway is now verified and recorded in the live bootstrap snapshot above. No remote Terraform backend initialization, Terraform plan or apply has been run. Every AWS mutation remains approval-gated.

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

In the current bootstrap sequence, no IAM roles, OIDC provider, permissions boundaries, state bucket or KMS keys have been created. The dev API Gateway listed above existed before this sequence and was only inspected; no duplicate was created. No remote backend initialization, Terraform plan or Terraform apply has been run. Any further AWS mutation requires an exact written plan and explicit owner approval before execution.
