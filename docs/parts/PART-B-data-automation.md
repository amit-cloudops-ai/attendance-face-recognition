# Part B — Data and Attendance (Sushmita)

**Sprint owner:** Sushmita. **Team integration target:** `develop`. Suggested branch: `team/sushmita-part-b`.
**Sprint deadline:** Sunday 15 November 2026, 18:00 IST for a reviewable PR.
**Read first:** `docs/contracts.md` sections 1, 3, 5, 7, 8 and `docs/FINISH_LINE.md`.

## Mission
Implement the business-data layer: attendance rules, employee records, attendance query, daily absence processing, weekly analytics and report retrieval. The frozen contracts define the external interface. This sprint's deployment is SAM, not Terraform; do not build Terraform modules.

## Files you own
- `shared/python/attendance_common/record_scan.py`
- `services/data/employees/**`
- `services/data/attendance_query/**`
- `services/data/daily_job/**`
- `services/data/weekly_job/**`
- `services/data/reports/**`
- `services/data/override/**` and `settings/**` only after core tasks pass
- focused Part B tests under `tests/unit/`

Coordinate the shared library imports with Amit before changing other shared modules. Do not edit recognition code, frontend, SAM template, frozen contracts or contract tests.

## Required implementation
### 1. record_scan
Implement exactly the contract behavior:
- Derive business date from the supplied timestamp in Asia/Kolkata.
- First scan creates clock-in. Status is late only when scan time is later than shift_start + configured grace; otherwise present.
- A scan within debounce is duplicate_ignored and must not change clock-in/out.
- A later scan at or beyond debounce updates clock_out (last scan wins).
- Use DynamoDB conditional writes to handle concurrent first scans; never allow two simultaneous clock-ins.
- Handle an existing absent row by converting it to a clock-in without losing idempotency.
- Return the specified shape: action, status, date, clock_in, clock_out.

### 2. Employee handlers
Implement list/get/create/deactivate routes in contracts.md. Validate employee_id format and HH:MM shift fields. Require consent=true at creation and persist consent_at. Deactivation sets active=false, preserves history, and writes the specified audit event.

### 3. Attendance query
Support employee_id, from, to, status, limit and cursor. Use the employee partition key when employee is selected; otherwise query the date-index GSI. Paginate correctly (DynamoDB Limit applies before FilterExpression). Convert Decimal safely before JSON serialization and enrich names from employees.

### 4. Daily job
Input {} or {"date":"YYYY-MM-DD"}. Use IST. Skip weekends and configured holidays. For each active employee without an attendance row, create an absent row using a conditional put; never overwrite a prior record. Add missing_clock_out where specified. Generate the daily JSON schema exactly. CSV is secondary if time permits. Re-runs must be idempotent.

### 5. Weekly job
Input {} or {"week":"YYYY-Www"}. Default to previous ISO week. Compute Monday-Sunday range, working days excluding weekends/holidays, and the exact percentages in contracts.md (one decimal). Guard zero working days. JSON is primary; CSV secondary.

### 6. Reports handler
Read requested daily/weekly JSON from reports bucket and return the defined summary plus a time-limited CSV URL only when CSV exists. Return the contract's 404 response for missing reports.

### 7. Optional endpoints
Only after the above are tested: override with mandatory reason + audit trail; settings GET/PUT with type/range validation + audit.

## Tests and proof
Add focused tests for on-time, late, debounce, clock-out, IST midnight, concurrent first scan, absent-row conversion, inactive employee, employee consent validation, query filters/pagination, daily weekend/holiday skip, daily idempotency, missing clock-out flag, weekly ISO boundaries, percentages and zero-day week. Tests use mocks/local fixtures; no live AWS needed.

## Deliverables
1. Working code in the owned paths.
2. Unit tests and actual output of `pytest -q` and `ruff check .`.
3. PR into develop with changed-files list, contract mappings, test output, redacted event samples, manual checklist and known gaps.
4. Update docs/STATUS.md only for behavior genuinely implemented and verified.

## Not allowed
No AWS resources, no credentials/account IDs, no real biometric photos, no schema/route renames, no edits to tests to make code pass. If a contract ambiguity blocks you, ask Amit with exact section and evidence.
