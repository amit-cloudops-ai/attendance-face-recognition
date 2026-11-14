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
| shared layer (tz, config, responses) | Lead | not started | - | |
| Part A: recognition | | not started | - | |
| Part B: data + automation | Sushmitha | in progress | Ruff + 20 pytest tests + Terraform fmt + Part B module validate green | PR #2 ready for review; AWS deployment and end-to-end integration still pending |
| shared record_scan | Part B | in progress | unit tests green in CI | Conditional IST clock-in/clock-out logic implemented on `b/data-automation` |
| Part C: access + web | | not started | - | |
| CI/CD | Lead | CI file in repo; deploy workflow pending | - | |

## Acceptance evidence
Paste links/screenshots per SPEC ID (F01-F13, N01-N11) as they pass.

## Confirmed decisions
- UI direction: A (clean light enterprise admin + high-contrast kiosk), confirmed 11 Nov.

## Known issues
(none yet)

## Decisions made after freeze
(none; contracts are frozen. List approved changes here with date and reason.)

## Session log
- 14 Nov: Part B implementation added shared attendance scan logic, employee/attendance/report/settings/override handlers, daily/weekly jobs, seed script, DynamoDB module and unit tests. PR #2 CI passed (Ruff, 20 pytest tests, Terraform fmt, and Part B module init/validate); AWS deployment and end-to-end integration remain pending.
- 11 Nov: repo scaffold, SPEC, contracts, architecture, part guides created.
