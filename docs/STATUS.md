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
| bootstrap + foundation | Lead | not started | - | |
| shared layer (tz, config, responses) | Lead | in progress | 16 tests passed; Ruff passed | Implemented IST helpers, cached config defaults/lookup, and API proxy responses on solo/amit-monday |
| Part A: recognition | Amit (solo) | in progress | 22 recognition/enrollment tests; Terraform validate green | Six handlers and Terraform module implemented: Lambda packaging, IAM, Rekognition collection, S3 notifications, DLQs, logs and alarms |
| Part B: data + automation | Amit (solo) | in progress | 19 data API/job tests; Terraform validate green | Employee CRUD, attendance query, daily/weekly jobs and report retrieval implemented; data module creates five encrypted/PITR tables, schedules, IAM and alarms |
| shared record_scan | Part B interface / Amit solo implementation | in progress | 16 tests passed; Ruff passed | Implemented conditional clock-in, debounce, clock-out, IST date, absent-row promotion and out-of-order event protection on solo/amit-monday |
| Part C: access + web | | not started | - | |
| CI/CD | Lead | CI green; deploy workflow pending | 57 Python tests; Ruff; Terraform fmt + validate for recognition and data modules | No deploy workflow or AWS apply; validation is static/mocked only | |

## Acceptance evidence
Paste links/screenshots per SPEC ID (F01-F13, N01-N11) as they pass.

## Confirmed decisions
- UI direction: A (clean light enterprise admin + high-contrast kiosk), confirmed 11 Nov.
- Solo infrastructure implementation follows ARCHITECTURE.md and TEAM_BRIEF: Terraform modules, not SAM. The Part B/Part C guide references are flagged as stale documentation; no frozen API/data contract changed.

## Known issues
- Part A is not complete: AWS deployment/integration, real Rekognition accuracy, IAM verification in-account, and end-to-end kiosk validation remain. The module has only been initialized and validated locally in CI; no apply has run.
- AWS integration, biometric accuracy, in-account IAM, raw-image deletion behaviour and end-to-end latency are not verified; no AWS resources have been provisioned.
- Part B optional override/settings handlers, foundation/root environment wiring, Part C access/API Gateway and frontend, and end-to-end deployment remain.
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
