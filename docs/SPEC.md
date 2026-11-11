# SPEC: Scope and Finish Line

**Version 1.0, FROZEN on 11 Nov 2026.** Any change needs lead approval and an update to this file in the same PR.
**Target:** production-ready and live by **15 Nov 2026**. Submission 16 Nov (buffer day).

## 1. Purpose
Contactless attendance for ~100 employees: face capture in browser, recognition in under 3 s, attendance stored in DynamoDB, automatic daily absence marking and weekly analytics, admin web app. No swipe cards, no manual registers.

## 2. Scope tiers
| Tier | Meaning | Items |
|---|---|---|
| **MUST** | Project is not done without it | Everything in section 3 marked MUST, all of section 4, all deliverables in section 5 |
| **SHOULD** | Ship if on schedule, otherwise list under Known Limitations | Admin override with audit, CSV export, settings endpoint, DLQ + alarms, keep-warm schedule, duplicate-face check at enrollment |
| **LATER** | Documented, not built | Rekognition Face Liveness, admin MFA, custom domain, email reports (SES), multi-site, mobile app |

## 3. Functional acceptance criteria
| ID | Tier | Criterion | Owner |
|---|---|---|---|
| F01 | MUST | Admin can add an employee and enroll 3 to 5 photos; faces are indexed in Rekognition and the uploaded photos are deleted | A + B + C |
| F02 | MUST | Kiosk shows live camera preview, captures a still, and displays name, time and status | C |
| F03 | MUST | First scan of a day creates `clock_in` with status `present`, or `late` if after shift start + grace | A (calls B) |
| F04 | MUST | A later scan at least `debounce_minutes` after clock_in updates `clock_out`; a scan inside the debounce window is ignored and the kiosk says "already clocked in" | B |
| F05 | MUST | Unknown face returns `no_match` and writes nothing. No face, several faces, poor quality each return their own code | A |
| F06 | MUST | An inactive employee returns `inactive` and writes nothing | A |
| F07 | MUST | At 23:59 IST every day the daily job writes `absent` for each active employee with no record on a working day, never overwrites, is safe to re-run, skips weekends and holidays, and writes the daily summary (JSON + CSV) to S3 | B |
| F08 | MUST | Monday 00:30 IST the weekly job writes analytics for the previous ISO week: present %, late %, absences per employee | B |
| F09 | MUST | Admin app: Cognito login; table filterable by employee, date range, status; pagination | B + C |
| F10 | MUST | Admin app shows daily and weekly reports | B + C |
| F11 | SHOULD | Admin can override a record with a mandatory reason; every override is audit-logged | B + C |
| F12 | MUST | Offboarding: deactivate employee and delete their faces from Rekognition; attendance history is kept | A + B + C |
| F13 | SHOULD | CSV export from the admin table | C |

## 4. Non-functional acceptance criteria
| ID | Criterion | How we prove it |
|---|---|---|
| N01 | p95 capture-click to result-on-screen is 3 s or less over 20 consecutive scans (warm) | `scripts/e2e_smoke` timing output pasted in STATUS |
| N02 | No raw image remains in the raw bucket 10 minutes after any test | List `captures/` and `enroll/` after test: empty |
| N03 | Encryption at rest on DynamoDB and S3 (KMS); TLS-only bucket policies | Screenshots + Terraform |
| N04 | One IAM role per Lambda; no `*` resources except where AWS requires it (logs) | IAM matrix in ARCHITECTURE section 6 matches Terraform |
| N05 | No public bucket; only CloudFront reads the web bucket | Block Public Access screenshot |
| N06 | `terraform apply` from a clean checkout builds a working environment | Rebuild dev from scratch once before freeze |
| N07 | CI green on `main`; no direct pushes; at least 1 review on every PR | Branch protection screenshot |
| N08 | Alarms email the lead: any Lambda errors, DLQ depth above 0, daily/weekly job failure, monthly budget over 15 USD | Trigger one alarm deliberately |
| N09 | Monthly cost at 100 employees x 2 scans/day is 15 USD or less | docs/COST.md |
| N10 | Logs retained 30 days, JSON structured, never contain images, tokens or full face data | Code review + sample log |
| N11 | Works on latest Chrome (desktop + Android) and Safari (iOS) | Manual test table in STATUS |

## 5. Deliverables
| Deliverable | Owner | File |
|---|---|---|
| Technical design doc with architecture diagram | Lead | docs/ARCHITECTURE.md (diagram in README + ARCHITECTURE; export PNG for the PDF) |
| Video demo: registration, clock-in, clock-out, admin summary | Lead (all appear) | docs/DEMO_SCRIPT.md is the storyboard |
| GitHub repo with deployment instructions | Lead | README.md + ARCHITECTURE section 11 |
| AWS cost sheet, 100 employees, 2 scans/day | Lead | docs/COST.md |

## 6. Test strategy
1. **Unit tests** (each Part, `pytest`, moto for S3/DynamoDB, mocks for Rekognition).
2. **Contract tests** (`tests/contract`): assert every Lambda reads and writes exactly the shapes in contracts.md.
3. **Integration on dev**: API calls against the deployed dev stack.
4. **E2E smoke** (`scripts/e2e_smoke`): enroll, scan, scan again, query, run daily job, fetch report.
5. **Pilot**: the whole team uses the prod kiosk for real for at least 1 working day before submission.

## 7. Project Definition of Done (release gate, 15 Nov)
- [ ] All MUST criteria pass (F01-F10, F12, N01-N11); evidence linked in STATUS
- [ ] `main` deployed to prod, kiosk and admin reachable over HTTPS
- [ ] Pilot completed, results recorded
- [ ] Design doc PDF, video, cost sheet, README deploy instructions ready
- [ ] Known limitations section written honestly

## 8. Known limitations (declared up front)
- **Still-photo spoofing:** v1 uses still images; a printed or on-screen photo of an enrolled employee could match. Mitigations in v1: strict threshold (default 95, tunable), kiosk supervised by reception, audit trail. Planned fix (LATER): Rekognition Face Liveness.
- Lighting and camera quality affect accuracy; enrollment with 3-5 varied photos is mandatory.
- Single region (ap-south-1), no multi-region failover.
