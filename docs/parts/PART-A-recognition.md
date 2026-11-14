# Part A: Recognition Engine

**Owner:** ______  **Folders you own:** `services/recognition/*`, `infra/modules/recognition/`
**Read first:** SPEC (F01 F03 F05 F06 F12, N01 N02 N10), contracts sections 1, 3, 4, 6, 7, 9, 10.

## Mission
Turn "an image landed in S3" into "a correct, safe, fast recognition result", and never keep the image. You provide seven Lambdas: `presign`, `result`, `recognize`, `enroll`, `enroll-url`, `faces-delete`, and the internal `failure` recovery worker, plus the Rekognition collection, S3 triggers, failure queues and IAM for them.

## You depend on / provide
- From Lead: layer `attendance_common` (`tz`, `config.get_settings`, `responses`), KMS key, buckets, SNS topic, common env vars.
- From Part B: `record_scan` (stub it in your tests; the real one arrives via the layer).
- You provide: `api_routes` output for your 4 API Lambdas; image-triggered Lambdas have no route.

## Build steps (with why)
**1. Collection.** Terraform resource for the Rekognition collection `attendance-{env}-faces` (if your provider version lacks it, create it once in CloudShell with `create-collection` and import/data-source it). *Why:* the collection holds face vectors, not photos.

**2. `presign` Lambda** (256 MB, 5 s). Generate `request_id` (uuid4); write scan-results row `{kind: scan, code: pending, created_at, ttl}`; create a pre-signed **POST** for `captures/{request_id}.jpg` with conditions: `Content-Type = image/jpeg`, `content-length-range 1024..1048576`, expiry 60 s. Create the S3 client with `region_name="ap-south-1"` and `signature_version="s3v4"`. Return the contract shape. *Why:* POST lets the server enforce size/type; the regional client avoids redirect/CORS failures on new buckets.

**3. `result` Lambda** (128 MB). `GetItem` scan-results by `request_id` from the path; 404 `not_found` if missing; return the contract shape. Strip internal fields. *Why:* the browser polls this every 500 ms, so keep it tiny.

**4. `recognize` Lambda** (512 MB, 15 s, reserved concurrency 10). Triggered by S3 `captures/`.
1. If the event is `{"warmup": true}`, return immediately.
2. For each record: parse `request_id` from the key.
3. Load settings (`get_settings()`).
4. **try:** `DetectFaces` on the S3 object. 0 faces to `no_face`; more than 1 to `multiple_faces`; Brightness or Sharpness below settings minimums to `low_quality`.
5. `SearchFacesByImage` (threshold from settings, MaxFaces 1, QualityFilter AUTO). No match to `no_match`.
6. `ExternalImageId` is the `employee_id`: load the employee. Missing record to `no_match` (log a warning). `active=false` to `inactive`.
7. Call `record_scan(employee_id, captured_at, similarity, request_id=request_id)`. The original `created_at` written by `presign` is the timestamp for the scan; do not use the worker's current time.
8. Update the scan-results row **only if `code = pending`** (conditional write): set `code=matched`, `action`, `name`, `time`, `status`, `message`.
9. Delete the image only after the terminal result is durable. If the result write or image deletion fails, raise; a retry sees the terminal result and repeats only the safe delete.
10. On unexpected infrastructure exceptions, leave `code=pending`, retain the raw image and re-raise. Lambda retries twice, with a maximum asynchronous event age of 10 minutes. Only after retries are exhausted does the async failure destination invoke the SQS recovery path, which marks the request `error` and deletes the image. *Why:* a transient AWS failure must not become a terminal user-visible failure before retries have been attempted.
`message` examples: "Welcome, Priya. Clocked in at 09:14." / "Already clocked in at 09:14." / "Face not recognised. Please try again."

**5. `enroll-url` Lambda.** Verify the employee exists; create row `{kind: enroll, code: pending}`; pre-signed POST for `enroll/{employee_id}/{request_id}.jpg` (same limits).

**6. `enroll` Lambda** (512 MB, 15 s, reserved concurrency 5). Triggered by `enroll/`. Parse `employee_id` and `request_id` from the key. Check the employee exists and is active; if the employee is missing/inactive or the photo limit is reached, remove any orphan face tagged with this exact request before returning a terminal result. Otherwise acquire a 45-second per-employee lease. Check the photo limit; run `DetectFaces` for `no_face` / `multiple_faces` / `low_quality`; run `SearchFacesByImage` at the match threshold and return `duplicate_face` if a different employee owns the match. Before indexing, search results are checked for a FaceId whose ExternalImageId exactly matches `employee_id#request_id`; reuse it when found, otherwise call `IndexFaces`. Persist the FaceId, increment `photo_count`, and write the request-specific `enrollment_{request_id}` marker in one conditional employee update while releasing the lease. Then set `code=enrolled`. The marker lets a retry finish result persistence without indexing or incrementing again. Delete the image only after a durable terminal result; unexpected exceptions preserve the image and remain retryable.

**7. `faces-delete` Lambda.** Requires the employee to be inactive (the admin UI deactivates first). Delete all face IDs in Rekognition batches and verify every ID is deleted or already absent; do not clear the employee record on partial failure. Write a deterministic audit record before the conditional employee update, then set `face_ids=[]`, `photo_count=0` and persist the audit marker. This makes retries safe if Rekognition deletion, audit persistence or the employee update fails. Return `{"deleted": N}`.

**8. Keep-warm (SHOULD).** Scheduler schedule `attendance-{env}-recognize-warm`, every 5 min, 08:00-20:00 IST, payload `{"warmup": true}`.

**9. Terraform module `infra/modules/recognition`.** It also creates the internal failure worker, consumes both async failure queues, and routes poison recovery messages to a separately alarmed processor DLQ. Inputs: `env`, `account_id`, `kms_key_arn`, `raw_bucket_name`, `raw_bucket_arn`, `tables` (names + arns), `layer_arn`, `alerts_topic_arn`, `common_env`. Outputs: `api_routes` (4 routes), `collection_id`, `recognize_function_name`. One role per Lambda following the IAM matrix in ARCHITECTURE 6.1 exactly. S3 notification for **both** prefixes defined here, with `aws_lambda_permission` for S3. DLQ (SQS, KMS-encrypted) for `recognize` and `enroll`, CloudWatch log groups with 30-day retention, alarms on Errors and DLQ depth.

## Tests you must write (`tests/unit/test_recognition_*.py`)
Use moto for S3 and DynamoDB; mock Rekognition (`unittest.mock` or botocore Stubber).
- presign: row created pending; fields/conditions correct; key = `captures/{id}.jpg`.
- recognize: matched (uses the original request timestamp and request ID), no_face, multiple_faces, low_quality, no_match, inactive, missing employee, duplicate event, transient exception remains pending and retains image, terminal duplicate delivery only cleans up, warmup returns fast.
- failure worker: converts exhausted async failures to terminal error, deletes capture/enrollment images, preserves already-terminal outcomes, and returns malformed SQS records for retry.
- enroll: every enroll code; request marker prevents double increment after result-write failure; lease serializes concurrent attempts; transient exception remains pending and retains image.
- failure worker: handles both capture and enrollment event envelopes and partial batch failures; repairs committed outcomes and compensates exact request-scoped orphan face IDs.
- faces-delete: rejects active employees, verifies complete Rekognition deletion, handles already-missing IDs, and keeps the audit/update retry-safe.
- contract test: scan-results items you write have exactly the contract attributes and a `ttl`.

## Accuracy work (Day 3 to 4)
Enroll each teammate with 4 photos (different light/angles). Run 20 scans per person. Record false rejects and any false accept in STATUS. Default threshold 95; raise toward 99 if any false accept appears; never go below 90. *Why:* a false accept (clocking in as someone else) is far worse than a false reject.

## Pitfalls
- S3 triggers require the Lambda permission and the notification to be created in the right order (`depends_on`).
- Rekognition reading an SSE-KMS object uses your role: it needs `kms:Decrypt`.
- Only this module defines the raw-bucket notification; two definitions overwrite each other.
- Do not log images, bounding boxes with faces, or tokens.
- Presigned POST: the browser must send `file` as the LAST form field (tell Part C).

## Done when
- [ ] All unit + contract tests green in CI
- [ ] On dev: enroll a person (3 photos) then scan: `matched`; stranger: `no_match`; two faces: `multiple_faces`
- [ ] `captures/` and `enroll/` are empty 10 min after tests
- [ ] p95 scan latency 3 s or less on 20 warm scans (numbers in STATUS)
- [ ] IAM matches the matrix; alarms created; DLQ tested once


## Reliability hardening (solo implementation)
- The attendance helper accepts an optional UUID v4 `request_id`. For recognition it is mandatory. Its outcome is stored under `attendance.scan_events[request_id]` in the same conditional attendance write, so a replay cannot turn the original clock-in into a clock-out.
- Presign `created_at` is the authoritative capture request timestamp. Worker retries must not substitute invocation time.
- Retryable exceptions never set `error` in the recognition/enrollment workers and never delete the source image.
- The internal `failure` Lambda consumes the async on-failure SQS destinations and first reconciles durable side effects: it repairs a scan result from `attendance.scan_events[request_id]`, repairs an enrollment result from the employee's `enrollment_{request_id}` marker, or deletes an orphan Rekognition face tagged with that exact enrollment request. It marks only uncommitted work `error`, then removes the image. Its own unprocessable messages move to a processor DLQ after five receives; that queue has a CloudWatch alarm.
- Biometric images remain in the private raw bucket only while retries/recovery are possible; the existing one-day lifecycle rule is the final backstop.
