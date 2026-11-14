# Contracts (FROZEN v1.0)

Every name, schema, endpoint and code in this file is a promise between Parts. **Do not rename or reshape anything here.** If you think something must change, tell the lead; the lead changes it here first, then everyone updates. AIs and humans: copy names exactly.

## 0. Global conventions
| Item | Value |
|---|---|
| Region | `ap-south-1` |
| Environments | `dev`, `prod` (`{env}` below) |
| Resource prefix | `attendance-{env}-` |
| Time zone | `Asia/Kolkata` (IST, UTC+05:30) for all business dates |
| `date` | string `YYYY-MM-DD` in IST |
| Timestamps | ISO 8601 with offset, e.g. `2026-11-12T09:14:05+05:30` |
| `employee_id` | string, regex `^[A-Z0-9_-]{3,20}$`, e.g. `EMP001` |
| `request_id` | UUID v4 string |
| Runtime | Python 3.12, boto3 only (no third-party packages in Lambda zips; shared code comes from the layer) |
| JSON errors | `{"error": {"code": "<snake_case>", "message": "<human text>"}}` with matching HTTP status |

## 1. Lambda environment variables (set on EVERY Lambda by Terraform)
`ENV`, `TZ_NAME=Asia/Kolkata`, `LOG_LEVEL=INFO`, `TABLE_EMPLOYEES`, `TABLE_ATTENDANCE`, `TABLE_SCAN_RESULTS`, `TABLE_CONFIG`, `TABLE_AUDIT`, `BUCKET_RAW`, `BUCKET_REPORTS`, `COLLECTION_ID`.
Code must read names/ARNs only from these variables. Never hard-code a resource name.

## 2. Resource names
| Resource | Name |
|---|---|
| Tables | `attendance-{env}-employees`, `-attendance`, `-scan-results`, `-config`, `-audit` |
| Buckets | `attendance-{env}-raw-{account_id}`, `attendance-{env}-reports-{account_id}`, `attendance-{env}-web-{account_id}` |
| Rekognition collection | `attendance-{env}-faces` |
| KMS alias | `alias/attendance-{env}` |
| Lambda layer | `attendance-{env}-common` (import path `attendance_common`) |
| SNS alerts topic | `attendance-{env}-alerts` |
| Cognito | pool `attendance-{env}-users`, app client `attendance-{env}-web` (public SPA, PKCE, no secret), groups `admin` and `kiosk` |
| Lambdas | `attendance-{env}-<name>` where name is one of: `presign`, `result`, `recognize`, `enroll`, `enroll-url`, `faces-delete`, `failure` (internal async failure recovery), `employees`, `attendance-query`, `reports`, `override`, `settings`, `daily-job`, `weekly-job` |

## 3. DynamoDB schemas (all on-demand, KMS-encrypted, PITR on)
**employees**: PK `employee_id` (S)
`name` S, `email` S, `department` S, `shift_start` S "HH:MM", `shift_end` S "HH:MM", `active` BOOL, `face_ids` L of S, `photo_count` N, `consent_at` S (ISO), `created_at` S, `updated_at` S. Internal retry metadata: `enrollment_{request_id}` S (FaceId committed for that request), `enrollment_lock_request` S and `enrollment_lock_until` N (short per-employee lease).

**attendance**: PK `employee_id` (S), SK `date` (S)
`clock_in` S (ISO, absent for `absent` rows), `clock_out` S (ISO, optional), `status` S one of `present` | `late` | `absent`, `flags` SS (optional, value `missing_clock_out`), `confidence` N (optional), `source` S one of `face` | `admin` | `system`, `updated_at` S, `updated_by` S (optional). Internal retry metadata: `scan_events` M keyed by `request_id`, storing the exact outcome of each accepted scan request so retries cannot create a second attendance transition.
GSI **`date-index`**: PK `date`, SK `employee_id`, projection ALL.

**scan-results**: PK `request_id` (S)
`kind` S (`scan` | `enroll`), `code` S (see section 6), `employee_id` S (optional), `name` S (optional), `time` S (ISO, optional), `status` S (`present`|`late`, optional), `action` S (`clock_in`|`clock_out`|`duplicate_ignored`, optional), `message` S, `created_at` S, `ttl` N (epoch seconds, created_at + 86400). TTL attribute = `ttl`.

**config**: PK `pk` (S). One settings item `pk = "SETTINGS"` with:
`face_match_threshold` N default 95, `min_brightness` N default 40, `min_sharpness` N default 40, `grace_minutes` N default 15, `debounce_minutes` N default 10, `weekend_days` L of N ISO weekdays (Mon=1..Sun=7) default [6,7], `max_photos_per_employee` N default 5.
Holiday items: `pk = "HOLIDAY#YYYY-MM-DD"`, `name` S.

**audit**: PK `audit_id` (S, UUID)
`actor` S (Cognito username), `action` S (`override` | `employee_create` | `employee_deactivate` | `faces_delete` | `settings_update`), `employee_id` S (optional), `date` S (optional), `old` M, `new` M, `reason` S, `at` S (ISO).

## 4. S3 keys
| Bucket | Key | Written by | Notes |
|---|---|---|---|
| raw | `captures/{request_id}.jpg` | kiosk via pre-signed POST | deleted by recognize Lambda immediately; lifecycle 1-day backstop |
| raw | `enroll/{employee_id}/{request_id}.jpg` | admin UI via pre-signed POST | deleted by enroll Lambda immediately; lifecycle 1-day backstop |
| reports | `reports/daily/YYYY-MM-DD.json` and `.csv` | daily-job | versioned bucket |
| reports | `reports/weekly/YYYY-Www.json` and `.csv` (ISO week, e.g. `2026-W46`) | weekly-job | versioned bucket |
Only the recognition module defines `aws_s3_bucket_notification` for the raw bucket (one resource per bucket): prefix `captures/` triggers `recognize`; prefix `enroll/` triggers `enroll`.

## 5. Shared library `attendance_common` (layer; import path `attendance_common`)
| Module | Owner | Provides |
|---|---|---|
| `tz.py` | Lead | `now_ist()`, `today_ist()`, `to_iso(dt)`, `parse_hhmm(s)` |
| `config.py` | Lead | `get_settings()` returns dict with defaults filled in (60 s in-memory cache) |
| `responses.py` | Lead | `ok(body, status=200)`, `error(status, code, message)` for API proxy format |
| `auth.py` | Part C | `require_group(event, "admin" or "kiosk")`; `get_username(event)`. NOTE: HTTP API gives `cognito:groups` as a stringified list like `"[admin]"`, so match with a word-boundary check, never JSON-parse |
| `record_scan.py` | Part B | `record_scan(employee_id: str, scanned_at: datetime, confidence: float) -> dict` |

`record_scan` returns `{"action": "clock_in"|"clock_out"|"duplicate_ignored", "status": "present"|"late", "date": "YYYY-MM-DD", "clock_in": ISO, "clock_out": ISO|None}` and implements F03/F04: first scan of the IST date = clock_in (`late` if time > shift_start + grace_minutes, else `present`); later scan at least `debounce_minutes` after clock_in = update clock_out (last scan wins); otherwise `duplicate_ignored`. Writes use conditional expressions. Part A calls it from the `recognize` Lambda (library call, not a Lambda invoke, for latency).

## 6. Result codes
**Scan** (`kind=scan`): `pending`, `matched` (with `action`), `no_match`, `no_face`, `multiple_faces`, `low_quality`, `inactive`, `error`.
**Enroll** (`kind=enroll`): `pending`, `enrolled`, `no_face`, `multiple_faces`, `low_quality`, `unknown_employee`, `limit_reached`, `duplicate_face`, `error`.

Unexpected infrastructure failures remain `pending` while Lambda's configured automatic retries run. Only the failure-destination consumer sets `error` after retries are exhausted, then removes the retained raw image. The failure consumer's own poison messages are moved to `attendance-{env}-failure-processor-dlq` after five receives and trigger an alarm.

## 7. HTTP API
Base path `/api` on the same CloudFront domain as the web apps (no CORS needed for the API). Auth: `Authorization: Bearer <Cognito access token>`. Group `kiosk` or `admin` as noted. Pre-signed POST to S3 is the only cross-origin call.

| Method + path | Group | Lambda (owner) | Request | Success response |
|---|---|---|---|---|
| `POST /api/kiosk/upload-url` | kiosk, admin | presign (A) | `{}` | `200 {"request_id": "...", "upload": {"url": "...", "fields": {...}}, "expires_in": 60}` |
| `GET /api/kiosk/result/{request_id}` | kiosk, admin | result (A) | none | `200 {"request_id","kind","code","action?","name?","time?","status?","message"}`; `404 not_found` if unknown |
| `POST /api/admin/employees/{employee_id}/enroll-url` | admin | enroll-url (A) | `{}` | same shape as upload-url, key `enroll/{employee_id}/{request_id}.jpg` |
| `DELETE /api/admin/employees/{employee_id}/faces` | admin | faces-delete (A) | none | `200 {"deleted": N}`; clears `face_ids`, `photo_count=0` |
| `GET /api/admin/employees` | admin | employees (B) | none | `200 {"items": [employee...]}` |
| `GET /api/admin/employees/{employee_id}` | admin | employees (B) | none | `200 employee` |
| `POST /api/admin/employees` | admin | employees (B) | `{employee_id,name,email,department,shift_start,shift_end,consent:true}` | `201 employee` (`consent` must be true; sets `consent_at`, `active=true`) |
| `DELETE /api/admin/employees/{employee_id}` | admin | employees (B) | none | `200 employee` with `active=false` (history kept; UI then calls the faces DELETE) |
| `GET /api/admin/attendance` | admin | attendance-query (B) | query: `employee_id?`, `from?`, `to?` (YYYY-MM-DD), `status?`, `limit?` (default 50, max 200), `cursor?` | `200 {"items":[{"employee_id","name","date","clock_in","clock_out","status","flags","source"}],"next_cursor": "..."|null}` |
| `GET /api/admin/reports` | admin | reports (B) | query: `type=daily|weekly`, `period` (`YYYY-MM-DD` or `YYYY-Www`) | `200 {"summary": <report json>, "csv_url": "<pre-signed GET, 300 s>"}`; `404` if not generated |
| `POST /api/admin/attendance/override` | admin | override (B) | `{employee_id,date,clock_in?,clock_out?,status?,reason}` (`reason` required) | `200 attendance record`; writes audit row; `source="admin"` |
| `GET /api/admin/settings` / `PUT /api/admin/settings` | admin | settings (B) | PUT body: any subset of settings keys | `200 settings` |

Terraform routes: each module outputs `api_routes`, a map `"METHOD /path" => { function_name, invoke_arn, group }`; the `access` module builds API Gateway routes, integrations and Lambda permissions from the merged map. This is the only wiring between Parts and the API.

## 8. Report schemas
**Daily** `reports/daily/YYYY-MM-DD.json`:
`{"date","generated_at","skipped": null|"weekend"|"holiday","totals":{"employees","present","late","absent","missing_clock_out"},"records":[{"employee_id","name","status","clock_in","clock_out","flags"}]}`

**Weekly** `reports/weekly/YYYY-Www.json`:
`{"week","from","to","working_days","generated_at","employees":[{"employee_id","name","present_days","late_days","absent_days","present_pct","late_pct","absent_pct"}],"totals":{"present_pct","late_pct","absent_pct"}}`
Definitions: `present_days` = days with a clock-in (present + late); `late_days` = subset that were late; `present_pct = present_days / working_days * 100`, `late_pct = late_days / working_days * 100`, `absent_pct = absent_days / working_days * 100`, rounded to 1 decimal. `working_days` = Mon-Sun days of that week that are not weekend or holiday.

CSV columns: daily `employee_id,name,date,status,clock_in,clock_out,flags`; weekly `employee_id,name,present_days,late_days,absent_days,present_pct,late_pct,absent_pct`.

## 9. Rekognition parameters
Scan: `DetectFaces` (must find exactly 1 face; Brightness and Sharpness at or above settings minimums) then `SearchFacesByImage` with `FaceMatchThreshold=settings.face_match_threshold`, `MaxFaces=1`, `QualityFilter="AUTO"`; matched `ExternalImageId` = `employee_id`. Enroll: `IndexFaces` with `MaxFaces=1`, `QualityFilter="AUTO"`, `ExternalImageId=employee_id`. The S3 client used for pre-signing must be created with `region_name="ap-south-1"` and `signature_version="s3v4"`.

## 10. Manual and scheduled invocation events
`daily-job`: `{}` (uses today IST) or `{"date": "YYYY-MM-DD"}` for a re-run. `weekly-job`: `{}` (previous ISO week) or `{"week": "YYYY-Www"}`. `recognize`: `{"warmup": true}` returns immediately without touching AWS services (keep-warm schedule, SHOULD). Scheduler schedules: `attendance-{env}-daily` cron `59 23 * * ? *`, `attendance-{env}-weekly` cron `30 0 ? * MON *`, both with timezone `Asia/Kolkata`.

## 11. Frontend runtime config (Part C)
Terraform uploads `/config.json` to the web bucket: `{"region":"ap-south-1","userPoolId","clientId","cognitoDomain","apiBase":"/api","rawBucketUrl":"https://<raw bucket>.s3.ap-south-1.amazonaws.com"}`. Kiosk lives at `/`, admin at `/admin/`, shared OAuth callback at `/callback.html`. `config.json` and `*.html` are served with `Cache-Control: no-cache`.


## 12. Internal retry metadata (additive implementation detail)
The frozen API response shapes and result-code vocabulary are unchanged. The following additive DynamoDB attributes support exactly-once attendance effects and recoverable enrollment:
- Attendance `scan_events` stores the outcome for each request ID atomically with its clock-in/clock-out transition. A repeated request ID returns the stored outcome.
- Employee `enrollment_{request_id}` stores the FaceId committed for that enrollment request. It prevents a retry after employee persistence from incrementing `photo_count` or appending the same FaceId again.
- Employee `enrollment_lock_request` and `enrollment_lock_until` serialize concurrent enrollment attempts for one employee. The 90-second lease is reclaimed by the same request or after expiry.
- Recognition and enrollment workers preserve pending results and raw images on retryable exceptions. Lambda asynchronous failure destinations feed the per-worker SQS queues; the internal `failure` Lambda converts exhausted failures to `error` and deletes the image. Its own unprocessable messages go to the processor DLQ and raise a separate alarm.
