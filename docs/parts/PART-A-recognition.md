# Part A: Recognition Engine

**Owner:** ______  **Folders you own:** `services/recognition/*`, `infra/modules/recognition/`
**Read first:** SPEC (F01 F03 F05 F06 F12, N01 N02 N10), contracts sections 1, 3, 4, 6, 7, 9, 10.

## Mission
Turn "an image landed in S3" into "a correct, safe, fast recognition result", and never keep the image. You provide six Lambdas: `presign`, `result`, `recognize`, `enroll`, `enroll-url`, `faces-delete`, plus the Rekognition collection, S3 triggers, DLQ and IAM for them.

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
7. Call `record_scan(employee_id, now_ist(), similarity)`.
8. Update the scan-results row **only if `code = pending`** (conditional write): set `code=matched`, `action`, `name`, `time`, `status`, `message`. *Why:* S3 events can be delivered twice; this makes a second delivery a no-op.
9. **finally:** always `DeleteObject` the image (ignore "not found").
10. On unexpected exceptions: write `code=error` (conditional), log the exception without payloads, delete the image in `finally`, then re-raise so the Errors alarm and DLQ fire. *Why:* the retry finds `code != pending` and does nothing.
`message` examples: "Welcome, Priya. Clocked in at 09:14." / "Already clocked in at 09:14." / "Face not recognised. Please try again."

**5. `enroll-url` Lambda.** Verify the employee exists; create row `{kind: enroll, code: pending}`; pre-signed POST for `enroll/{employee_id}/{request_id}.jpg` (same limits).

**6. `enroll` Lambda** (512 MB, 15 s, reserved concurrency 5). Triggered by `enroll/`. Parse `employee_id` and `request_id` from the key. Checks in order: employee exists and `active` else `unknown_employee`; `photo_count` below `max_photos_per_employee` else `limit_reached`; `DetectFaces` for `no_face` / `multiple_faces` / `low_quality`; (SHOULD) `SearchFacesByImage` at the match threshold, and if it hits a **different** `employee_id` return `duplicate_face`; then `IndexFaces` (MaxFaces 1, QualityFilter AUTO, `ExternalImageId=employee_id`); update employees `face_ids` (append), `photo_count` (+1), `updated_at`; set `code=enrolled`. Always delete the image in `finally`.

**7. `faces-delete` Lambda.** Read `face_ids` from the employee; `DeleteFaces` in batches; set `face_ids=[]`, `photo_count=0`; write an audit row (`action=faces_delete`, `actor` from `auth.get_username`). Return `{"deleted": N}`.

**8. Keep-warm (SHOULD).** Scheduler schedule `attendance-{env}-recognize-warm`, every 5 min, 08:00-20:00 IST, payload `{"warmup": true}`.

**9. Terraform module `infra/modules/recognition`.** Inputs: `env`, `account_id`, `kms_key_arn`, `raw_bucket_name`, `raw_bucket_arn`, `tables` (names + arns), `layer_arn`, `alerts_topic_arn`, `common_env`. Outputs: `api_routes` (4 routes), `collection_id`, `recognize_function_name`. One role per Lambda following the IAM matrix in ARCHITECTURE 6.1 exactly. S3 notification for **both** prefixes defined here, with `aws_lambda_permission` for S3. DLQ (SQS, KMS-encrypted) for `recognize` and `enroll`, CloudWatch log groups with 30-day retention, alarms on Errors and DLQ depth.

## Tests you must write (`tests/unit/test_recognition_*.py`)
Use moto for S3 and DynamoDB; mock Rekognition (`unittest.mock` or botocore Stubber).
- presign: row created pending; fields/conditions correct; key = `captures/{id}.jpg`.
- recognize: matched (calls record_scan with right args), no_face, multiple_faces, low_quality, no_match, inactive, missing employee, duplicate event is a no-op, image always deleted (including on exception), warmup returns fast.
- enroll: every enroll code; photo_count increments; image deleted.
- faces-delete: clears fields, writes audit.
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
