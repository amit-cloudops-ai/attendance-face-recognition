# IAM least-privilege inventory — deployment and runtime roles

**Implementation baseline:** `solo/amit-monday`; current task work is isolated on `ai/T04-data-runtime-iam`  
**Target region:** `us-east-1`  
**Status:** candidate inventory only. This document is not an attachable policy and does not authorize AWS changes.

## 1. Role separation

| Role | Purpose | Required boundary |
|---|---|---|
| `attendance-github-plan-dev` | Refresh and plan dev root; access dev state/lock only | No application role permissions |
| `attendance-github-apply-dev` | Apply reviewed dev plan | Must attach only dev execution boundary |
| `attendance-github-plan-prod` | Refresh and plan prod root; access prod state/lock only | No application role permissions |
| `attendance-github-apply-prod` | Apply reviewed prod plan | Must attach only prod execution boundary |
| Lambda and Scheduler roles | Runtime access per handler | Pre-created environment boundary is mandatory |

OIDC requirements:
- Audience: `sts.amazonaws.com`
- Dev subject: `repo:amit-cloudops-ai/attendance-face-recognition:environment:dev`
- Prod subject: `repo:amit-cloudops-ai/attendance-face-recognition:environment:prod`
- Dev GitHub Environment is restricted to `develop`; prod is restricted to `main` with a required reviewer.

Plan roles must not have infrastructure mutation permissions. Prod plan/apply permissions must be separate from dev. Do not use static AWS credentials or wildcard OIDC subjects.

## 2. Terraform resource inventory

| Module | Resource families |
|---|---|
| Foundation | KMS keys/aliases; S3 buckets, access blocks, encryption, CORS, versioning, lifecycle, bucket policy; SNS topic/subscription; Lambda layer; AWS Budget |
| Data | DynamoDB tables/items; CloudWatch log groups/alarms; Lambda functions; IAM roles/inline policies; Scheduler schedules |
| Recognition | Rekognition collection; SQS queues/redrive; CloudWatch logs/alarms; Lambda functions; IAM roles/inline policies; async invoke config; event source mapping; Lambda permissions; S3 bucket notification |
| Access | Cognito pools/groups/domain/client; API Gateway v2 API/authorizer/integrations/routes/stage; Lambda permissions; CloudFront OAC/policies/function/distribution; web bucket policies and objects |

## 3. Runtime policy reconciliation

The following is a reconciliation checklist based on the current Terraform policies. Each action needs confirmation against actual handler code and service authorization before boundary policies are finalized.

| Runtime function group | Resource scope | Actions currently required or to verify |
|---|---|---|
| presign / enroll_url | Raw bucket `captures/*` or `enroll/*`; scan-results table | `s3:PutObject`, `dynamodb:PutItem` or `GetItem` |
| result | Scan-results table | `dynamodb:GetItem` |
| recognize | Rekognition collection; raw `captures/*`; employees, attendance, config, scan-results; recognize DLQ | `rekognition:DetectFaces` (resource wildcard may be required), `rekognition:SearchFacesByImage`, S3 get/delete, DynamoDB get/put/update, `sqs:SendMessage` |
| enroll | Rekognition collection; raw `enroll/*`; employees, config, scan-results; enroll DLQ | DetectFaces, SearchFacesByImage, IndexFaces, DeleteFaces; S3 get/delete; DynamoDB get/update; SQS send |
| faces_delete | Rekognition collection; employees and audit tables | Rekognition DeleteFaces; DynamoDB get/update/put |
| failure | Recognition DLQs; scan-results, employees, attendance/date index; Rekognition collection; raw captures/enroll prefixes | SQS receive/delete/get-attributes; DynamoDB get/update/query; Rekognition search/delete; S3 get/delete |
| employees | Employees and audit tables | DynamoDB get/put/update/scan; audit put |
| attendance_query | Attendance table/date index and employees table | DynamoDB query and employee scan |
| daily_job | Employees, attendance/date index, config, reports/daily prefix, alerts topic | DynamoDB scan/query/put/update/get; S3 put; SNS publish |
| weekly_job | Employees, attendance/date index, config, reports/weekly prefix, alerts topic | DynamoDB scan/query/get; S3 put; SNS publish |
| reports | Reports object prefix | S3 get |
| override | Employees, attendance and audit | DynamoDB get/put (verify actual update calls in handler) |
| settings | Config and audit | DynamoDB get/put/update as required by handler |
| Scheduler roles | Matching daily or weekly Lambda only | `lambda:InvokeFunction` on the exact target Lambda ARN |

Important runtime review points:
- The foundation module creates the KMS key and uses it for DynamoDB tables, raw/report/web buckets and SQS encryption. Verify whether application roles need `kms:Decrypt` and `kms:GenerateDataKey` for each resource's actual encryption context and the chosen AWS service integration. Do not assume a broad KMS grant is necessary.
- The current Terraform adds KMS decrypt/data-key actions to every Lambda execution role. This is a candidate overgrant until the data paths and KMS key policy are validated. Narrow the grants to only handlers that actually call KMS or need direct KMS access.
- Data DynamoDB call sites are reconciled below. In particular, override uses GetItem/PutItem (not UpdateItem), and settings uses GetItem/PutItem plus audit PutItem.
- SQS asynchronous destination producer and event-source consumer permissions are reconciled in the recognition review below; keep these distinct from data-handler policies.
- Rekognition resource-level scope is verified in section 3B: DetectFaces requires `Resource: "*"`; collection actions are collection-ARN scoped.
- Lambda logging requires scoped `logs:CreateLogStream` and `logs:PutLogEvents` on that function's log group ARN suffix. Verify log-group creation stays in Terraform, not runtime.

## 3A. Verified handler call-site review — 14 Nov 2026

The data handler review confirms these concrete SDK operations in the solo implementation baseline:

| Handler | Verified operations | Policy reconciliation |
|---|---|---|
| employees | GetItem, Scan, PutItem, UpdateItem | Existing table and audit permissions cover these calls |
| attendance_query | Scan employees; Query attendance and date index | Existing Scan/Query scope matches |
| daily_job | Scan employees; Query attendance; GetItem config; PutItem/UpdateItem attendance; PutObject reports; SNS Publish | Existing policy covers these operations |
| weekly_job | Scan employees; Query attendance; GetItem config; PutObject reports; SNS Publish | Existing policy covers these operations |
| reports | S3 GetObject from reports prefix | Existing S3 read scope matches |
| override | GetItem employee/attendance; PutItem attendance/audit | Existing policy covers the observed calls |
| settings | PutItem config/audit | Existing policy covers the observed calls |

Data-role KMS correction: DynamoDB encryption is service-managed. Only daily_job/weekly_job report writers and the reports reader receive direct KMS actions. Recognition raw-image and encrypted-SQS KMS actions are separately documented in section 3B. The foundation key's SNS and CloudFront service statements still require provider/resource-scope review in the foundation-module task.

The runtime policy code has now been changed to remove the blanket KMS grant from every Lambda role and instead add per-handler KMS statements:

| Module | Function | KMS actions | Reason |
|---|---|---|---|
| Data | daily_job | GenerateDataKey | Writes SSE-KMS report objects |
| Data | weekly_job | GenerateDataKey | Writes SSE-KMS report objects |
| Data | reports | Decrypt | Reads SSE-KMS report objects |
| Recognition | presign | GenerateDataKey | Presigned upload to raw SSE-KMS bucket |
| Recognition | enroll_url | GenerateDataKey | Presigned upload to raw SSE-KMS bucket |
| Recognition | recognize | Decrypt, GenerateDataKey | Reads raw objects and sends to encrypted SQS DLQ |
| Recognition | enroll | Decrypt, GenerateDataKey | Reads raw objects and sends to encrypted SQS DLQ |
| Recognition | failure | Decrypt | Reads raw objects and consumes encrypted SQS DLQs |
| Other handlers | result, faces_delete, employees, attendance_query, override, settings | None | No direct S3/SQS KMS data operation identified |

The foundation KMS key policy includes a Lambda service-principal statement for the two asynchronous failure destination queues only (`recognize-dlq` and `enroll-dlq`). It is constrained by `aws:SourceAccount` and exact `aws:SourceArn` values (`ArnEquals`). The separate failure-processor DLQ is not an asynchronous destination and is excluded from this statement. The corresponding function execution roles retain the SQS producer KMS permissions and `sqs:SendMessage` permissions required by Lambda asynchronous destinations.

AWS authorization references reviewed:
- S3 SSE-KMS requires `kms:GenerateDataKey` for PutObject and `kms:Decrypt` for GetObject: https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingKMSEncryption.html
- SQS SSE-KMS producers require `kms:GenerateDataKey` and `kms:Decrypt`; consumers require `kms:Decrypt`: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-key-management.html

This is a code-call-site review, not a complete AWS authorization verification. The Lambda destination key-policy statement is scoped to the exact two destination queue ARNs and source account. No SQS encryption-context condition is added because the reviewed AWS SQS key-management guidance specifies source ARN/account confused-deputy controls but does not establish an encryption-context condition for this use case. S3 encryption-context details, Rekognition resource-level support and provider API actions remain open gates.

## 4. Deployment policy construction

Foundation module provider actions have been mapped against the exact AWS provider v6.73.0 source and AWS Service Authorization References in `docs/security/FOUNDATION-PROVIDER-IAM.md`. This mapping includes the S3 bucket read actions that the monolithic `aws_s3_bucket` provider resource calls even when split resources own configuration. It also identifies the account-wide `aws-portal:ModifyBilling` dependency introduced by the Budget resource.

Remaining provider-action tasks:
- Data and recognition module: T07.
- Access module: T08.
- All deployment policies must use exact API action names, resource ARNs, resource tags and supported condition keys. Use `iam:PassRole` only for exact environment-specific execution role ARNs and condition it by `iam:PassedToService`.

## 5. Execution-role permissions boundaries

Two environment-specific boundary policy templates have been drafted:
- `infra/policies/execution-role-boundary-dev.json.tftpl` — rendered policy name: `attendance-dev-execution-boundary`.
- `infra/policies/execution-role-boundary-prod.json.tftpl` — rendered policy name: `attendance-prod-execution-boundary`.

The templates cap the union of runtime permissions identified by the data and recognition call-site audits. They use exact environment resource ARNs and an account-ID template variable. KMS use is limited to the environment key alias via `kms:ResourceAliases` and to S3/SQS forward access sessions via `kms:ViaService`. The templates are allow-list boundaries: they contain no IAM management, STS, provisioning, `iam:PassRole`, or boundary self-management actions. `rekognition:DetectFaces` is the only runtime action with `Resource: "*"`, because AWS does not support resource-level authorization for that action.

A permissions boundary does not grant permissions; each role still needs its own least-privilege inline policy. The templates are not yet attachable because the verified 12-digit account ID must be supplied at render time. Rendered JSON and ARNs must be validated before bootstrap.

The GitHub apply role may attach the expected boundary to approved `attendance-<env>-*` roles, but must not modify, delete or detach the boundary or create an unbounded application role. Apply role policies must constrain role creation and policy attachment by resource ARN/name and supported boundary conditions. Validate provider support before role creation.

## 6. Terraform state isolation

- Dev state: `attendance/dev/terraform.tfstate`
- Dev lock: `attendance/dev/terraform.tfstate.tflock`
- Prod state: `attendance/prod/terraform.tfstate`
- Prod lock: `attendance/prod/terraform.tfstate.tflock`

Scope object read/write to the matching state key. Allow `s3:DeleteObject` only on the matching lock object. Scope `s3:ListBucket` by the corresponding `s3:prefix`. Do not grant one environment access to the other's state.

## 7. Remaining validation

1. Verify CI after the Terraform formatting correction.
2. Inspect all application Lambda handlers and compare each AWS SDK operation to its role policy.
3. Validate all Terraform provider read/write actions and AWS IAM resource/condition support.
4. Produce two execution boundaries and four GitHub plan/apply policy documents with exact resource scopes.
5. Validate backend bucket controls and state permissions separately.
6. Review GitHub Environment branch controls, workflow token scopes, encrypted plan handoff and provenance checks.
7. Run static tests and Terraform validation without a remote backend.
8. Submit the solo-only PR to `develop` only after the release candidate is reviewed.

## Safety boundary

No AWS resources, IAM roles, OIDC providers, state buckets or permissions boundaries have been created. No backend has been initialized against AWS. No Terraform plan or apply has been run. All policy content remains design material pending review and explicit approval.


## 3B. Verified recognition handler call-site review — 14 Nov 2026

The recognition runtime policy was compared against the current handler and shared-library SDK call sites:

| Function | Verified AWS operations | Policy coverage |
|---|---|---|
| presign | DynamoDB PutItem (scan request); presigned S3 POST for `captures/*` | `dynamodb:PutItem`, `s3:PutObject`; KMS GenerateDataKey for SSE-KMS POST |
| result | DynamoDB GetItem (scan result) | `dynamodb:GetItem` on scan-results table |
| recognize | S3 HeadObject/GetObject and DeleteObject; Rekognition DetectFaces and SearchFacesByImage; DynamoDB GetItem/PutItem/UpdateItem across employees/config/scan-results/attendance; SQS async failure destination | `s3:GetObject`, `s3:DeleteObject`; DetectFaces on `*`; collection search on collection ARN; table actions on exact table ARNs; `sqs:SendMessage`; KMS Decrypt + GenerateDataKey |
| enroll | S3 HeadObject/GetObject and DeleteObject; Rekognition DetectFaces, SearchFacesByImage, IndexFaces and DeleteFaces; DynamoDB GetItem/UpdateItem for employees/config/scan-results; SQS async failure destination | Exact S3 prefix and table ARNs; DetectFaces on `*`; collection actions on collection ARN; `sqs:SendMessage`; KMS Decrypt + GenerateDataKey |
| enroll_url | DynamoDB GetItem (employee), PutItem (request); presigned S3 POST for `enroll/*` | `dynamodb:GetItem`, `dynamodb:PutItem`, `s3:PutObject`; KMS GenerateDataKey |
| faces_delete | DynamoDB GetItem/UpdateItem (employee), PutItem (audit); Rekognition DeleteFaces | Exact employee/audit table ARNs and collection ARN |
| failure | SQS event-source poller; DynamoDB GetItem/UpdateItem and Query attendance date index; Rekognition SearchFacesByImage/DeleteFaces; S3 GetObject/DeleteObject | SQS ReceiveMessage/DeleteMessage/GetQueueAttributes on the two source DLQs; KMS Decrypt; exact table/index, collection and raw-object prefixes |

Shared-library review confirmed that `record_scan` performs attendance GetItem/PutItem/UpdateItem and employee GetItem, while `get_settings` performs config GetItem. Those actions are included in the recognize role policy.

Least-privilege correction: removed `sqs:ChangeMessageVisibility` from the failure processor role. The Lambda SQS event-source execution-role documentation and AWSLambdaSQSQueueExecutionRole managed policy identify ReceiveMessage, DeleteMessage and GetQueueAttributes as the required queue operations for this integration. The handler itself does not call ChangeMessageVisibility.

Rekognition scope: AWS documents that DetectFaces does not support a collection resource ARN, so its `Resource: "*"` is necessary. Collection-bound SearchFacesByImage, IndexFaces and DeleteFaces remain scoped to the single attendance collection.

KMS split:
- presign/enroll_url: GenerateDataKey for presigned single-object uploads to SSE-KMS S3.
- recognize/enroll: Decrypt for raw-image reads and Decrypt + GenerateDataKey for encrypted SQS async-destination producer use.
- failure: Decrypt for encrypted SQS event-source consumption and raw-image reads.
- result/faces_delete: no direct KMS operations identified.

This is a static call-site/policy reconciliation, not a deployed AWS authorization test. Exact AWS account policies, permissions boundaries and live service delivery remain unverified.


## 3C. Data runtime IAM reconciliation — 14 Nov 2026

The seven data handlers were reviewed against their actual boto3 call sites and the per-function policy map in `infra/modules/data/main.tf`:

| Function | SDK operations | Required policy scope | Finding |
|---|---|---|---|
| employees | DynamoDB GetItem, Scan, PutItem, UpdateItem; audit PutItem | employees table Get/Scan/Put/Update; audit table Put | Exact actions/resources present |
| attendance_query | DynamoDB Scan employees; Query attendance table and date-index GSI | employees table Scan; attendance table and `/index/date-index` Query | Exact actions/resources present |
| daily_job | Scan employees; Query attendance date-index; GetItem config; PutItem/UpdateItem attendance; S3 PutObject reports/daily/*; SNS Publish on failure | Exact DynamoDB table/index ARNs; daily report object prefix; alert topic ARN | Exact actions/resources present |
| weekly_job | Scan employees; Query attendance by employee key; GetItem config; S3 PutObject reports/weekly/*; SNS Publish on failure | Exact DynamoDB table/index ARNs; weekly report object prefix; alert topic ARN | Exact actions/resources present |
| reports | S3 GetObject JSON; HeadObject CSV; presigned GetObject URL | S3 GetObject on reports/* | Exact action; HeadObject is authorized by GetObject |
| override | GetItem employees/attendance; PutItem attendance/audit | Exact employee, attendance and audit table ARNs | Exact actions/resources present; no UpdateItem required |
| settings | Config GetItem via get_settings; PutItem config; PutItem audit | Exact config and audit table ARNs | Exact actions/resources present; no UpdateItem required |

KMS review:
- daily_job and weekly_job each write report JSON and CSV objects through single-part `PutObject`; the role's `kms:GenerateDataKey` grant is scoped to the project CMK.
- reports reads the generated report JSON using `GetObject`; its `kms:Decrypt` grant is scoped to the same CMK.
- No data handler requires direct KMS access for DynamoDB table encryption; DynamoDB performs encryption/decryption on behalf of the caller.
- The report bucket policy and CMK resource policy still need validation in the foundation policy task. This static call-site audit does not prove live authorization.

Logging:
- Each data Lambda receives `logs:CreateLogStream` and `logs:PutLogEvents` scoped to its Terraform-managed log group ARN suffix.
- Log-group creation is provisioned by Terraform, so runtime roles do not need `logs:CreateLogGroup`.

Scheduler:
- Each Scheduler execution role has `lambda:InvokeFunction` on only its matching daily or weekly Lambda ARN.
- The Scheduler trust policy currently trusts `scheduler.amazonaws.com` without source-account/source-schedule conditions. This is a confused-deputy hardening item tracked separately as T32; do not consider the trust policy finalized.

Conclusion: no missing data-handler API actions or unjustified data-handler KMS grants were found in the current policy map. This is static code/policy reconciliation; AWS live authorization remains unverified.
