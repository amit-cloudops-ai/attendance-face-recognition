# Part B — Data and Attendance (Sushmita)

**Owner:** Sushmita. **Integration target:** `develop`. Suggested branch: `team/sushmita-part-b`.
**Deadline:** Sunday 15 November 2026, 18:00 IST for a reviewable PR.
**Read first:** `docs/contracts.md` sections 1, 3, 5, 7 and 8; `docs/FINISH_LINE.md`.

## Mission
Implement data and attendance behavior: employee records, clock-in/out rules, attendance query, daily absence processing, weekly analytics and report retrieval. Frozen contracts define all external interfaces. Monday sprint infrastructure is SAM, not Terraform.

## Files you own
- `shared/python/attendance_common/record_scan.py`
- `services/data/employees/**`
- `services/data/attendance_query/**`
- `services/data/daily_job/**`
- `services/data/weekly_job/**`
- `services/data/reports/**`
- `services/data/override/**` and `services/data/settings/**` only after core scope passes
- Focused Part B tests under `tests/unit/`

Coordinate shared Python imports with Amit. Do not edit recognition code, frontend, SAM template, frozen contracts, contract tests or another owner's paths.

## Required implementation
1. **record_scan:** derive business date in Asia/Kolkata; first scan creates clock-in; late status uses shift_start + grace; rapid scan inside debounce returns duplicate_ignored; later scan updates clock_out; conditional writes prevent concurrent duplicate clock-ins; handle an existing absent row safely. Return the exact contract shape.
2. **Employees:** list/get/create/deactivate. Validate employee ID and HH:MM fields. Require consent=true, persist consent_at, preserve attendance history on deactivation, and write required audit events.
3. **Attendance query:** employee/date/status filters, limit/cursor pagination, employee partition key or date-index GSI as appropriate. Handle DynamoDB pagination and Decimal serialization.
4. **Daily job:** input {} or {"date":"YYYY-MM-DD"}; IST dates; skip weekends/holidays; idempotently add absent rows only for active employees without a record; set missing_clock_out where required; write contract-compliant daily JSON. CSV is secondary.
5. **Weekly job:** input {} or {"week":"YYYY-Www"}; default previous ISO week; calculate Mon-Sun, working days and percentages exactly as contracts.md defines; guard zero working days; JSON first, CSV secondary.
6. **Reports:** read the requested daily/weekly JSON and return the specified summary and a short-lived CSV URL when available; correct not-found response.
7. **Optional only after core:** override with mandatory reason and audit; settings GET/PUT with range validation and audit.

## Tests and proof
Cover on-time/late, debounce, clock-out, IST midnight, concurrent first scan, absent-row conversion, inactive employee, employee consent, query filters/pagination, daily holiday/weekend skip and idempotency, missing clock-out, weekly ISO boundaries, hand-calculated percentages and zero working days.

Use mocks/local fixtures; no live AWS. Run `pytest -q` and `ruff check .`.

## Deliverables
- Working code in owned paths and focused tests.
- PR into develop with one-line-per-file summary, contract mapping, actual test output, redacted sample events, manual verification checklist and known gaps.
- Update docs/STATUS.md only for behavior actually implemented and verified.
- No AWS provisioning, credentials, account IDs or real biometric images.

## Out of scope
Recognition/Rekognition handlers, API Gateway/SAM, frontend, route/schema redesign, contract edits and contract-test edits. Ask Amit with exact contract section and evidence if blocked.
