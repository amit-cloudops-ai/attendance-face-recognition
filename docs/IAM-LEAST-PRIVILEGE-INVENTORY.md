# IAM least-privilege inventory — deployment and runtime roles

**Repository branch:** `solo/amit-monday`  
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
| failure | Recognition DLQs; scan-results, employees, attendance/date index; Rekognition collection; raw captures/enroll prefixes | SQS receive/delete/get-attributes/change-visibility; DynamoDB get/update/query; Rekognition search/delete; S3 get/delete |
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
- Verify DynamoDB update actions for override/settings and every handler; compare code call-sites with Terraform statements.
- Verify SQS permissions for Lambda asynchronous destinations versus the explicit failure consumer queues; keep each role scoped to its actual queue set.
- Verify the `rekognition:DetectFaces` action's resource-level support. Retain `Resource: "*"` only if AWS documents that resource scope is unsupported.
- Lambda logging requires scoped `logs:CreateLogStream` and `logs:PutLogEvents` on that function's log group ARN suffix. Verify log-group creation stays in Terraform, not runtime.

## 4. Deployment policy construction

Candidate service families to verify against provider read/write requests:
- S3 bucket configuration, policy, notification and object operations.
- KMS describe/key policy/tag/key/alias lifecycle actions.
- SNS topic/subscription operations.
- Lambda function/layer/invoke permission/event-source mapping/async invoke configuration.
- DynamoDB table, item, TTL, PITR and tag operations.
- IAM role, inline policy, permissions boundary and pass-role operations.
- CloudWatch log groups/alarms and EventBridge Scheduler schedule operations.
- Rekognition collection, SQS queue/redrive policies.
- Cognito, API Gateway v2 and CloudFront resources/policies/functions/distribution.
- AWS Budgets resources and notifications.
- S3 remote state and native lock object operations.

The earlier candidate action inventory must be expanded to exact IAM action names (not service wildcards), exact ARNs, resource tags and supported condition keys. Use `iam:PassRole` only for exact environment-specific execution role ARNs and condition it by `iam:PassedToService`.

## 5. Execution-role permissions boundaries

Create two customer-managed boundary policies during a separately reviewed manual bootstrap:
- `attendance-dev-execution-boundary`
- `attendance-prod-execution-boundary`

Each boundary caps the union of the runtime permissions required by the application roles in that environment. A permissions boundary does not grant permissions; each role still needs its own least-privilege inline policy.

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
