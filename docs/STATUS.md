# Project Status (source of truth for "what is built")

**Update this file at the end of every work session (human or AI).** Newest entries at the top of the log.

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
| bootstrap + foundation | Amit (solo) | in progress | Terraform fmt + validate green | Foundation module defines KMS, private encrypted buckets, raw-image lifecycle/CORS, common layer, SNS alerts and USD 15 budget; dev root wired. No bootstrap or apply performed |
| shared layer (tz, config, responses, auth) | Amit (solo) | in progress | Shared attendance tests included in 57 passing; Ruff passed | IST helpers, cached config, API responses, Cognito group/username helpers and conditional record_scan implementation on solo/amit-monday |
| Part A: recognition | Amit (solo) | in progress | 22 recognition/enrollment tests; Terraform validate green | Six handlers and Terraform module implemented: Lambda packaging, IAM, Rekognition collection, S3 notifications, DLQs, logs and alarms |
| Part B: data + automation | Amit (solo) | in progress | 19 data API/job tests; Terraform validate green | Employee CRUD, attendance query, daily/weekly jobs and report retrieval implemented; data module creates five encrypted/PITR tables, schedules, IAM and alarms |
| shared record_scan | Part B interface / Amit solo implementation | in progress | 16 tests passed; Ruff passed | Implemented conditional clock-in, debounce, clock-out, IST date, absent-row promotion and out-of-order event protection on solo/amit-monday |
| Part C: access + web | Amit (solo) | in progress | Node module syntax + HTML CSP hygiene green; access/dev Terraform validate green; browser testing pending | Cognito groups and PKCE public client, JWT HTTP API routes, CloudFront private web origin/security headers, generated config.json, kiosk camera/scan flow, admin employee/enrollment/attendance/report UI |
| CI/CD | Amit (solo) | CI green; deploy workflow pending | 57 Python tests; Ruff; Node syntax + CSP check; Terraform fmt + validate for recognition, data, foundation, access and dev root | No OIDC deployment workflow or AWS apply; validation is static/mocked only | |

## Acceptance evidence
Paste links/screenshots per SPEC ID (F01-F13, N01-N11) as they pass.

## Confirmed decisions
- UI direction: A (clean light enterprise admin + high-contrast kiosk), confirmed 11 Nov.
- Solo infrastructure implementation follows ARCHITECTURE.md and TEAM_BRIEF: Terraform modules, not SAM. The Part B/Part C guide references are flagged as stale documentation; no frozen API/data contract changed.

## Known issues
- Part A is not complete: AWS deployment/integration, real Rekognition accuracy, IAM verification in-account, and end-to-end kiosk validation remain. The module has only been initialized and validated locally in CI; no apply has run.
- AWS integration, biometric accuracy, in-account IAM, raw-image deletion behaviour and end-to-end latency are not verified; no AWS resources have been provisioned.
- Part B SHOULD override/settings handlers remain unimplemented. Part C has not been browser-tested against a deployed stack. Bootstrap state bucket/OIDC role setup and automated deployment workflow remain.
- After the first approved deployment, add the exact CloudFront site origin to the dev `allowed_origins`, `callback_urls` and `logout_urls` values and apply again; this enables production-domain S3 presigned POST CORS and Cognito redirects without introducing a Terraform dependency cycle.
- Part B and Part C guides still mention SAM in places, while ARCHITECTURE.md and TEAM_BRIEF specify Terraform modules. Solo implementation follows the architecture/Team Brief; reconcile the stale guide wording before team integration.

## Decisions made after freeze
(none; contracts are frozen. List approved changes here with date and reason.)

## Session log
- 11 Nov: repo scaffold, SPEC, contracts, architecture, part guides created.
- 14 Nov: Amit solo T10 implementation added: attendance_common timezone/config/response helpers, record_scan, and focused moto-backed unit tests. GitHub Actions passed: Ruff, pytest (16 passed), and terraform fmt. No AWS resources provisioned.
- 14 Nov: Amit solo T11 batch added Cognito group helpers plus presign, result-polling and S3-triggered recognize handlers. Added mocked-AWS coverage for authorization, pre-signed POST, result contract, recognition outcomes, duplicate delivery and image cleanup. GitHub Actions passed: Ruff, pytest (28 passed), and terraform fmt. No AWS resources provisioned.
- 14 Nov: Part A enrollment batch added admin enrollment URL creation, S3-triggered face indexing with quality/duplicate/limit checks, and audited face-template deletion. GitHub Actions passed: Ruff, pytest (38 passed), and terraform fmt. AWS integration and real biometric accuracy remain unverified; no AWS resources provisioned.
- 14 Nov: Recognition Terraform module added six Lambda packages, least-privilege per-function roles, Rekognition collection, S3 prefix notifications, encrypted SQS failure destinations, log groups and CloudWatch alarms. GitHub Actions passed Python tests (38), Ruff, Terraform fmt and Terraform validate. No Terraform apply or AWS resource provisioning performed.
- 14 Nov: Part B core APIs and jobs added employee CRUD with consent/audit, indexed attendance queries with cursor pagination, idempotent daily absent finalization and missing-clock-out flags, weekly ISO analytics, and report JSON/CSV retrieval. Added the Terraform data module for five encrypted/PITR DynamoDB tables, five Lambdas, Asia/Kolkata schedules, least-privilege IAM and CloudWatch alarms. GitHub Actions passed 57 Python tests, Ruff, Terraform fmt, and Terraform validate for both modules. No AWS resources provisioned.
- 14 Nov: Part C access and browser app added Cognito admin/kiosk groups, PKCE public client, JWT-protected HTTP API routes, CloudFront OAC private static origin, API no-cache routing, security headers, frontend S3 publishing and generated `config.json`. Added kiosk camera/upload/polling flow, admin employee creation/consent, 3–5 photo enrollment, offboarding, attendance filters/pagination and daily/weekly report views. Added `docs/FRONTEND.md`. GitHub Actions passed 57 Python tests, Ruff, Node module syntax and HTML CSP hygiene checks, Terraform formatting and validation for all modules plus the composed dev root. No AWS resources provisioned; no browser/device E2E test run.
