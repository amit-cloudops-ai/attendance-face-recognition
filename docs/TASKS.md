# Team allocation and delivery contracts

Deadline: Monday 16 November 2026. Code freeze: Sunday 15 November 2026, 21:00 IST.
Team contributions are additive. Amit's solo implementation is the guaranteed delivery track and must not depend on teammate completion.

## Branch model
- Amit: `solo/amit-monday` — independent end-to-end implementation.
- Team integration: `develop`.
- Sushmita: her own branch (suggested `team/sushmita-part-b`) → PR into develop.
- Gopi: his own branch (suggested `team/gopi-part-c`) → PR into develop.
Never automatically merge team code into Amit's solo branch. Amit decides after review whether to cherry-pick anything.

## Assignments
- **Sushmita — Part B: data and attendance logic.**
- **Gopi — Part C: access and frontend.**
- **Amit — Part A, platform/infrastructure, full integration and independent solo implementation.** Amit's solo branch independently includes the entire system, not just Part A.

---

## Sushmita — Part B: data + attendance
**Read first:** `docs/contracts.md`, `docs/parts/PART-B-data-automation.md`, `docs/FINISH_LINE.md`.

### Scope
1. Implement `attendance_common.record_scan(employee_id, scanned_at, confidence)`: IST business date; shift/grace calculation; first scan creates clock-in; debounce suppresses rapid repeats; later scan updates clock-out; conditional writes protect concurrent scans.
2. Employee create/list/get/deactivate handlers. Validate required fields and explicit consent on employee creation. Preserve attendance history on deactivation.
3. Attendance query: employee/date/status filters, pagination, date-index access pattern.
4. Daily job: skip weekends/holidays; idempotently create absent records only for active employees with no attendance; write daily JSON summary. CSV is secondary.
5. Weekly job: previous ISO week, working-day calculation and percentages exactly as defined in contracts.md; JSON is primary.
6. Reports retrieval handler. Override/settings handlers only after the above core paths pass.
7. Add tests for all above behavior; do not weaken existing tests/contracts.

### Files / boundaries
Own: `shared/python/attendance_common/record_scan.py` and Part B files under `services/data/**`, plus focused Part B unit tests.
Do not edit: `services/recognition/**`, `web/**`, `template.yaml`, frozen `docs/contracts.md`, `tests/contract/**`, or other teammate-owned paths without coordination.

### Deliverables
- Working code and tests.
- PR into develop with a file-by-file summary, contract mapping, commands and actual test output.
- Redacted sample event payloads and a concise manual verification checklist in the PR description.
- Update docs/STATUS.md only for completed/verified tasks.
- No AWS provisioning, credentials, account IDs or real biometric images in the repo.

### Acceptance
Tests cover on-time/late, duplicate within debounce, clock-out after debounce, IST midnight, concurrent first scans, inactive employee, daily idempotency, holiday/weekend skip, weekly percent hand-calculation. `pytest -q` and `ruff check .` pass. Contracts unchanged. Target PR: Sunday 15 Nov 18:00 IST.

### Not included
Recognition/Rekognition handlers, API Gateway/SAM, frontend, schema or route redesign.

---

## Gopi — Part C: access + frontend
**Read first:** `docs/contracts.md`, `docs/parts/PART-C-access-frontend.md`, `docs/FINISH_LINE.md`.

### Scope
1. Shared Cognito Hosted UI + PKCE authentication and a small API client. Handle missing/expired token and 401/403 cleanly.
2. Kiosk page: camera preview, capture, resize/compress, request upload URL, submit the S3 pre-signed POST using all returned fields, poll result, render pending/present/late/duplicate/no_match/no_face/multiple_faces/low_quality/error states.
3. Admin page: protected login, employee create with explicit consent, enrollment flow for 3–5 photos, employee list/deactivation, attendance table filters and pagination, daily/weekly report display.
4. Responsive mobile-friendly layout; camera permission and unsupported-browser states; accessible labels/focus. Never log tokens or image data.
5. Provide local run instructions and a browser verification matrix.

### Files / boundaries
Own: `web/shared/**`, `web/kiosk/**`, `web/admin/**`, and frontend-specific documentation.
Do not edit backend handlers, `template.yaml`, frozen `docs/contracts.md`, contract tests or Part B-owned paths.

### Deliverables
- Frontend code with clear local run instructions.
- PR into develop with screenshots/short recording, routes used, file-by-file summary, and desktop/mobile verification.
- Update docs/STATUS.md only for completed/verified work.
- No AWS provisioning or credentials.

### Acceptance
Kiosk path is testable with mock or deployed API: preview → capture → pre-signed upload → poll → result. Admin supports login, employee consent/create, enrollment, filtered attendance and reports. Clear failure states for denied camera, missing config, expired session, API errors and unknown face. No console errors. Target PR: Sunday 15 Nov 18:00 IST.

### Not included
Attendance calculation, Lambda/data code, infrastructure, contract changes.

---

## Amit — independent solo track
Branch: `solo/amit-monday`. It must be independently demoable. Work sequence:
1. Shared library + tests.
2. Recognition API and async handlers; ensure raw images are deleted in all terminal paths.
3. Data handlers/jobs and report generation.
4. Single SAM template: private S3, CloudFront, Cognito/JWT API, DynamoDB, Rekognition, Scheduler, narrow per-function IAM and alarms.
5. Kiosk/admin UI and configuration.
6. CI, SAM validation/build, unit/mock/local integration tests.
7. After explicit approval only: deploy, verify live gates, collect evidence, rehearse and package demo.

No production-readiness claim until required evidence exists.

## PR protocol for everyone
- One coherent task per PR; team PR base is develop.
- Never push directly to main/develop.
- Never edit contracts/tests to make code pass.
- Run pytest, ruff and applicable SAM/cfn-lint validation.
- PR body: summary, changed files, acceptance checks, actual command output, known gaps.
- Team PRs are not dependencies of solo branch.
