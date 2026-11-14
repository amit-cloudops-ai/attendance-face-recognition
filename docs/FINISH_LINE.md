# Monday Finish Line — 16 November 2026

This document controls the mentor-demo sprint. Where the 11 Nov SPEC, ARCHITECTURE or README conflicts with this sprint plan, this document controls. Frozen API/data contracts remain in docs/contracts.md.

## Release claim
Only claim what has been demonstrated: a deployed serverless face-attendance prototype with authenticated kiosk/admin paths, encrypted storage, least-privilege access, attendance automation, tests, monitoring and a documented hardening roadmap. Do not claim liveness detection, multi-region HA, enterprise readiness, a full multi-environment CI/CD pipeline, or any gate without evidence.

## Gate — pass/fail
| Gate | Acceptance | Evidence |
|---|---|---|
| G1 | HTTPS kiosk camera preview, capture, upload, poll, and show employee/time/status | Screen recording + timings |
| G2 | Admin creates employee and enrolls 3+ varied photos; uploaded images deleted | Recording + S3 prefixes empty |
| G3 | First scan clocks in; present/late uses shift and grace; rapid repeat ignored; later scan after debounce clocks out | DynamoDB record + tests |
| G4 | Unknown face returns no_match and writes no attendance | Test + recording |
| G5 | Cognito admin login; filter attendance by employee/date/status | Recording |
| G6 | Idempotent daily absence job and daily/weekly reports on IST schedule | Tests + report objects + schedule config |
| G7 | Raw images deleted; 1-day lifecycle backstop; reports bucket versioned; buckets private | S3 evidence |
| G8 | DynamoDB encrypted; per-Lambda least privilege; Cognito authorization on protected routes | IAM/API evidence |
| G9 | Clean checkout can run SAM build/deploy | Build/deploy transcript |
| G10 | CI passes pytest, ruff, cfn-lint/SAM validation | Actions evidence |
| G11 | Lambda error and budget alarms; documented cost estimate | Alarm/budget evidence + cost sheet |
| G12 | Architecture, deployment guide, cost sheet, demo script/video | Files + video |
| G13 | At least two pilot users enrolled and have clocked in/out | Redacted attendance evidence |

Code inspection alone does not satisfy a gate requiring live AWS or human evidence.

## Architecture and scope decisions
- Monday infrastructure source of truth: one AWS SAM/CloudFormation template, `template.yaml`; Terraform is deferred for this sprint.
- One demo environment in ap-south-1. Deploy only from Amit's machine/account after his explicit approval.
- Keep frozen routes, request/response shapes, result codes, schemas and resource environment-variable conventions in docs/contracts.md unchanged unless Amit explicitly approves and documents a contract revision.
- Sprint encryption target: DynamoDB encryption and S3 SSE-S3; customer-managed KMS is deferred.
- Python 3.12, boto3-only Lambda runtime unless explicitly approved.
- The original Terraform architecture remains long-term reference only; do not mix Terraform and SAM deployment workflows.

## Cut order
Cut visual polish/settings/override UI/CSV export first; then weekly CSV (keep JSON), keep-warm and DLQ only if a safe error path remains. Do not fake or silently skip recognition, clock-in/out semantics, unknown-face behavior, authorization, image deletion, daily-job idempotency, reproducible build, or evidence.

## Timeline
- Sat 14 Nov: controls, branch setup, readiness checks.
- Sun 15 Nov: integration, test, deployment candidate (AWS deployment only after explicit approval).
- Sun 15 Nov 21:00 IST: code freeze; after this only gate-blocking fixes.
- Mon 16 Nov: rehearse once, verify live URL and fallback materials, then demo.

## Limitations to state openly
Still-photo spoofing is possible without liveness detection. Accuracy depends on camera, lighting and enrollment quality. A single-region demo is not a certified biometric/payroll system. Obtain valid organizational consent and review privacy, retention, deletion and access practices before real employee use.
