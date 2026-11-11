# Team Brief: Serverless Face-Recognition Attendance System

Read this whole page (15 min), then your Part guide in `docs/parts/`. Questions go to the lead.

## 1. What we are building (in plain words)
An employee walks up to a screen, looks at the camera, and within 3 seconds sees "Welcome <name>, clocked in 09:14". No cards, no registers. Behind the scenes the photo goes to S3, a Lambda asks Amazon Rekognition who it is, writes the attendance to DynamoDB, and deletes the photo. Every night a job marks who was absent; every Monday a job produces weekly stats. HR uses an admin web page to filter and export attendance.

It must be **live and production-grade, not a demo**: HTTPS, logins, least-privilege security, encryption, alarms, automated deployment, tests, cost sheet, design document, and a demo video.

## 2. The finish line
`docs/SPEC.md` is the finish line (frozen). Short version: all MUST items pass, `main` is deployed to prod, the team has used it for real for a day, and the submission pack (design doc PDF, video, cost sheet, README) is ready by **Sun 15 Nov 2026**. Submission day is Mon 16 Nov (buffer, not work time).

## 3. Team and ownership
| Role | Owner | Builds | Do not touch |
|---|---|---|---|
| Lead | Amit | Repo, CI/CD, AWS bootstrap, KMS, buckets, IAM baseline, alarms, shared layer (tz/config/responses), design doc, cost sheet, video, integration | |
| **Part A**: Recognition engine | ______ | Rekognition, enrollment, presign, recognize, result, faces-delete Lambdas | B's and C's folders |
| **Part B**: Data and automation | ______ | 5 DynamoDB tables, `record_scan`, employees/attendance/reports/override/settings Lambdas, daily + weekly jobs, scheduler | A's and C's folders |
| **Part C**: Access and frontend | ______ | Cognito, API Gateway, CloudFront, kiosk app, admin app, `auth.py` | A's and B's folders |
Detailed guides: `docs/parts/PART-A-recognition.md`, `PART-B-data-automation.md`, `PART-C-access-frontend.md`.

## 4. How the pieces fit together (why integration will not hurt)
Integration problems come from people guessing each other's names and shapes. We remove the guessing:
1. **`docs/contracts.md` is frozen.** It lists every table, attribute, S3 key, endpoint, result code, environment variable and function name. Use them exactly. If you think a contract is wrong, tell the lead; do not change it yourself.
2. **Terraform modules are the only wiring.** Each Part owns one module. Parts connect through module outputs: each Part exports `api_routes` (which URL maps to which Lambda) and the access module builds the API from them. You never edit another Part's module.
3. **Shared code lives in one layer** (`attendance_common`). Part A calls Part B's `record_scan(...)` as a library function, so both can test independently.
4. **Walking skeleton first.** By end of Day 2 every endpoint exists and returns contract-shaped fake data, and the kiosk works end to end with stubs. After that we replace stubs with real logic one at a time, and the system always works.
5. **Contract tests + CI.** Every PR runs tests that check shapes against contracts. A PR that breaks a contract cannot merge.

## 5. Git workflow
- Branches: `develop` (deploys to dev), `main` (deploys to prod, protected). Your branches: `a/<topic>`, `b/<topic>`, `c/<topic>`. PR into `develop`. Squash merge. At least 1 review (the lead, or another Part owner for shared changes).
- Small PRs (one Lambda or one screen), merged at least daily. Never push to `main`/`develop` directly.
- Commit messages: `a: recognize no_match path` (part prefix + what).
- Before opening a PR: `pytest`, `ruff check .`, fill the PR template, update `docs/STATUS.md`.
- Nobody deploys by hand to prod. Merge to `develop` deploys to dev automatically; test there.

## 6. Your local setup (30 min)
Install Git, Python 3.12, VS Code, Terraform (Part A/B/C modules need `terraform fmt`). Clone the repo, `python -m venv .venv`, `pip install -r requirements-dev.txt`, run `pytest` (should pass). You get a **read-only IAM user for the dev account** (Console) to see logs, tables and S3. You do not need your own AWS account.

## 7. Using AI assistants safely
You may use any AI assistant. At the start of every session paste the **session start prompt** from `docs/AI_CONTEXT.md`; at the end paste the **session end prompt**. AI assistants forget; the repo files do not. Never let an AI change `docs/contracts.md`, other Parts' folders, or IAM wildcards. When an error appears, ask the AI for the root cause and the list of files affected before changing anything. Paste real error text and the relevant log lines, not a description.

## 8. Five-day plan (check-ins: standup 10:00, integration checkpoint 18:00; adjust to your availability and tell the lead)
| Day | Lead | Part A | Part B | Part C |
|---|---|---|---|---|
| **1 Wed 11** | Freeze docs, branch protection, bootstrap AWS, foundation on dev, shared layer, onboard team | Read docs; unit tests + handler skeletons for presign/result/recognize | Read docs; unit tests for `record_scan`; table definitions | Read docs; kiosk + admin static mockups using fake API data; confirm design direction |
| **2 Thu 12** | Deploy all stubs on dev; CI deploy workflow green | Stub Lambdas deployed, S3 trigger working | Stub Lambdas deployed; tables live | Cognito + CloudFront + API routes live; kiosk talks to real dev API (stubs) = **walking skeleton by 18:00** |
| **3 Fri 13** | Alarms, dashboard, IAM review | Real recognize + enroll + faces-delete; accuracy test | Real `record_scan`, admin APIs, daily/weekly jobs | Real kiosk flow, admin table, enrollment page; **18:00 integration checkpoint** |
| **4 Sat 14** | Prod deploy, hardening, pilot starts, design doc | Tuning, keep-warm, edge cases | Reports, override, seed data, job tests | Polish, browsers, CSV export, error states |
| **5 Sun 15** | **Freeze 12:00**, final e2e, video, PDF, submission pack | Bug fixes only | Bug fixes only | Bug fixes only |
Rule: after the Day 3 checkpoint, no new features unless the lead approves. Anything not finished goes into "Known limitations" honestly.

## 9. Definition of done for a Part
Your Part is done when: (1) every item in your guide's "Done when" list passes on **dev**, (2) unit + contract tests pass in CI, (3) you updated `docs/STATUS.md`, (4) the lead ran the e2e smoke test through your pieces.

## 10. When you are blocked
Post the exact error + what you tried in the team chat within 30 minutes of being stuck. Do not silently change a contract or another Part's file to "get past" it.
