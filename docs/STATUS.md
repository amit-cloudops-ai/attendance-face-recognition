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
| Part B: data + automation | | not started | - | |
| shared record_scan | Part B interface / Amit solo implementation | in progress | 16 tests passed; Ruff passed | Implemented conditional clock-in, debounce, clock-out, IST date, absent-row promotion and out-of-order event protection on solo/amit-monday |
| Part C: access + web | | not started | - | |
| CI/CD | Lead | CI file in repo; deploy workflow pending | - | |

## Acceptance evidence
Paste links/screenshots per SPEC ID (F01-F13, N01-N11) as they pass.

## Confirmed decisions
- UI direction: A (clean light enterprise admin + high-contrast kiosk), confirmed 11 Nov.

## Known issues
- Part A is not complete: AWS deployment/integration, real Rekognition accuracy, IAM verification in-account, and end-to-end kiosk validation remain. The module has only been initialized and validated locally in CI; no apply has run.
- AWS integration, biometric accuracy, IAM, raw-bucket deletion behaviour and end-to-end latency are not yet verified; no AWS resources have been provisioned from this work session.

## Decisions made after freeze
(none; contracts are frozen. List approved changes here with date and reason.)

## Session log
- 11 Nov: repo scaffold, SPEC, contracts, architecture, part guides created.
- 14 Nov: Amit solo T10 implementation added: attendance_common timezone/config/response helpers, record_scan, and focused moto-backed unit tests. GitHub Actions passed: Ruff, pytest (16 passed), and terraform fmt. No AWS resources provisioned.
- 14 Nov: Amit solo T11 batch added Cognito group helpers plus presign, result-polling and S3-triggered recognize handlers. Added mocked-AWS coverage for authorization, pre-signed POST, result contract, recognition outcomes, duplicate delivery and image cleanup. GitHub Actions passed: Ruff, pytest (28 passed), and terraform fmt. No AWS resources provisioned.
- 14 Nov: Part A enrollment batch added admin enrollment URL creation, S3-triggered face indexing with quality/duplicate/limit checks, and audited face-template deletion. GitHub Actions passed: Ruff, pytest (38 passed), and terraform fmt. AWS integration and real biometric accuracy remain unverified; no AWS resources provisioned.
- 14 Nov: Recognition Terraform module added six Lambda packages, least-privilege per-function roles, Rekognition collection, S3 prefix notifications, encrypted SQS failure destinations, log groups and CloudWatch alarms. GitHub Actions passed Python tests (38), Ruff, Terraform fmt and Terraform validate. No Terraform apply or AWS resource provisioning performed.
