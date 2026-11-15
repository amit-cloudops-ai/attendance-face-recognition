# Operations runbook

**Applies to:** the attendance face-recognition system after an approved dev deployment. This is an operating procedure, not authorization to make AWS changes.

## 1. Alert ownership and first response

CloudWatch alarms publish to the environment's SNS alert topic. Budget notifications are sent to the configured alert email. The operational owner and backup contact must be explicitly assigned before production; do not assume the repository owner is the on-call operator.

For every alert, record: environment, alarm name, UTC and IST timestamps, affected Lambda/queue/table, request IDs where available, impact, actions taken and final disposition. Do not include employee names, raw images, access tokens, FaceIds or biometric content in tickets or logs.

### Lambda Errors or Throttles

1. Identify the environment and function from the alarm name.
2. Inspect the function's CloudWatch log group and invocation metrics for the alert window.
3. Correlate using request IDs and exception class; do not copy request bodies or personal data into incident notes.
4. Check concurrency, timeout, downstream AWS service errors and recent deployment changes.
5. If a release caused the incident, stop further deployments and follow the rollback procedure below.
6. Verify successful invocations and that the alarm returns to OK before closing the incident.

Recognition and enrollment reserved concurrency are 10 and 5; the failure processor is 2. Daily and weekly jobs are limited to one concurrent execution each. Do not raise limits during an incident without checking Rekognition spend and downstream capacity.

### Recognition p95 duration

The recognition Lambda alarm threshold is p95 Duration greater than 2,500 ms over a one-minute period. Compare Lambda duration, cold starts, Rekognition calls, S3 event delay and DynamoDB latency. The 2,500 ms alarm is not proof of the end-to-end three-second browser target; the browser acceptance test must measure camera capture, upload, processing and rendering separately.

### API or browser failures

Check CloudFront/API Gateway access logs, Cognito authorizer errors, browser console/network failures and CORS/CSP configuration. Verify the site is served over HTTPS and camera permission is granted. Never weaken CSP or camera permissions as an incident workaround without a reviewed change.

## 2. Dead-letter queue handling

Recognition and enrollment failures first enter their respective encrypted SQS DLQs. The failure processor reconciles committed attendance/enrollment side effects, finalizes terminal results, and removes raw images. Its own poison messages enter the failure-processor DLQ.

When a DLQ-depth alarm fires:

1. Pause ad-hoc redrive. Record queue name, message count, oldest-message age and affected request IDs.
2. Inspect a small sample using an authorized operator identity. Treat message bodies as sensitive; do not paste them into chat or tickets.
3. Determine whether the request already committed an attendance transition or enrollment. Check the authoritative DynamoDB records and request-scoped idempotency markers before retrying.
4. For recognition, confirm `attendance.scan_events[request_id]` and scan-results before any redrive. For enrollment, check the employee's `enrollment_{request_id}` marker and request-tagged Rekognition face before any retry or deletion.
5. Fix the underlying cause first. Redrive only after confirming the handler is idempotent for the affected messages and the destination queue/permissions are healthy.
6. Verify terminal result codes, attendance/audit records and raw-image deletion. Record the redrive batch and message disposition.

Do not manually delete DLQ messages to silence an alarm. The failure-processor DLQ indicates the recovery mechanism itself failed and requires investigation before redrive.

## 3. Biometric privacy and offboarding

- Employee creation requires explicit consent. Do not enroll a person without recorded consent.
- Raw capture and enrollment images are deleted by workers after terminal processing. The one-day S3 lifecycle rule is a backstop, not the primary deletion mechanism.
- On offboarding, deactivate the employee, then invoke the faces deletion operation. Verify the employee is inactive, FaceIds/photo count are cleared, the audit record exists, and the API exposes only the safe `has_face_templates` indicator—not FaceIds.
- If deletion is partial, use the idempotent retry path and investigate the Rekognition collection and employee record. Do not reactivate the employee to make deletion succeed.
- For suspected biometric exposure, restrict access, disable affected kiosk/admin identities as appropriate, preserve audit evidence, and follow the organization's privacy/legal incident process. Do not destroy evidence or promise a legal outcome.

## 4. Budget and cost controls

The billing Terraform root defines separate monthly USD 15 cost budgets for dev and prod, with actual-cost notifications at 80% and 100%. Recognition concurrency limits and API throttling provide additional spend controls.

When a budget notification arrives:
1. Confirm environment, actual spend and billing period in AWS Cost Explorer/Budgets.
2. Inspect Rekognition usage, Lambda invocations, API requests, data transfer, CloudWatch logs and S3 storage/version growth.
3. Check for abnormal scans, repeated retries, leaked kiosk credentials or a growing DLQ.
4. Contain abusive access by disabling the relevant Cognito user or applying an approved rate/concurrency change.
5. Record the cost driver and corrective action. Do not raise the budget threshold to clear an alert.

Budget email delivery, SNS confirmation and alert routing must be tested in dev. The USD 15 figure is a guardrail, not a verified forecast or guaranteed spend ceiling.

## 5. Backup and restore

### Protected data

- All five DynamoDB tables have point-in-time recovery enabled.
- The reports S3 bucket is versioned.
- The Terraform state bucket is intended to be versioned and protected by all four S3 Block Public Access settings.
- The raw biometric bucket is intentionally not versioned so deletion is not defeated by retained object versions. Its lifecycle expiration is a one-day backstop.

### Restore procedure

1. Identify the affected environment, table/bucket, incident time and recovery point. Obtain approval before restoring or changing production data.
2. For DynamoDB, restore the selected point in time to a **new table**; do not overwrite the live table. Verify encryption, indexes, tags, TTL and item counts.
3. Validate restored data and application compatibility in isolation. Reconcile writes that occurred after the recovery point.
4. Prepare a reviewed Terraform/application cutover plan to point the application at the restored table. Apply only after explicit approval.
5. For reports, restore the required object version to a new key or recover it using an approved version-aware procedure. Do not remove other versions.
6. For Terraform state, preserve the bucket and all versions. Recover a previous state version only with a reviewed state-recovery procedure; never delete a lock object while Terraform may be running.
7. Record recovery point, duration, data loss window, verification results and approvals.

A restore has not yet been tested. Complete a dev restore drill and record the result before production readiness is approved. Raw biometric images are intentionally not recoverable after deletion.

## 6. Rollback

### Application or infrastructure release

1. Stop new deployment dispatches and identify the exact commit and plan run that introduced the issue.
2. Preserve logs, plan artifacts, state versions and incident evidence.
3. Select the last known-good commit. Create a reviewed rollback PR or release commit; do not force-push protected branches.
4. Generate a **new** Terraform plan from the rollback commit. Inspect every action, especially resource replacement/deletion, data retention, IAM and KMS policy changes.
5. Obtain independent approval and apply only that exact saved plan through the matching GitHub apply environment.
6. Run smoke, authentication, scan, report, deletion and alarm checks. Confirm no queued work or data inconsistency remains.

A code revert does not reverse DynamoDB writes, Rekognition face changes, S3 deletion or external side effects. Restore data separately when required.

### Emergency access containment

If an OIDC deployment role or GitHub environment is suspected compromised, suspend the relevant GitHub environment/deployment path and revoke or restrict the role trust/permissions through a separately approved security change. Preserve the state bucket and state versions. Do not delete the OIDC provider or state bucket as an emergency shortcut.

## 7. Scheduled jobs and routine checks

- Verify daily and weekly report generation and SNS notification delivery.
- Review Lambda error/throttle alarms and all three DLQ families.
- Review monthly budgets and unexpected Rekognition/API usage.
- Verify employee offboarding requests have no remaining FaceIds.
- Confirm S3 raw-image retention/deletion and DynamoDB PITR status.
- Review GitHub environment reviewers, branch restrictions and role trust after repository governance changes.

## 8. Evidence still required before production

The following are not proven by repository CI: live alarm/email delivery, budget notification delivery, restore drill, real Cognito group authorization, Rekognition recognition quality, raw-image deletion timing, offboarding deletion in AWS, real DLQ redrive, browser/camera acceptance and measured 20-scan p95. Record each test with date, environment, commit, evidence link and operator approval.
