## Current status — 14 November 2026

### Working agreement and source of truth

- Repository rules are defined in `AGENTS.md`; the task queue is `docs/TASKS.md`; reusable ChatGPT operating instructions are in `docs/CHATGPT_PROJECT_INSTRUCTIONS.md`.
- Work is task-ID based and isolated on `ai/T##-short-description` branches. One task is active at a time. The owner prefers to continue in the current ChatGPT conversation until it becomes too long; do not force a new chat between tasks.
- The implementation baseline for this task is `solo/amit-monday` at `92e9bf53066145949bd430dd8dcbc0e7850df46d`. The governance task branch is `ai/T01-repository-governance`; T02 will continue from this branch so the restored rules stay in the working history.
- Do not commit to `main` or `develop`, alter teammate branches, or merge teammate PRs into solo work without explicit direction.
- Target AWS account: the owner's existing account. Target region: `us-east-1`.

### T01 — repository governance restoration

- **Status:** complete.
- Restored `AGENTS.md`, `docs/TASKS.md`, and `docs/CHATGPT_PROJECT_INSTRUCTIONS.md`.
- Created a 30-task queue. T01 is complete; T02 is the next task and covers KMS key-policy validation for Lambda asynchronous failure destinations.
- Updated CI push triggers to include `ai/**` so task branches receive the repository's existing Python and Terraform checks.
- The CI workflow currently runs Ruff, pytest, browser JavaScript/CSP checks, Bash syntax, workflow YAML parsing, Terraform formatting, and Terraform module/environment-root validation. A `cfn-lint` step is not present in the checked workflow, and no `template.yaml` was found in the checked repository tree; T17 explicitly verifies whether a CloudFormation template exists before adding linting.
- T01 branch validation: GitHub Actions runs [43611844694](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43611844694) and [43611848777](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43611848777) completed successfully. Both `python` and `terraform-fmt` jobs passed.

### T02 — Lambda asynchronous destination KMS policy

- **Status:** complete on `ai/T02-lambda-dlq-kms-policy`.
- Root cause: the Lambda service-principal key-policy statement used a wildcard matching all environment DLQs, including the failure-processor queue which is not an asynchronous destination.
- Fix: replaced the wildcard with `ArnEquals` and the exact `recognize-dlq` and `enroll-dlq` queue ARNs, retaining the source-account condition. The execution-role KMS and SQS permissions remain separately scoped to the actual producer/consumer functions.
- AWS documentation reviewed: Lambda requires execution-role destination permissions and both the role and key resource policy to permit KMS use for customer-managed encrypted destinations; SQS documents the Lambda service as a supported event source for encrypted queues and supports source-ARN confused-deputy conditions.
- Validation: run [43612039939](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43612039939), commit `598a6e013ffb1861941ca33c2a9611fae304482b`: Python and Terraform jobs passed, including `terraform fmt`, all four module validations and both environment-root validations.

### T03 — recognition runtime IAM reconciliation

- **Status:** complete on `ai/T03-recognition-runtime-iam`.
- CI run [43612245039](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43612245039), commit `aad1fb68f4045e84aa3c418cf24794af45edb1c8`: Python and Terraform jobs passed, including `terraform fmt`, all four module validations and both environment-root validations.
- Audited all seven recognition handlers and shared `record_scan`/`get_settings` SDK call sites against the role-specific policies.
- Removed unused `sqs:ChangeMessageVisibility` from the failure processor role; retained ReceiveMessage, DeleteMessage and GetQueueAttributes on the two event-source queues.
- Verified `rekognition:DetectFaces` requires `Resource: "*"`; collection-bound actions remain on the collection ARN. AWS docs: [Rekognition IAM guide](https://docs.aws.amazon.com/rekognition/latest/dg/security_iam_service-with-iam.html).
- Found a separate deployment blocker: several recognition handlers hard-code `ap-south-1`, while Terraform targets `us-east-1`. Added T31 to correct runtime region selection across all Lambda handlers/shared code before deployment.

### T31 — Lambda runtime region alignment

- **Status:** complete on `ai/T31-runtime-region`.
- Attempt 1 CI run [43612501767](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43612501767) failed 29 tests because the region was captured at module import, before Moto fixtures set `AWS_REGION`.
- Root cause: module-level region constants evaluated before test fixture environment overrides. Tests were not changed.
- Attempt 2 changed all handler region resolution to call-time `_region()` lookups and kept shared helpers on call-time environment reads. This preserves isolated Moto test regions while deployed Lambdas use their actual `AWS_REGION`.
- CI run [43612668343](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43612668343), commit `604a3ef6f69c05af50c8cd3319e1d44166c93545`: Python and Terraform jobs passed, including pytest, Ruff, formatting, all module validations and both environment-root validations.
- Root cause: all seven data handlers and all seven recognition handlers contained an explicit `ap-south-1` region constant; shared DynamoDB helpers and the result handler also fell back to `ap-south-1`. Terraform provider and backend roots target `us-east-1`, so these SDK clients could address the wrong regional resources.
- Fix: all 14 Lambda handlers now derive their region from Lambda's reserved `AWS_REGION` environment variable with `us-east-1` as the local/test fallback. Shared `get_settings` and `record_scan` helpers use the same environment variable and fallback.
- No AWS resources or live AWS calls were used. Python and Terraform CI are the validation gates.

### T04 — data runtime IAM reconciliation

- **Status:** complete on `ai/T04-data-runtime-iam`.
- CI run [43612832683](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43612832683), commit `6c1946a4d2391eeabf0a0323fae19669259722dc`: Python and Terraform jobs passed, including pytest, Ruff, formatting, all four module validations and both environment-root validations.
- Audited all seven data handlers against the role-specific policies in `infra/modules/data/main.tf`.
- Confirmed the actions and ARNs for employees, attendance query, daily/weekly jobs, reports, override and settings. Override uses GetItem/PutItem, settings uses GetItem/PutItem; no UpdateItem grants are required for either.
- Confirmed data KMS split: daily_job/weekly_job GenerateDataKey for SSE-KMS report writes; reports Decrypt for report reads; no direct KMS permission for DynamoDB encryption.
- Confirmed per-function CloudWatch log writes are scoped to Terraform-managed log groups; Scheduler invoke policies target only their matching Lambda functions.
- Found the Scheduler trust policy lacks source account/schedule ARN conditions. Added T32 to harden it separately.

### T05 — environment runtime permissions boundaries

- **Status:** templates drafted; CI validation and final review pending.
- Added dev/prod IAM policy templates in `infra/policies/`, scoped to the audited runtime union across DynamoDB, S3, KMS, Rekognition, SQS, SNS, Lambda Scheduler invocation and CloudWatch Logs.
- KMS actions are constrained by the environment-specific alias condition and `kms:ViaService` for S3/SQS. AWS documents `kms:ResourceAliases` as an IAM-policy condition and lists S3/SQS as supported `kms:ViaService` integrations.
- Boundaries are allow-list ceilings and include no IAM management, `iam:PassRole`, STS, provisioning or self-management actions. They do not grant permissions; the handler-specific role policies remain the grant layer.
- Account ID is a template variable because the verified 12-digit account ID is not in the repository. Templates must be rendered and validated before manual bootstrap. No policy has been created or attached.

### Phase B — deployment readiness (not complete; no AWS provisioning)

- T31 is next because runtime region mismatch blocks any us-east-1 deployment. T04 follows.
- Region migration and separate dev/prod Terraform state keys are present on the solo implementation branch. The state bucket remains a manual prerequisite.
- The manual deployment workflow uses GitHub OIDC, separate plan/apply role variables, encrypted saved plans using age, commit/branch checks, and GitHub Environment gates. Its workflow logic still requires a dedicated least-privilege and protection review.
- The IAM inventory is a candidate review document, not an attachable policy. Runtime KMS grants have been narrowed by handler in the data and recognition modules; exact key-policy conditions and remaining runtime IAM mappings are not yet fully verified.
- Required execution-role boundary inputs exist, but dev/prod boundary policy documents and the four GitHub plan/apply policies are not finalized.
- Remaining gates are tracked as T02–T18 in `docs/TASKS.md`; PR promotion, dev deployment, production deployment, and acceptance tasks follow as T19–T24.
- CI validation on the implementation baseline is green as noted above. T01 branch CI is green; subsequent tasks will continue on their own `ai/T##` branches.

### Release acceptance

AWS integration, Rekognition accuracy, consent-gated end-to-end behavior, raw-image deletion evidence, 20-scan p95 latency, browser/device compatibility, budget alarms, dev acceptance and production readiness remain unverified.

### Safety boundary

No AWS resources, IAM roles, OIDC provider, permissions boundaries, state bucket or KMS keys have been created by this work. No remote Terraform backend initialization, Terraform plan or Terraform apply has been run. Any such operation requires an exact written plan and separate explicit owner approval before execution.

## Session log

- 14 Nov 2026: Audited repository governance and found the three expected governance files absent from the solo implementation branch. Created `ai/T01-repository-governance` from the verified solo baseline, restored the governance files, created the task board, and added AI task-branch push CI coverage. T01 closed after both CI jobs passed. The next task is T02; no AWS changes. No AWS changes.
