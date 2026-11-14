# Technical Design Document

Serverless Face-Recognition Attendance System. Version 1.0 (11 Nov 2026). Companion docs: [SPEC](SPEC.md), [contracts](contracts.md), [COST](COST.md).

## 1. Context and goals
Replace swipe cards and paper registers with contactless face-based clock-in/out for about 100 employees. Goals: result on screen within 3 s; no biometric images retained; least-privilege security; low, predictable cost; fully reproducible infrastructure; operable by a small team.
Non-goals (v1): liveness detection, multi-site, payroll integration.

## 2. Architecture diagram
See the diagram in [README.md](../README.md). Export it as PNG (mermaid.live) for the PDF version of this document.

## 3. Scan sequence
```mermaid
sequenceDiagram
  participant K as Kiosk (browser)
  participant API as CloudFront + API GW
  participant P as presign Lambda
  participant S3 as S3 raw bucket
  participant R as recognize Lambda
  participant RK as Rekognition
  participant D as DynamoDB
  K->>API: POST /api/kiosk/upload-url (Bearer token)
  API->>P: invoke
  P->>D: put scan-results {request_id, code=pending}
  P-->>K: request_id + pre-signed POST
  K->>S3: POST image (captures/request_id.jpg)
  S3-->>R: ObjectCreated event
  R->>RK: DetectFaces, then SearchFacesByImage
  R->>D: get employee, record_scan (attendance), update scan-results
  R->>S3: delete image
  loop every 500 ms, max 8 s
    K->>API: GET /api/kiosk/result/request_id
    API-->>K: pending, then matched/no_match/...
  end
```
Latency budget (target p95 under 3 s): client resize + upload about 0.5 s, S3 event about 0.3 s, Lambda warm about 0.1 s, Rekognition two calls about 0.8 s, DynamoDB about 0.1 s, poll interval up to 0.5 s.

## 4. Components
| Component | Tech | Part |
|---|---|---|
| Kiosk and admin web apps | static HTML/JS on S3 behind CloudFront (OAC) | C |
| Auth | Cognito user pool, Hosted UI + PKCE, groups `admin`, `kiosk` | C |
| API | API Gateway HTTP API, JWT authorizer, routes built from module outputs | C |
| Recognition | presign, result, recognize, enroll, enroll-url, faces-delete and internal failure-recovery Lambdas; Rekognition collection; encrypted SQS recovery queues | A |
| Data and automation | 5 DynamoDB tables, employees/attendance-query/reports/override/settings Lambdas, daily-job, weekly-job, EventBridge Scheduler | B |
| Platform | KMS, buckets, layer, SNS, alarms, budgets, CI/CD, bootstrap | Lead |

## 5. Data model
Defined in [contracts.md](contracts.md) section 3. Access patterns: by employee over a date range (PK query), by date for all employees (GSI `date-index`), employee list (about 100 items; Scan is acceptable at this scale), result polling by `request_id` (TTL 1 day).

## 6. Security
### 6.1 IAM matrix (one role per Lambda; all also get CloudWatch Logs on their own log group and `kms:Decrypt`/`kms:GenerateDataKey` on the attendance KMS key)
| Lambda | Allowed actions and resources |
|---|---|
| presign | `s3:PutObject` on raw `captures/*`; `dynamodb:PutItem` on scan-results |
| result | `dynamodb:GetItem` on scan-results |
| recognize | `rekognition:DetectFaces`; `rekognition:SearchFacesByImage` on the collection; `s3:GetObject`, `s3:DeleteObject` on raw `captures/*`; `dynamodb:GetItem` employees + config; `GetItem`/`PutItem`/`UpdateItem` attendance; `GetItem`/`UpdateItem` scan-results; `sqs:SendMessage` on its DLQ |
| enroll | `rekognition:DetectFaces`; `IndexFaces`, `SearchFacesByImage`, `DeleteFaces` on the collection; `s3:GetObject`, `s3:DeleteObject` on raw `enroll/*`; `dynamodb:GetItem`/`UpdateItem` employees; `GetItem` config; `GetItem`/`UpdateItem` scan-results; DLQ send |
| enroll-url | `s3:PutObject` on raw `enroll/*`; `dynamodb:GetItem` employees; `PutItem` scan-results |
| faces-delete | `rekognition:DeleteFaces` on the collection; `dynamodb:GetItem`/`UpdateItem` employees; `PutItem` audit; only for inactive employees |
| failure | `sqs:ReceiveMessage`/`DeleteMessage`/`GetQueueAttributes`/`ChangeMessageVisibility` on recognition/enrollment DLQs; `dynamodb:GetItem`/`UpdateItem` scan-results + employees; `dynamodb:Query` attendance + date-index; `rekognition:SearchFacesByImage`/`DeleteFaces` on collection; `s3:GetObject`/`DeleteObject` raw captures/enroll prefixes |
| employees | `dynamodb:GetItem`/`PutItem`/`UpdateItem`/`Scan` employees; `PutItem` audit |
| attendance-query | `dynamodb:Query` attendance and `attendance/index/date-index`; `Scan` employees |
| reports | `s3:GetObject` on reports `reports/*` |
| override | `dynamodb:GetItem` employees; `GetItem`/`UpdateItem`/`PutItem` attendance; `PutItem` audit |
| settings | `dynamodb:GetItem`/`PutItem`/`UpdateItem` config; `PutItem` audit |
| daily-job | `dynamodb:Scan` employees; `Query` attendance and `attendance/index/date-index`; `PutItem`/`UpdateItem` attendance; `GetItem` config; `s3:PutObject` reports `reports/daily/*`; `sns:Publish` alerts topic |
| weekly-job | `dynamodb:Scan` employees; `Query` attendance (+ index); `GetItem` config; `s3:PutObject` reports `reports/weekly/*`; `sns:Publish` alerts topic |
`rekognition:DetectFaces` does not support resource-level permissions, so `*` is acceptable only for that one action. `daily-job` needs `dynamodb:UpdateItem` on attendance to add the `missing_clock_out` flag after checking a clock-in without a clock-out. `enroll` needs `rekognition:DeleteFaces` on the collection to roll back a face index if the conditional employee update fails.

### 6.2 Controls
- Encryption at rest: DynamoDB (KMS), S3 (SSE-KMS with bucket key), CloudWatch logs contain no biometric images, tokens or full face data; Lambda logs use JSON format with 30-day retention. TLS enforced by bucket policies (`aws:SecureTransport`) and CloudFront (redirect to HTTPS, TLS 1.2+).
- Raw bucket: Block Public Access, no versioning. Workers delete images after a durable terminal result; retryable failures retain images while Lambda retries. The failure consumer reconciles already-committed attendance/enrollment writes, removes an uncommitted request-scoped face template, finalizes exhausted requests and deletes the image. Lifecycle expires `captures/` and `enroll/` after 1 day (S3 minimum granularity) as a backstop, plus incomplete multipart uploads. Reports bucket: versioning on (audit trail). Web bucket: private, CloudFront OAC only.
- Pre-signed POST: 60 s expiry, JPEG only, 1 KB to 1 MB, key fixed by server.
- API: Cognito JWT authorizer on every route + group check in the Lambda; API Gateway throttling (10 req/s, burst 20 per stage); Lambda reserved concurrency caps on `recognize` and `enroll` to bound Rekognition spend.
- Response headers on CloudFront: HSTS, CSP (self + S3 regional endpoint + Cognito domain), `X-Content-Type-Options`, `Permissions-Policy: camera=(self)`.
- Secrets: none in code. CI uses GitHub OIDC; no long-lived AWS keys.

### 6.3 Threat model (summary)
| Threat | Mitigation | Residual risk |
|---|---|---|
| Photo/video of an employee shown to the camera | Strict threshold, supervised kiosk, audit trail | Real in v1; fix is Face Liveness (LATER) |
| Someone abuses upload endpoint | Auth required, pre-signed POST limits, throttling, concurrency cap, budget alarm | Low |
| Stolen kiosk token | Dedicated `kiosk` user with kiosk-only routes and 60 min access tokens; disabling blocks new auth/refresh but already-issued JWTs remain valid until expiry (up to 60 min) | Medium (device theft) |
| Biometric data leak | Raw images are retained only for the bounded retry/recovery window, then deleted; only Rekognition feature vectors remain for enrolled employees; KMS, least privilege and offboarding deletion | Low |
| Admin misuse | Cognito admin group, override requires reason and is audited | Low |
| Cost attack | Throttling, reserved concurrency, AWS Budget alarm | Low |
### 6.4 Privacy and compliance
Biometric data is personal data (India DPDP Act 2023 applies). Controls: explicit consent captured at enrollment (`consent_at`), purpose limitation (attendance only), no retention of raw images, deletion of faces on offboarding (the API refuses to delete while the employee is active), access limited to admins. Have HR/mentor confirm the consent text. This is engineering guidance, not legal advice.

## 7. Reliability and failure modes
| Failure | Behaviour |
|---|---|
| Duplicate S3 event | Attendance transition is idempotent by `request_id`; the exact outcome is stored atomically in `attendance.scan_events`. Terminal result updates are conditional; duplicate deliveries only repeat safe image cleanup |
| Retryable Rekognition/DynamoDB error | Worker leaves the result `pending`, retains the image and raises. Lambda asynchronous invocation retries twice, with a maximum event age of 10 minutes |
| Exhausted recognition retries | Failure consumer queries attendance by IST date and request ID. If the attendance write committed, it repairs the result to `matched`; otherwise it marks `error`. It then deletes the raw image |
| Exhausted enrollment retries | If the employee request marker exists, the consumer repairs the result to `enrolled`; otherwise it searches for and deletes any FaceId tagged with that exact request ID, marks `error`, and deletes the image |
| Failure consumer cannot process a message | SQS retries it five times, then moves it to the separately alarmed failure-processor DLQ |
| Image already deleted when event retried | Terminal result is left unchanged; repeated `DeleteObject` is safe. If the request is still pending, it is finalized as an error |
| Cold start | Keep-warm schedule (SHOULD) during 08:00-20:00 IST every 5 min; small zip, 512 MB memory |
| Browser never gets a result | UI times out at 8 s, shows "try again" (nothing is lost; user can rescan) |
| Daily job fails midway | Idempotent conditional puts: re-run with `{"date": ...}`; SNS alert on error |
| Bad deploy | `git revert` on `main`, pipeline redeploys; DynamoDB PITR for data mistakes |

## 8. Observability
Structured JSON logs (30-day retention); alarms to SNS `attendance-{env}-alerts` (email lead): Lambda `Errors` > 0 on any function, `Throttles` > 0, DLQ `ApproximateNumberOfMessagesVisible` > 0, `recognize` p95 `Duration` > 2500 ms, job failures; AWS Budget 15 USD (80% and 100%). CloudWatch metrics and alarms are provisioned; a custom dashboard (scans per hour, p95 latency, error counts, Rekognition calls) is deferred and is not part of the current Terraform build.

## 9. Cost
See [COST.md](COST.md). About 10 to 14 USD per month at 100 employees x 2 scans/day.

## 10. Decision log
| # | Decision | Why |
|---|---|---|
| D1 | Terraform with one module per Part | Module inputs/outputs are a typed integration contract; parts cannot step on each other |
| D2 | One CloudFront domain for web and `/api/*` | HTTPS (webcam needs it), no CORS for API, one URL |
| D3 | Two S3 buckets for data (raw, reports) | Versioning would silently keep "deleted" biometric images; audit trail goes on reports only |
| D4 | Delete raw image in code, lifecycle only as backstop | Lifecycle cannot do 1 hour (1-day minimum) |
| D5 | Poll a results table | S3 to Lambda is async; polling is simple and robust inside 3 s |
| D6 | `record_scan` as a shared layer library | Avoids Lambda-to-Lambda call latency and cold start |
| D7 | EventBridge Scheduler with timezone | Rule cron is UTC only |
| D8 | Pre-signed POST, not PUT | Server-enforced size and content-type limits |
| D9 | Cognito Hosted UI + PKCE + groups | No custom login code, MFA ready later |
| D10 | Thresholds in config table | Tune accuracy without redeploy |
| D11 | Single region us-east-1 | Existing deployment target and verified service/IAM policy alignment; one region keeps resource, identity and signing endpoints consistent |
| D12 | Liveness deferred | Time; risk documented, mitigations listed |

## 11. Deployment

The deployment is approval-gated and is not yet executed. The target is AWS account `924422830139`, region `us-east-1`. The solo release is maintained on `solo/amit-monday`; only after the readiness gates pass should it be promoted by PR to `develop` for dev and later `main` for production.

1. **Read-only inventory:** confirm STS identity and inspect the existing OIDC provider, state bucket, runtime boundaries, six deployment roles and policy attachments. On 14 November 2026, STS verified account `924422830139`; the read-only preflight found no matching state bucket and returned `NoSuchEntity` for the expected OIDC provider and roles. Any result affected by missing read permissions remains unconfirmed.
2. **Bootstrap plan:** choose a globally unique `attendance-tf-state-924422830139-<approved-suffix>` bucket name. Render the exact bucket configuration/policy, OIDC trust documents, two runtime boundaries, six plan/apply roles and 26 managed policy templates. Present all changes and permissions to the owner. No AWS write is allowed before explicit approval.
3. **GitHub governance:** configure six exact environments: `dev-plan`, `dev-apply`, `prod-plan`, `prod-apply`, `billing-plan`, `billing-apply`. Restrict dev to `develop`; prod and billing to `main`. The repository owner is the sole apply reviewer and self-review is allowed. This is a manual owner checkpoint, not independent approval. Use `scripts/configure_github_environments.sh` and `scripts/configure_branch_protection.sh` in dry-run mode first.
4. **AWS bootstrap:** after a separate explicit approval, create only approved missing resources. Verify all resource ARNs, trust relationships, policies and bucket controls using read-only calls.
5. **Dev plan and apply:** approve remote backend initialization separately. Run the dev plan from `develop`, inspect the complete saved plan and cost, then obtain separate explicit approval before applying that exact encrypted plan artifact.
6. **First deployment URL/CORS update:** the first apply uses localhost callback/logout URLs and raw-bucket allowed origins to avoid a Terraform dependency cycle. After CloudFront is created, add the exact HTTPS site origin to `COGNITO_CALLBACK_URLS`, `COGNITO_LOGOUT_URLS` and `ALLOWED_ORIGINS` in the dev apply environment variables. Repeat with the production CloudFront origin only during the separately approved production release. Run a second reviewed plan and separately approved apply.
7. **Cognito user bootstrap:** Terraform creates the user pool and the `admin` and `kiosk` groups, but it does not create users. Create the first administrator in the Cognito console and add the account to the `admin` group. Create a dedicated kiosk account and add it to `kiosk`. Public self-registration is disabled.
8. **Alerts:** confirm the SNS email subscription and any AWS Budget notification email from the inbox. An unconfirmed SNS subscription will not deliver alarms.
9. **Dev acceptance:** run consent-based enrollment and scan tests, validate clock-in/clock-out/debounce, daily/weekly jobs, reports, offboarding, raw-image deletion, alarms, cost, browser camera behaviour and p95 capture-to-result timing. The existing API smoke test does not replace browser/device testing.
10. **Production:** only after dev acceptance, promote the approved release to `main`, run a separate production plan, review it, and obtain a separate explicit apply approval. Billing remains on its isolated root and role pair.

## 12. Operations runbook
| Task | How |
|---|---|
| Add employee | Admin app, Add employee, capture 3-5 photos, wait for "enrolled" |
| Offboard | Admin app, Deactivate (sets inactive and deletes faces) |
| Tune accuracy | Admin app Settings (or config table item `SETTINGS`): `face_match_threshold` |
| Re-run daily/weekly job | Console, Lambda, Test with `{"date": "YYYY-MM-DD"}` / `{"week": "YYYY-Www"}` |
| Disable a kiosk | Cognito, disable user `kiosk-01`; already-issued access JWTs may remain valid for up to 60 minutes |
| Roll back | Revert commit on `main`, run a new manual plan, review it, then apply through the protected `prod` environment |
| Restore data | DynamoDB point-in-time restore to a new table, then swap |

## 13. Limitations and future work
Face Liveness, admin MFA, custom domain, SES email reports, shift templates and leave management, multi-region. See SPEC section 8.
