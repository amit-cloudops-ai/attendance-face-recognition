# Pre-deployment audit — solo release

**Audit branch:** `fix/solo-owner-governance`  
**Target integration branch:** `solo/amit-monday`  
**Code audit baseline:** `31bb951c9c6dcffe3ddd95e9aa9b2d9df4808d75`  
**Follow-up fixes:** Part 2 static corrections are now added to PR #29; their latest CI result is pending.  
**CI:** [Run 43630911862 — passed](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43630911862)  
**AWS target:** account `924422830139`, region `us-east-1`  
**Deployment status:** NOT READY — no AWS resources have been provisioned by this deployment work.

This is a code/repository audit, not a claim that a live AWS deployment has been validated. The current branch has passed CI, but no remote Terraform backend initialization, Terraform plan, Terraform apply, IAM Access Analyzer run, or deployed browser/integration test has occurred. The owner's local WSL checkout was not directly executable from this GitHub audit; local verification must use this exact commit.

## 1. Verified baseline

The latest completed CI run on the audited commit passed both jobs:

- Python: Ruff, 95 pytest tests, canonical-region check, browser JavaScript syntax, HTML/CSP hygiene, shell syntax, workflow YAML, IAM template checks, and policy/configuration checks.
- Terraform: formatting, provider lockfile checks, `terraform init -backend=false` and `terraform validate` for the recognition, data, foundation and access modules, dev/prod roots, and billing root.

**Important distinction:** Terraform validation passed in GitHub Actions. A Terraform plan did not run. Validation does not prove that AWS will accept the rendered policies, quotas, resources, or provider operations.

Static review also confirmed the shared Lambda layer source layout (`shared/python/...`), S3 notification dependency on Lambda invoke permissions, CloudFront forwarding of the Authorization header, and account-root access in the KMS key policy.

## 2. Reconciliation of the previous seven-item audit

| Previous finding | Audit result |
|---|---|
| Dev execution boundary must exist before the dev root can plan/apply | **Correct.** The boundary template exists; the live policy was not returned by the read-only preflight and is not confirmed present. |
| State bucket and local `backend.hcl` are required | **Correct.** No matching project state bucket was found. Dev/prod backend examples exist; the actual local backend file is intentionally ignored and cannot be verified from GitHub. There is no executable Terraform bootstrap root. |
| Deployment workflow cannot run from the solo branch | **Correct.** Dev is restricted to `develop`; prod/billing to `main`. Those branches are still scaffold-only. The solo release must be promoted by reviewed PR after readiness gates. |
| Dev callback URL example is wrong | **Found and corrected on PR #29.** The example now points to `/callback.html`. |
| Two applies are needed | **Correct.** First create CloudFront with localhost callback/logout and origin values; then use the deployed CloudFront HTTPS origin in the Cognito callback/logout URLs and raw-bucket CORS settings, followed by a second reviewed plan/apply. |
| Local `web/config.json` can collide with Terraform upload | **Found and corrected on PR #29.** The generic frontend fileset now excludes root `config.json`, leaving the dedicated Terraform resource as its sole owner. |
| Reserved Lambda concurrency may exceed a quota of 10 | **Partly correct.** One environment reserves 19 concurrent executions (10 recognize + 5 enroll + 2 failure + 1 daily job + 1 weekly job); dev and prod deployed together reserve 38. The common regional Lambda default quota is 1,000, not 10; the account's actual available unreserved concurrency and existing reservations still need a read-only check. Do not remove concurrency limits without evidence. |

The previous recommendation to bypass OIDC and apply locally as the broad `Amit-admin` user is **not accepted as the default path**. The local Terraform wrapper has no STS account guard, the tfvars examples omit a required boundary ARN, and the proposed shortcut weakens the least-privilege deployment model. Any local apply would need its own exact plan and explicit approval.

## 3. Additional findings

### P1 — resolve before the first AWS build

1. **Encrypted SNS alert path was incomplete; static correction is now in PR #29.** The branch adds a CloudWatch service-principal statement to the alerts KMS key policy, grants `kms:Decrypt` and `kms:GenerateDataKey*` to the daily/weekly publisher roles, and adds SNS to the runtime boundary's `kms:ViaService` allowlist. Latest CI must validate these changes, and actual encrypted SNS/CloudWatch email delivery still requires a dev deployment test.
2. **Local Terraform input/account safety defects were corrected on PR #29.** Dev/prod examples now include the matching execution-boundary ARN, dev callback uses `/callback.html`, boundary ARN validation is tied to `account_id`, dev/prod providers restrict allowed account IDs, and the local wrapper checks STS before remote init/plan/apply. Exact local WSL execution is still pending.
3. **Generated frontend config collision is corrected on PR #29.** Root `config.json` is excluded from the generic `fileset` upload.
4. **Bootstrap is not executable yet.** `infra/bootstrap` contains documentation, not a Terraform root or a deterministic create/attach script. The exact account-specific state bucket, OIDC trust, boundaries, six roles and 26 managed policy documents still need rendering and review before any write.
5. **Live AWS inventory is incomplete.** The first preflight verified STS account `924422830139` and checked bootstrap resources only. The expanded application-resource inventory and the newly added Lambda/Rekognition quota checks have not yet been run.

### P2 — resolve before dev acceptance or production

6. **Scheduled-job alerting is incomplete.** No EventBridge Scheduler target-error alarm was found. Lambda error alarms do not cover a schedule that fails before invoking its Lambda.
7. **No warmup/provisioned-concurrency implementation was found.** The recognition handler has a warmup branch, but no schedule invokes it and no provisioned concurrency resource exists. Reserved concurrency is a cap, not a warm-instance guarantee. The current p95 alarm measures Lambda duration, not full capture-to-screen latency.
8. **Report retention is undefined.** The reports bucket is versioned but has no lifecycle retention policy; it stores employee/attendance data. Define retention and noncurrent-version expiry.
9. **Backup/DR is not accepted.** DynamoDB PITR is configured, but T27 remains open: no restore rehearsal or documented recovery-time evidence has been completed.
10. **Browser and integration coverage is incomplete.** CI has unit/static checks, but no browser automation or deployed integration suite. The browser/device matrix and real camera, Cognito PKCE, CORS, reports, schedules, offboarding and end-to-end latency tests remain pending.
11. **Audit writes are not atomic with all business updates.** Employee, settings and override handlers perform the business-table write and audit-table write separately. A failure between the two can leave a committed change without its corresponding audit event. Review a DynamoDB transaction/outbox design.
12. **Cost budgets are mis-scoped.** The two USD 15 budgets have no cost filters, so both track total account spend. Choose one account-wide budget or separate dev/prod budgets after activating and applying the Environment cost-allocation tag.
13. **Raw-image deletion has a fallback gap.** Normal workers and the failure processor attempt deletion, while S3 lifecycle expiry is one day. If the failure processor itself dead-letters, the 10-minute raw-image deletion objective is not guaranteed. Define an orphan-cleanup/recovery policy and test the failure path.
14. **Supply-chain controls are incomplete.** CI installs unpinned Python test dependencies; Terraform CI uses the setup action's default version while deployment pins Terraform 1.10.5; GitHub Actions are tag-pinned rather than SHA-pinned. T28 remains open.

15. **JWT revocation is delayed.** Cognito access tokens are valid for 60 minutes and API Gateway validates them statelessly. Disabling a kiosk/admin user prevents future authentication/refresh but an already-issued JWT can remain usable until expiry. Document the incident response and decide whether shorter access-token validity or a server-side revocation mechanism is required before production.

### P3 — product/operational decisions

16. Holiday records are read from the config table, but no admin holiday-management API/UI was found; document the manual configuration procedure or build a supported workflow.
17. Still-photo matching can be spoofed with a printed/displayed image. This is documented as a v1 limitation; require supervised kiosk operation and explicit risk acceptance before production, or scope Face Liveness.
18. The browser verification matrix is blank. Test supported Chrome/Android/Safari/iOS devices, camera permissions, responsive layout, accessibility and poor-network behaviour.
19. Consent capture currently stores a boolean and timestamp. Before production, record the exact notice/purpose version shown to the employee, the data controller, retention/deletion terms and the withdrawal process; obtain the required privacy/legal approval for employee face data and processing in the selected `us-east-1` region.
20. The repository default branch `main` is still scaffold-only. The integrated application is on the solo branch; do not represent the default branch as the completed release until the approved promotion.
21. There are 26 open PRs. PR #29 is the active solo audit PR; PR #2 is the separate teammate Part B PR; #4–#27 are historical chained task PRs. Do not merge these into the solo release. Close historical PRs only after confirming their work is represented in the consolidated branch.

## 4. Four-part remediation plan

### Part 1 — application correctness and recovery

**Status: corrections started on this audit branch; latest CI passed.**

- Weekly reports now exclude weekend/holiday records from working-day percentages, with regression coverage.
- Kiosk and admin enrollment polling windows increased from 8/12 seconds to 30 seconds.
- Inactive employees with remaining face templates now have a visible retry-deletion action.
- Enrollment photo selection and display now respect the configured maximum and remaining slots.
- E2E smoke polling increased to 60 seconds; it tracks exact raw object keys and removes only test-created objects if application cleanup fails.
- Remaining in this part: transactional audit consistency, explicit pending-request UX after long async retries, and manual browser verification. A one-command local check is now provided at `scripts/local_predeploy_check.sh`; it uses backend-disabled Terraform init only and makes no AWS API calls.

### Part 2 — Terraform, IAM and AWS configuration correctness

- Verify CI for the SNS topic/KMS static corrections, then test encrypted Lambda and CloudWatch alarm email delivery in dev.
- Run `bash scripts/local_predeploy_check.sh` from WSL on the current PR head; this checks Python, browser JS/HTML, shell, YAML, Terraform fmt and backend-disabled Terraform validate without AWS access.
- Confirm CI enforces generated `config.json` ownership.
- Run the local wrapper against the verified profile in read-only/validate mode; do not initialize the remote backend until separately approved.
- Pin Terraform CI to the deployment version.
- Run the expanded read-only preflight, including Lambda concurrency and Rekognition service quotas.
- Complete the account-specific rendered bootstrap plan; do not create anything yet.

### Part 3 — GitHub release and deployment governance

- Verify/configure the six GitHub environments, environment variables/secrets and owner-only apply checkpoints.
- Apply branch protection/rulesets to the intended release branches.
- Verify OIDC provider, six plan/apply roles, two runtime boundaries and all policy attachments.
- Keep the solo branch as source of truth; merge the audit PR into solo, then open a separate readiness PR into `develop`.
- Do not merge teammate or historical task PRs into the solo release.
- Keep plan/apply artifacts encrypted and require a separate owner approval for each AWS mutation stage.

### Part 4 — operational and production acceptance

- Fix/verify scheduler alarms and encrypted SNS delivery; confirm email subscriptions.
- Define report retention, raw-image orphan cleanup, backup/restore and incident runbooks.
- Run deployed dev E2E, Cognito/PKCE, camera/browser/device, CORS, attendance transition, schedule/report, offboarding and IAM tests.
- Measure actual capture-to-screen p95 and cold-start behaviour; decide whether warmup or provisioned concurrency is justified.
- Resolve budget scope and verify monthly cost against the USD 15 target.
- Complete a supervised pilot and record false accepts/rejects before production approval.

## 5. Go/no-go gates

**Do not start the AWS build until Parts 1–3 have passed their static/local/CI checks, the expanded read-only AWS inventory and quota checks are reviewed, and the owner has approved the exact bootstrap resource plan.**

After bootstrap, remote backend initialization, dev plan, dev apply, production plan and production apply remain separate approval gates. A successful Terraform validate is not a substitute for a live plan; a successful dev deploy is not a substitute for dev acceptance.

No AWS resource or policy was created, changed or deleted during this audit.
