## Current status — 14 November 2026

### Working agreement and source of truth

- Repository rules are defined in `AGENTS.md`; the task queue is `docs/TASKS.md`; reusable ChatGPT operating instructions are in `docs/CHATGPT_PROJECT_INSTRUCTIONS.md`.
- Work is task-ID based and isolated on `ai/T##-short-description` branches. One task is active at a time. The owner prefers to continue in the current ChatGPT conversation until it becomes too long; do not force a new chat between tasks.
- The solo implementation baseline is `solo/amit-monday` at `92e9bf53066145949bd430dd8dcbc0e7850df46d`. Work is now stacked in task branches; the current active branch is `ai/T32-scheduler-trust`, based on the completed T09 work. Task PRs remain open and unmerged pending owner review.
- Do not commit to `main` or `develop`, alter teammate branches, or merge teammate PRs into solo work without explicit direction.
- Target AWS account: the owner's existing account. Target region: `us-east-1`.

### T01 — repository governance restoration

- **Status:** complete.
- Restored `AGENTS.md`, `docs/TASKS.md`, and `docs/CHATGPT_PROJECT_INSTRUCTIONS.md`.
- Created the task queue. T01 is complete; T02–T09 and T31 are complete. T32 is the active cross-cutting task.
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
- Found the Scheduler trust policy lacked source account and schedule-group ARN conditions. T32 now creates environment-specific schedule groups and scopes each role to its group ARN and account.

### T05 — environment runtime permissions boundaries

- **Status:** complete on `ai/T05-runtime-boundaries`.
- CI run [43613054015](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43613054015), commit `91f8d63fa37d36067877755806c5975a454c37cd`: Python and Terraform jobs passed. The Python job rendered and parsed both templates with a dummy account ID, checked environment-specific KMS alias and S3/SQS `kms:ViaService` values, rejected IAM/STS management actions and unscoped resources other than Rekognition DetectFaces, and verified the 6,144-character managed-policy size limit.
- The templates remain account-ID parameterized and have not been created or attached in AWS. IAM Access Analyzer and live authorization validation remain future bootstrap/deployment gates.
- Added dev/prod IAM policy templates in `infra/policies/`, scoped to the audited runtime union across DynamoDB, S3, KMS, Rekognition, SQS, SNS, Lambda Scheduler invocation and CloudWatch Logs.
- KMS actions are constrained by the environment-specific alias condition and `kms:ViaService` for S3/SQS. AWS documents `kms:ResourceAliases` as an IAM-policy condition and lists S3/SQS as supported `kms:ViaService` integrations.
- Boundaries are allow-list ceilings and include no IAM management, `iam:PassRole`, STS, provisioning or self-management actions. They do not grant permissions; the handler-specific role policies remain the grant layer.
- Account ID is a template variable because the verified 12-digit account ID is not in the repository. Templates must be rendered and validated before manual bootstrap. No policy has been created or attached.

### T06 — foundation Terraform provider IAM mapping

- **Status:** complete on `ai/T06-foundation-provider-iam`.
- CI run [43613487881](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43613487881), commit `2a05c4d8248f7164d21f0aa6e1c851dad3b8e94d`: Python and Terraform jobs passed, including the policy-template validator, formatting, all module validations and both environment-root validations.
- CI resolved AWS provider v6.73.0 and archive provider v2.8.1 in run [43613054015](https://github.com/amit-cloudops-ai/attendance-face-recognition). The root constraint still allows AWS provider >=5,<7 and no lockfile is committed; T33 tracks pinning and reproducibility.
- Mapped KMS key/alias, all S3 bucket and split configuration resources, SNS topic/subscription, Lambda layer and AWS Budget API operations against provider v6.73.0 source and AWS Service Authorization References. Full matrix: `docs/security/FOUNDATION-PROVIDER-IAM.md`.
- S3 provider v6.73.0 `aws_s3_bucket` read path requires more bucket-level read actions than the explicitly configured split resources alone suggest; HeadBucket maps to `s3:ListBucket`. S3 Control tagging operations are used for tagged buckets.
- AWS Budget operations require `budgets:ModifyBudget`/`ViewBudget` plus account-wide `aws-portal:ModifyBilling`/`ViewBilling`. T34 tracks isolating budgets so ordinary deployment roles do not receive account-wide billing modification.
- Foundation KMS key policy still allows CloudFront service access from any distribution in the account; T35 tracks exact distribution scoping.

### T07 — data and recognition Terraform provider IAM mapping

- **Status:** static mapping drafted; CI validation pending.
- Mapped DynamoDB table TTL/PITR/tag APIs; CloudWatch Logs and metric alarms; IAM roles/inline policies; Lambda functions, permissions, event source mappings and async invoke config; Scheduler schedules; SQS queues/redrive allow policies; Rekognition collections; and S3 bucket notifications. Full matrix: `docs/security/DATA-RECOGNITION-PROVIDER-IAM.md`.
- Exact `iam:PassRole` scopes are required for Lambda execution roles and Scheduler target roles, with `iam:PassedToService` conditions.
- Critical KMS dependency: all five DynamoDB tables use the customer-managed KMS key. AWS requires the principal selecting the CMK to have Encrypt, Decrypt, ReEncrypt, GenerateDataKey, DescribeKey and CreateGrant permissions via DynamoDB. These belong in deployment-role policies, not Lambda runtime boundaries.
- T36 adds the customer-managed-key ViaService authorization and exact deployment-role KMS permissions before bootstrap. The direct DynamoDB metadata statement is not part of the customer-managed-key example.

### T07 — data and recognition Terraform provider IAM mapping

- **Status:** complete on `ai/T07-data-recognition-provider-iam`.
- Provider v6.73.0 source/API mapping covers DynamoDB table TTL/PITR/tags, CloudWatch Logs and alarms, IAM roles and inline policies, Lambda functions/permissions/event-source mappings/async invoke config, Scheduler schedules, SQS queues/redrive allow policies, Rekognition collections and S3 bucket notifications.
- Full matrix and exact resource-scope requirements: `docs/security/DATA-RECOGNITION-PROVIDER-IAM.md`.
- Identified the DynamoDB customer-managed-key deployment dependency. T36 tracks the corresponding key-policy and apply-role permission work.
- CI run [43614059591](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43614059591), commit `6421a667c10c`: Python and Terraform jobs passed.

### T08 — access Terraform provider IAM mapping

- **Status:** complete on `ai/T08-access-provider-iam`.
- Mapped Cognito user pool/client/domain/groups, API Gateway v2 API/authorizer/integrations/routes/stage, CloudFront distribution/OAC/cache/origin-request/response-header policies/function, S3 web bucket policy and frontend objects, and Lambda API permissions.
- API Gateway v2 uses `apigateway:GET/POST/PATCH/PUT/DELETE`; CloudFront is global and uses resource-specific action names; Cognito IAM granularity is user-pool level. Exact provider source/API matrix: `docs/security/ACCESS-PROVIDER-IAM.md`.
- CI run [43615508377](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43615508377), commit `59ad7e0c1ccd`: Python and Terraform jobs passed, including access module and dev/prod root validation.

### T09 — dev plan-role policy

- **Status:** complete on `ai/T09-dev-plan-policy`.
- Three managed-policy templates: `github-plan-dev-core.json.tftpl`, `github-plan-dev-edge.json.tftpl`, and `github-plan-dev-state.json.tftpl`. The split keeps each under the 6,144-character IAM managed-policy limit.
- Core/edge policies contain read-only service actions. State policy reads only `attendance/dev/terraform.tfstate` and permits Get/Put/Delete only on `attendance/dev/terraform.tfstate.tflock`; the state object cannot be written. No prod state path is present.
- Documented read-only residual scope: API Gateway v2 GET permissions span the `/apis` family because IDs are generated and child resources are not independently tagged by this configuration. CloudFront read actions use per-resource-family wildcards where IDs are opaque; no CloudFront mutation actions are granted.
- First CI attempt exposed an overbroad validator prefix that rejected `iam:GetRole` and other read-only IAM calls. Root cause was isolated; the policy was not changed. Fix attempt 1 narrowed the validator to explicit write/admin action prefixes.
- Final CI run [43615873597](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43615873597), commit `dcde60d5e339`: Python and Terraform jobs passed, including policy template rendering, JSON parsing, size checks, read-only action checks and dev-only state path checks.
- Added three read-only policy templates: `github-plan-dev-core.json.tftpl` (DynamoDB/IAM/Lambda/Scheduler/SQS/Rekognition/CloudWatch/SNS/Budgets reads), `github-plan-dev-edge.json.tftpl` (KMS/S3/Cognito/API Gateway v2/CloudFront reads), and `github-plan-dev-state.json.tftpl` (dev state read plus dev lockfile lifecycle only).
- The three rendered managed policies are each below 6,144 characters with dummy values. The state object is read-only; PutObject/DeleteObject are restricted to the dev `.tflock` object. No production state path is included.
- The plan role has no infrastructure create/update/delete actions. `s3:ListBucket` on the three app buckets is retained because the reviewed AWS provider v6.73.0 bucket refresh path calls HeadBucket, which requires ListBucket; no raw-object read permission is granted.
- CI now validates rendered JSON, template substitution, policy size, absence of infrastructure mutation actions, and dev-only state paths.

### Phase B — deployment readiness (not complete; no AWS provisioning)

- Complete: T01–T09, T31–T36. PRs #3–#17 are open and remain unmerged pending owner review.
- Active: T10 dev apply-role policy. The policy set is drafted and CI validation is pending.
- Remaining deployment policies: T11 prod plan, T12 prod apply. T09 dev plan is complete; T10 is being finalized.
- Remaining operational/security gates: T13 state bucket bootstrap specification; T14 GitHub OIDC/workflow permissions; T15 encrypted plan artifact lifecycle; T16 GitHub environment variables/secrets/protection; T17 template linting; T18 exact manual bootstrap plan; T19 solo-only deployment-readiness PR.
- Release gates T20–T24 remain explicitly approval-gated.
- Remaining deployment policies: dev apply (T10), prod plan (T11), prod apply (T12). T09 dev plan policies are complete.
- Remaining operational/security gates: state bucket specification (T13), OIDC/workflow permissions (T14), encrypted plan lifecycle (T15), GitHub environment/secrets/protection (T16), CI template linting (T17), exact bootstrap plan (T18), then solo-only readiness PR (T19).
- No AWS resource creation, remote backend initialization, Terraform plan or apply has occurred. These actions remain approval-gated.

### Release acceptance

AWS integration, Rekognition accuracy, consent-gated end-to-end behavior, raw-image deletion evidence, 20-scan p95 latency, browser/device compatibility, budget alarms, dev acceptance and production readiness remain unverified.

### Safety boundary

No AWS resources, IAM roles, OIDC provider, permissions boundaries, state bucket or KMS keys have been created by this work. No remote Terraform backend initialization, Terraform plan or Terraform apply has been run. Any such operation requires an exact written plan and separate explicit owner approval before execution.

## Session log

- 14 Nov 2026: Audited repository governance and found the three expected governance files absent from the solo implementation branch. Created `ai/T01-repository-governance` from the verified solo baseline, restored the governance files, created the task board, and added AI task-branch push CI coverage. T01 closed after both CI jobs passed. The next task is T02; no AWS changes. No AWS changes.

- First CI attempt [43615741764](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43615741764) failed in the new policy validator, not in pytest or Terraform. Root cause: the validator treated every `iam:` action as a mutation, incorrectly rejecting required read-only `iam:GetRole`, `iam:GetRolePolicy` and `iam:ListRoleTags`. The policy itself was not changed. Fix attempt 1 narrows the validator to explicit IAM write/administrative prefixes and also checks API Gateway, DynamoDB, Lambda, SQS, Scheduler and other service mutation verbs. Revalidation is pending.

### T32 — EventBridge Scheduler trust policy hardening

- **Status:** complete on `ai/T32-scheduler-trust`.
- Created `aws_scheduler_schedule_group.attendance` named `attendance-dev` or `attendance-prod` and assigned daily/weekly schedules to the matching group.
- Scheduler execution-role trust now requires both `aws:SourceAccount=var.account_id` and `aws:SourceArn=aws_scheduler_schedule_group.attendance.arn` using exact `StringEquals` conditions. This follows AWS guidance that the SourceArn must be the schedule-group ARN, not an individual schedule ARN.
- Added the schedule-group CRUD/tag provider operations to the T07 IAM action inventory. Updated the dev plan role policy to read only the `attendance-dev` schedule group and its schedules.
- CI run [43616332197](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43616332197), commit `966eda33e8b7`: Python and Terraform jobs passed. Python validation checked environment-specific group names, source account/ARN trust conditions, schedule group assignment in both environment roots, and dev-only plan policy group/schedule ARNs. Terraform formatting, all four module validations and both environment-root validations passed.
- Confirmed the current Scheduler execution-role trust policy allowed any `scheduler.amazonaws.com` principal request without source conditions.
- AWS's current confused-deputy guidance explicitly requires `aws:SourceArn` to identify a **schedule-group ARN**, not an individual schedule ARN. The existing configuration used the shared `default` group, which would not separate dev and prod.
- Added a dedicated `attendance-<env>` schedule group in the data module, assigned daily/weekly schedules to it, and scoped Scheduler role trust to the exact group ARN plus `aws:SourceAccount=var.account_id` using `StringEquals`.
- Added `account_id` as an explicit data-module input in both environment roots. Provider IAM follow-up includes Create/Get/DeleteScheduleGroup and tagging actions.
- AWS evidence: [EventBridge Scheduler confused-deputy prevention](https://docs.aws.amazon.com/scheduler/latest/UserGuide/cross-service-confused-deputy-prevention.html) states the source ARN must be the schedule group ARN and recommends combining it with source account.


### T33 — Terraform provider reproducibility

- **Status:** active on `ai/T33-provider-lockfiles`.
- CI previously resolved AWS provider `6.73.0` and archive provider `2.8.1`, while dev/prod roots still allowed broad ranges (`>= 5.0, < 7.0` and `>= 2.4, < 3.0`) and no lockfiles were committed.
- Objective: pin the exact provider versions verified by the current CI baseline, generate `linux_amd64` and `windows_amd64` checksums for both environment roots, commit the lockfiles, and make CI fail if the lockfiles need modification.
- No backend initialization against AWS, plan, apply, or resource provisioning is part of this task.


### T34 — AWS Budget isolation

- **Status:** complete on `ai/T35-cloudfront-kms-scope`.
- The final key policy is owned by the access module and installed only after the CloudFront distribution is created. Its OAC decrypt grant requires exact `aws:SourceAccount` and `ArnEquals aws:SourceArn = aws_cloudfront_distribution.site.arn`; no distribution wildcard remains.
- CI on descendant branch run [43617044959](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43617044959), commit `fdd6513176`: Python and Terraform jobs passed, validating the exact KMS policy source and both environment roots.
- Removed `aws_budgets_budget.monthly` from the shared foundation module. Normal dev/prod Terraform roots no longer create or update account-level budgets.
- Added independent `infra/billing` Terraform root with its own backend state key `attendance/billing/terraform.tfstate`; it manages the dev and prod USD 15 monthly budgets and their 80%/100% actual-cost notifications.
- Removed `budgets:ViewBudget` and `aws-portal:ViewBilling` from the dev environment plan-role core policy. Billing access belongs only to a dedicated billing plan/apply role; no such role or policy is attached/created here.
- This isolates the privileged account-level `aws-portal:ModifyBilling` permission from standard environment deployment roles. Bootstrap, billing role trust and billing plan/apply policy remain separate manual review items.


### T35 — exact CloudFront KMS scope

- **Status:** complete on `ai/T36-dynamodb-kms-access`.
- The access-module KMS policy includes the AWS-documented customer-managed-key path: account principal, `kms:CallerAccount`, exact `kms:ViaService=dynamodb.us-east-1.amazonaws.com`, and required crypto/grant/describe actions. The AWS-managed-key-only direct metadata statement is intentionally omitted.
- Added separate dev/prod apply-policy fragments scoped to the matching KMS alias and DynamoDB ViaService. `kms:CreateGrant` is separately constrained by `kms:GrantIsForAWSResource=true`.
- CI run [43617044959](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43617044959), commit `fdd6513176`: Python and Terraform jobs passed, including the new KMS policy validator, formatting, module validation and both environment roots.
- AWS reference: [DynamoDB encryption at rest usage notes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/encryption.usagenotes.html).
- Removed the CloudFront service statement from the foundation key policy. Foundation now creates the KMS key with the default account-root policy; it no longer needs the distribution ID before that resource exists.
- Added `kms_key_id` output from foundation and input to access. The access module now owns `aws_kms_key_policy.attendance` and installs the complete key policy after creating the CloudFront distribution.
- CloudFront's `kms:Decrypt` grant uses `aws:SourceAccount` plus `ArnEquals aws:SourceArn = aws_cloudfront_distribution.site.arn`; the former `distribution/*` wildcard is removed. SNS alert and Lambda async DLQ service statements and account-root administration remain in the final policy.
- Added the `kms:GetKeyPolicy`/`kms:PutKeyPolicy` provider action mapping for the access-module policy resource.
- Also corrected a latent T31 omission: `user_pool_issuer` output was still hard-coded to `ap-south-1`; it now emits the `us-east-1` issuer used by the deployed Cognito pool.


### T36 — DynamoDB customer-managed KMS authorization

- **Status:** implementation drafted; CI validation pending.
- The final key policy in the access module now has a DynamoDB customer-managed-key statement for account principals using the key only through `dynamodb.us-east-1.amazonaws.com`, with `kms:CallerAccount` constrained to this account. This allows only `Encrypt`, `Decrypt`, `ReEncrypt*`, `GenerateDataKey*`, `CreateGrant` and `DescribeKey` through DynamoDB. The separate DynamoDB service-principal metadata statement was removed after reviewing AWS documentation: that direct metadata statement appears in the AWS-managed-key example, while the customer-managed-key example authorizes the table-creating principal through `kms:ViaService`.
- Added environment-specific dev/prod apply-policy fragments for the exact `alias/attendance-dev` or `alias/attendance-prod` key. The crypto actions and `kms:CreateGrant` are separate statements; CreateGrant alone requires `kms:GrantIsForAWSResource=true`. Both are constrained to the DynamoDB ViaService and environment alias.
- CI validates exact service principal statements, action sets, account/region conditions, environment aliases, CreateGrant condition and policy size.
- AWS reference: [DynamoDB encryption at rest usage notes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/encryption.usagenotes.html) explains the minimum customer-managed-key actions, the `kms:ViaService` model and DynamoDB grant lifecycle.


### T10 — dev Terraform apply-role policy

- **Status:** policy set drafted; CI validation pending.
- Added split managed-policy templates for core services, DynamoDB, Lambda, IAM, foundation, access, dev state and DynamoDB KMS provisioning. Each rendered policy is below the 6,144-character managed-policy limit.
- IAM role creation requires the exact dev execution boundary and required Project/Environment tags. `iam:PassRole` is split between the exact 14 Lambda execution-role ARNs and two Scheduler role ARNs, with `iam:PassedToService` constrained separately.
- DynamoDB table permissions use five exact dev table ARNs and the attendance date GSI. Lambda permissions use 14 exact function ARNs; the event-source-mapping create action is the one documented `Resource: "*"` exception and is constrained by `lambda:FunctionArn` to the failure processor.
- Foundation permissions exclude AWS Budgets and billing actions; the separate billing root is not in the dev apply role. State writes are limited to the dev state object and dev lockfile.
- Added CI validation for JSON rendering, size, dev-only ARNs, exact PassRole roles/service conditions, mandatory execution boundary, state/lock isolation, DynamoDB tables, Lambda event source mapping scope and API Gateway path family.
- Residual service limitations are documented in `infra/policies/README.md`: API Gateway v2 child-resource paths remain scoped at the API path family until generated API ID can be pinned; several create APIs require `Resource: "*"` with tag or function conditions where supported. This is a policy template, not an attached AWS role.
- No AWS resources, IAM roles or policies created; no remote backend initialization, Terraform plan or apply.


### T11 — production Terraform plan-role policy

- **Status:** policy templates drafted; CI validation pending.
- Cloned the dev read-only plan policy into three production-specific policy templates (core, edge, state), changing environment tags, S3/DynamoDB/Lambda/KMS/Scheduler resource names and state key to prod.
- The production state object is read-only; only the production `.tflock` object can be Get/Put/Deleted for native S3 locking.
- CI checks read-only action sets, 6,144-character policy size, exact `attendance-prod` Scheduler group/schedule ARNs, and rejects dev resources/state paths from prod policies.
- No AWS resources or IAM roles created; no remote backend initialization, plan or apply.


### T12 — production Terraform apply-role policy

- **Status:** policy templates drafted; CI validation pending.
- Added the production counterpart to the split dev apply set: core, data, Lambda, IAM, foundation, access, state and DynamoDB KMS templates.
- Production policies use exact prod table/function/queue/role ARNs, `attendance-prod` KMS alias, prod tags, prod schedule group, and the prod execution-role boundary. The prod state object is Get/Put only; the prod lockfile is the only state path with Get/Put/Delete.
- CI validates each policy's JSON, size, absence of dev resource/state paths and billing permissions, exact PassRole role/service scope, required prod boundary, five DynamoDB table ARNs, failure processor function condition and prod KMS alias/ViaService/GrantIsForAWSResource conditions.
- No AWS resources, IAM roles or policies created or attached; no remote backend initialization, Terraform plan or apply.


### T13 — Terraform state bucket bootstrap specification

- **Status:** specification drafted; CI validation pending.
- Added `docs/STATE-BUCKET-BOOTSTRAP.md` with a globally unique account-specific bucket naming convention, us-east-1 region, SSE-S3 default encryption, versioning, all four Block Public Access settings, BucketOwnerEnforced ownership, TLS-only deny policy, no Object Lock, no automatic state expiration, rollback and manual verification sequence.
- Documented state and lockfile keys for dev, prod and the isolated billing root. Plan/apply state permissions are environment-specific; billing state remains separate and is not included in normal environment roles.
- CI checks all three Terraform S3 backend blocks for exact state keys, region, encryption and native lockfiles, and checks required bucket security controls in the bootstrap spec.
- No AWS bucket or resources created; no remote backend init, plan or apply.


### T14 — GitHub OIDC trust and deployment workflow hardening

- **Status:** implementation drafted; CI validation pending.
- Updated deploy workflow to use four operation-specific GitHub environments (`dev-plan`, `dev-apply`, `prod-plan`, `prod-apply`) and one environment-scoped `AWS_ROLE_ARN` variable. This makes the OIDC subject distinguish plan and apply roles.
- Added four trust policy templates with exact repository/environment subjects and `aud=sts.amazonaws.com`; no wildcard subjects.
- Documented exact role names, environment branch restrictions, required apply reviewers/self-review prevention, branch protection/CODEOWNERS, environment variables and age recipient/identity separation in `docs/GITHUB-OIDC-DEPLOYMENT.md`.
- Workflow retains minimal permissions (`actions:read`, `contents:read`, `id-token:write`), dev/develop and prod/main branch gates, manual dispatch, exact plan run/commit/branch provenance checks and no static AWS credentials.
- CI validates all four trust templates, exact audience/subject, OIDC provider ARN, workflow environment/role selector, branch gates, token permissions and absence of static AWS credentials.
- No OIDC provider, IAM role or GitHub environment was created/configured. No AWS resource or remote backend operation was performed.


### T15 — encrypted Terraform plan artifact lifecycle

- **Status:** workflow hardening drafted; CI validation pending.
- Plan artifact names now include environment, workflow run ID and run attempt. Apply verifies successful manual workflow_dispatch run, exact workflow path, expected release branch, exact same commit SHA and numeric run attempt before download.
- Apply downloads only from the referenced run ID and artifact name including the verified attempt. This closes the prior gap where another workflow_dispatch run on the same branch/commit could potentially satisfy the SHA/branch/event checks.
- Added EXIT cleanup for plaintext plan after encryption; artifact upload includes only tfplan.age and retention-days=1. Apply uses a protected age identity secret, umask 077, ephemeral identity file cleanup, removes encrypted artifact after decryption and removes decrypted plan in an always()-guarded cleanup step.
- Added `docs/TERRAFORM-PLAN-ARTIFACT.md` with lifecycle, access, retention, provenance, rotation and residual trust requirements.
- CI validates workflow path/run-attempt binding, encrypted-only upload path, one-day retention, age identity cleanup and no static AWS credentials.
- No plan artifact generated; no AWS role assumption, remote backend init, plan or apply.
