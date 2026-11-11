# Part B: Data and Automation

**Owner:** ______  **Folders you own:** `services/data/*`, `infra/modules/data/`, `shared/python/attendance_common/record_scan.py`, `scripts/seed_data.py`
**Read first:** SPEC (F03 F04 F07 F08 F09 F10 F11, N10), contracts sections 1, 3, 4, 5, 7, 8, 10.

## Mission
Own the data: tables, the attendance rules, the nightly absence job, the weekly analytics, and the admin read/write API. Everything about "what counts as present/late/absent" lives in your code.

## You depend on / provide
- From Lead: layer base (`tz`, `config.get_settings`, `responses`), KMS key, reports bucket, SNS topic.
- From Part C: `auth.require_group`, API routes built from your `api_routes`.
- You provide: tables (names/ARNs to Part A and the Lead), `record_scan` to Part A, `api_routes` for employees, attendance-query, reports, override, settings.

## Build steps (with why)
**1. Tables (Terraform, `infra/modules/data`).** Five tables exactly as contracts section 3: on-demand, KMS encryption with the shared key, PITR on, deletion protection on in prod, TTL on `scan-results.ttl`, GSI `date-index` on attendance (projection ALL). Seed the `SETTINGS` item (defaults) with a Terraform `aws_dynamodb_table_item` (`lifecycle { ignore_changes = [item] }` so later edits by the admin app are not overwritten). Outputs: names + ARNs map.

**2. `record_scan` (shared library).** Algorithm (contracts section 5):
1. `date = IST date of scanned_at`; load settings and the employee (`shift_start`).
2. Try `PutItem` with `ConditionExpression attribute_not_exists(employee_id)`: `clock_in = scanned_at`, `status = late` if `scanned_at` time is after `shift_start + grace_minutes` else `present`, `source = face`, `confidence`, `updated_at`. Success returns `action = clock_in`.
3. On `ConditionalCheckFailedException`: `GetItem`. If it is an `absent` row (rare: scan after the job but same date) convert it with an update conditional on `status = absent` into a clock-in. Otherwise if `scanned_at - clock_in < debounce_minutes` return `duplicate_ignored` with the existing times; else `UpdateItem` `clock_out = scanned_at`, `updated_at` (last scan wins) and return `clock_out`.
*Why conditional writes:* two scans at the same instant cannot both become clock_in.

**3. Employees Lambda.** Routes: list, get, create, deactivate (see contracts section 7). Validate `employee_id` regex, `shift_start/shift_end` as `HH:MM`, `consent=true` required on create. Create sets `active=true`, `photo_count=0`, `face_ids=[]`, `consent_at`. Deactivate sets `active=false` (never delete the row or history). Write audit rows (`employee_create`, `employee_deactivate`) using `get_username`.

**4. Attendance-query Lambda.** Validate dates. If `employee_id` is given: `Query` PK with `date BETWEEN from AND to`. Else: loop the GSI for each date in range (cap range at 93 days) with `Query` on `date-index`. Apply `status` as a FilterExpression, **loop until `limit` items are collected** (DynamoDB applies Limit before the filter). Cursor = base64 of `LastEvaluatedKey` (or your own composite). Merge `name` from a cached employees Scan. Convert `Decimal` to numbers before JSON.

**5. Daily job `daily-job`** (900 s timeout, 256 MB). Input `{}` or `{"date": ...}`.
1. Resolve date. If weekend (`weekend_days`) or `HOLIDAY#date` exists: write the report with `skipped` set, no absences, done.
2. Scan active employees. For each with no record: `PutItem` `status=absent`, `source=system`, `ConditionExpression attribute_not_exists(employee_id)` (never overwrites; re-runs are safe).
3. For records with `clock_in` but no `clock_out`: add flag `missing_clock_out` (SS ADD).
4. Query the day via GSI, build the daily report JSON + CSV per contracts section 8, `PutObject` to `reports/daily/YYYY-MM-DD.json|csv`.
5. On exception: log, publish to SNS alerts, re-raise.

**6. Weekly job `weekly-job`.** Input `{}` (previous ISO week) or `{"week": "YYYY-Www"}`. Compute Monday to Sunday dates; `working_days` = days not weekend/holiday; query each date via GSI; per employee compute `present_days` (present + late), `late_days`, `absent_days`, percentages per the definitions (round 1 decimal; guard `working_days = 0`). Write JSON + CSV to `reports/weekly/`. Same error handling.

**7. Scheduler (in your module).** Two `aws_scheduler_schedule` resources: `attendance-{env}-daily` `cron(59 23 * * ? *)` and `attendance-{env}-weekly` `cron(30 0 ? * MON *)`, `schedule_expression_timezone = "Asia/Kolkata"`, with an IAM role allowed `lambda:InvokeFunction` on the two job functions. *Why Scheduler:* EventBridge rules are UTC only.

**8. Reports Lambda.** Read JSON from S3, return `{"summary": ..., "csv_url": presigned GET 300 s}`; 404 if the object is missing. Use a regional s3v4 client.

**9. Override (SHOULD).** Validate `reason` non-empty; load old record; apply changes (`source=admin`, `updated_by`); write audit with old/new. **10. Settings (SHOULD).** GET returns merged defaults; PUT validates types/ranges (threshold 80-99.9, grace 0-120, debounce 1-60, weekend_days subset of 1..7) and writes audit.

**11. Seed script.** `scripts/seed_data.py`: creates 10 fake employees and 30 days of varied attendance (present/late/absent, some missing clock_out) into dev. Used for tests, demo and weekly-report verification.

**12. Terraform outputs.** `tables` (names, arns), `api_routes` (employees x4, attendance-query, reports, override x1, settings x2), `daily_job_arn`, `weekly_job_arn`. IAM exactly per ARCHITECTURE 6.1. Alarms on Errors for both jobs.

## Tests you must write
- `record_scan`: first scan present; first scan late (after grace); duplicate within debounce; clock_out after debounce; two rapid concurrent scans produce one clock_in; midnight boundary uses IST date; absent-row conversion.
- daily job: absences created only for active employees; weekend and holiday skip; never overwrites an existing record; idempotent re-run; missing_clock_out flag; report JSON matches the schema.
- weekly job: percentages on a seeded week; `working_days` with a holiday; zero-division guard; ISO week boundaries (including a week that spans two months).
- attendance-query: each filter, pagination, status filter with limit.
- contract tests: every item you write matches section 3; every API response matches section 7/8.

## Pitfalls
- **Time zones:** compute dates in IST always (`attendance_common.tz`), never `datetime.utcnow().date()`.
- DynamoDB returns `Decimal`; JSON needs conversion. Reserved words (`date`, `status`) need `ExpressionAttributeNames`.
- `Scan` and `Query` paginate at 1 MB; loop on `LastEvaluatedKey`.
- Scheduler cron uses 6 fields; weekday names must be `MON`.
- Do not scan the attendance table; use PK or GSI queries.

## Done when
- [ ] All tests green in CI; seeded 30-day data produces a weekly report that matches a hand calculation
- [ ] Daily job re-run changes nothing; manual run with `{"date": ...}` works on dev
- [ ] Admin attendance endpoint filters by employee, date range, status with pagination
- [ ] Schedules visible in the console with timezone `Asia/Kolkata`
- [ ] IAM matches the matrix; alarms created
