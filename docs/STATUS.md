# Project Status (source of truth for "what is built")

**Update this file at the end of every work session (human or AI).** Newest entries at the top of the log.

## Current execution decision (14 Nov 2026)
- **Solo-first delivery is the governing plan.** `solo/amit-monday` is the working implementation and source of truth for completing the entire application independently. Do not merge teammate branches or PRs into this branch. Team work remains isolated on its own branches and is optional; consider it only after inspecting the actual contribution, tests, contract compliance and maintainability, and only if it is genuinely useful.
- Finish and validate Phase A reliability/security work on the solo branch before preparing the AWS development release candidate. Do not deploy or provision AWS resources until the reviewed dev Terraform plan is explicitly approved.
- `main`, `develop`, and teammate branches remain untouched by solo implementation work.

## Phase A reliability hardening (solo implementation validated; AWS validation outstanding)
- Recognition now leaves retryable failures pending and retains raw images. Terminal results are persisted before image deletion. The original presign `created_at` is used as the scan timestamp.
- Shared `record_scan` accepts a UUID request ID and stores the exact outcome in the attendance row's `scan_events` map alongside the conditional attendance transition. Replays return the original outcome rather than creating a second clock action.
- Enrollment now uses a 45-second per-employee lease, a request-specific employee marker, and request-scoped Rekognition FaceId recovery. A retry after employee persistence can finish result persistence without incrementing photo_count or appending the FaceId again. Rekognition ExternalImageId now includes employee_id plus request_id, allowing exact recovery if indexing succeeded but employee persistence did not.
- Added an internal `failure` Lambda to consume async failure destination messages. It repairs scan results when attendance already committed, repairs enrollment results when the employee marker exists, removes exact request-scoped orphan FaceIds when enrollment did not commit, and only marks truly uncommitted requests as `error`. A processor DLQ receives poison recovery messages after five receives and has its own alarm.
- Offboarding face deletion now requires the employee to be inactive, verifies all Rekognition FaceIds are deleted or already absent, writes a deterministic audit record, and updates the employee record retry-safely. The employee API hides internal enrollment and offboarding markers.
- **Validated by GitHub Actions on the solo branch:** 91 Python tests passed; Ruff, Node syntax/CSP, Bash syntax, GitHub Actions YAML, Terraform formatting, and Terraform validation for recognition/data/foundation/access modules plus dev/prod roots all passed. The latest code validation is commit `246b847`; later changes were documentation-only. This does not substitute for deployed AWS integration testing.

## Milestones
| Day | Date | Goal | Done? |
|---|---|---|---|
| 1 | Wed 11 Nov | Docs frozen, repo + branch rules, bootstrap + foundation on dev, team onboarded, stubs of all Lambdas deployed | [ ] |
| 2 | Thu 12 Nov | Walking skeleton end-to-end on dev (kiosk to stubbed recognize to table to admin list) | [ ] |
| 3 | Fri 13 Nov | Real implementations merged to `develop`; contract tests green; 6 pm integration checkpoint | [ ] |
| 4 | Sat 14 Nov | Hardening, prod deploy, pilot starts, docs complete | [ ] |
| 5 | Sun 15 Nov | **Code freeze 12:00**, final tests, video, PDF, submission pack ready | [ ] |
| - | Mon 16 Nov | Submission buffer | [ ] |

## Module status
| Module | Owner | Status (not started / in progress / on dev / on prod) | Tests | Notes |
|---|---|---|---|---|
| bootstrap + foundation | Amit (solo) | in progress | Terraform fmt + validate green for dev and prod roots | Foundation module defines KMS, private encrypted buckets, raw-image lifecycle/CORS, common layer, SNS alerts and USD 15 budget; dev/prod roots wired. Bootstrap and apply not performed |
| shared layer (tz, config, responses, auth) | Amit (solo) | in progress | Shared attendance tests included in 57 passing; Ruff passed | IST helpers, cached config, API responses, Cognito group/username helpers and conditional record_scan implementation on solo/amit-monday |
| Part A: recognition | Amit (solo) | implemented locally; AWS validation pending | Included in 91 passing Python tests; recognition Terraform validate green | Seven handlers including failure recovery; request-level scan idempotency; request-scoped Rekognition IDs; retry-safe enrollment; encrypted SQS recovery and processor DLQ; safe audited offboarding |
| Part B: data + automation | Amit (solo) | in progress | 33 data API/job/admin tests; Terraform validate green | Employee CRUD, attendance query, daily/weekly jobs, reports, reason-required attendance overrides and validated settings API; five encrypted/PITR tables, schedules, IAM and alarms |
| shared record_scan | Amit (solo) | implemented locally; AWS validation pending | Request-id idempotency and legacy-row coverage included in 91 passing Python tests | Implemented conditional clock-in, debounce, clock-out, IST date, absent-row promotion and out-of-order event protection on solo/amit-monday |
| Part C: access + web | Amit (solo) | in progress | Node module syntax + HTML CSP hygiene green; access/dev/prod Terraform validate green; browser testing pending | Cognito groups and PKCE public client, JWT HTTP API routes, CloudFront private web origin/security headers, generated config.json, kiosk camera/scan flow, admin employee/enrollment/attendance/report/override/settings UI |
| CI/CD | Amit (solo) | CI green; manual OIDC deploy workflow added but not configured/run | 91 Python tests; Ruff; Node syntax + CSP; Bash syntax; workflow YAML; Terraform fmt + validate for recognition, data, foundation, access, dev and prod roots | GitHub variables/environments and AWS OIDC roles still need bootstrap; no manual deployment workflow run or AWS apply |

## Acceptance evidence
Paste links/screenshots per SPEC ID (F01-F13, N01-N11) as they pass.

## Confirmed decisions
- Solo-first ownership: complete the full application on `solo/amit-monday`; teammate contributions remain separate and are evaluated only after the solo implementation is complete. No teammate code is a dependency for finishing the solo project.
- UI direction: A (clean light enterprise admin + high-contrast kiosk), confirmed 11 Nov.
- Solo infrastructure implementation follows ARCHITECTURE.md and TEAM_BRIEF: Terraform modules, not SAM. The Part B/Part C guide references are aligned to Terraform modules. The external API routes and response envelopes remain unchanged; approved additive internal retry metadata is documented below.

## Known issues
- Part A is not complete: AWS deployment/integration, real Rekognition accuracy, IAM verification in-account, and end-to-end kiosk validation remain. The module has only been initialized and validated locally in CI; no apply has run.
- AWS integration, biometric accuracy, in-account IAM, raw-image deletion behaviour and end-to-end latency are not verified; no AWS resources have been provisioned.
- Part B override and settings endpoints are implemented and audit-logged. Part C has not been browser-tested against a deployed stack. Bootstrap state bucket/OIDC role setup and GitHub environment/variable configuration remain; the manual deploy workflow is committed but has not been run.
- `scripts/e2e_smoke.sh` is committed and syntax-checked, but not executed because no dev stack or consented test photos are available in this work session.
- Team PR #2 by Sushmitha (`b/data-automation` → `develop`) is open and separate from the solo branch. Earlier PR checks failed Ruff and Terraform formatting; the latest head is being rechecked. Do not merge until CI is green and the PR is reviewed against the frozen contracts and current Terraform module boundaries. No Part C teammate branch/PR is visible yet.
- After the first approved deployment, add the exact CloudFront site origin to the dev `allowed_origins`, `callback_urls` and `logout_urls` values and apply again; this enables production-domain S3 presigned POST CORS and Cognito redirects without introducing a Terraform dependency cycle.
- Part B and Part C contributor guides are aligned to the Terraform modules in ARCHITECTURE.md and TEAM_BRIEF; frozen API/data contracts were not changed.

## Decisions made after freeze
- 14 Nov 2026 — Approved additive internal retry metadata (no external API route/response change): `attendance.scan_events[request_id]` makes attendance writes idempotent; employee `enrollment_{request_id}` and 45-second lease attributes make enrollment recoverable; `last_faces_delete_audit_id` makes offboarding audit/update retries safe. New Rekognition `ExternalImageId` format is `employee_id#request_id`; recognition remains backward-compatible with legacy `employee_id` values. Reason: prevent duplicate attendance transitions, duplicate face indexing, orphan biometric templates and incomplete offboarding after transient failures.

## Session log
- 11 Nov: repo scaffold, SPEC, contracts, architecture, part guides created.
- 14 Nov: Amit solo T10 implementation added: attendance_common timezone/config/response helpers, record_scan, and focused moto-backed unit tests. GitHub Actions passed: Ruff, pytest (16 passed), and terraform fmt. No AWS resources provisioned.
- 14 Nov: Amit solo T11 batch added Cognito group helpers plus presign, result-polling and S3-triggered recognize handlers. Added mocked-AWS coverage for authorization, pre-signed POST, result contract, recognition outcomes, duplicate delivery and image cleanup. GitHub Actions passed: Ruff, pytest (28 passed), and terraform fmt. No AWS resources provisioned.
- 14 Nov: Part A enrollment batch added admin enrollment URL creation, S3-triggered face indexing with quality/duplicate/limit checks, and audited face-template deletion. GitHub Actions passed: Ruff, pytest (38 passed), and terraform fmt. AWS integration and real biometric accuracy remain unverified; no AWS resources provisioned.
- 14 Nov: Recognition Terraform module added six Lambda packages, least-privilege per-function roles, Rekognition collection, S3 prefix notifications, encrypted SQS failure destinations, log groups and CloudWatch alarms. GitHub Actions passed Python tests (38), Ruff, Terraform fmt and Terraform validate. No Terraform apply or AWS resource provisioning performed.
- 14 Nov: Part B core APIs and jobs added employee CRUD with consent/audit, indexed attendance queries with cursor pagination, idempotent daily absent finalization and missing-clock-out flags, weekly ISO analytics, and report JSON/CSV retrieval. Added the Terraform data module for five encrypted/PITR DynamoDB tables, five Lambdas, Asia/Kolkata schedules, least-privilege IAM and CloudWatch alarms. GitHub Actions passed 57 Python tests, Ruff, Terraform fmt, and Terraform validate for both modules. No AWS resources provisioned.
- 14 Nov: Part C access and browser app added Cognito admin/kiosk groups, PKCE public client, JWT-protected HTTP API routes, CloudFront OAC private static origin, API no-cache routing, security headers, frontend S3 publishing and generated `config.json`. Added kiosk camera/upload/polling flow, admin employee creation/consent, 3–5 photo enrollment, offboarding, attendance filters/pagination and daily/weekly report views. Added `docs/FRONTEND.md`. GitHub Actions passed 57 Python tests, Ruff, Node module syntax and HTML CSP hygiene checks, Terraform formatting and validation for all modules plus the composed dev root. No AWS resources provisioned; no browser/device E2E test run.
- 14 Nov: Added Part B reason-required attendance override and validated settings GET/PUT endpoints with audit records, scoped IAM, API routes, admin override dialog and settings form. Added production Terraform root with deletion protection and a manual-only OIDC plan/apply workflow gated by GitHub environments; the apply job downloads the previously reviewed plan and verifies the same commit SHA/branch. Added the consent-gated `scripts/e2e_smoke.sh` flow for a deployed dev stack. Solo branch CI passed 71 Python tests, Ruff, frontend syntax/CSP checks, Bash syntax, workflow YAML parsing and Terraform formatting/validation for all modules and both environment roots. The deployment workflow and smoke script are not run; no AWS resources provisioned.
- 14 Nov: Sushmitha opened PR #2 (`b/data-automation` → `develop`). It remains separate from `solo/amit-monday`; latest PR checks still fail Ruff and Terraform formatting. No merge or edits to the teammate branch were made.

- 14 Nov: Phase A reliability hardening on `solo/amit-monday`: request-ID idempotency in attendance transitions; recognition and enrollment retry paths preserve pending requests and raw images; enrollment uses per-employee leases and request markers; added automated async failure destination consumer that reconciles committed attendance/enrollment effects and compensates orphan face indexes, plus processor DLQ with alarm; added regression tests and updated contracts/architecture/Part A documentation. CI validation in progress after offboarding and orphan-face compensation changes. No AWS resources provisioned.

- 14 Nov: Phase A solo hardening completed locally on `solo/amit-monday`. GitHub Actions passed 91 Python tests, Ruff, browser syntax/CSP, Bash syntax, workflow YAML, Terraform fmt and Terraform validate across all modules and dev/prod roots. Implemented request-id attendance idempotency, retry-safe recognition/enrollment, SQS failure reconciliation/compensation, request-scoped Rekognition FaceIds, safe audited offboarding, and filtering of internal employee metadata. No AWS resources provisioned; no AWS integration, accuracy, browser/device E2E or 10-minute raw-image test run yet.
