# IAM least-privilege inventory — deployment roles

**Repository branch:** `solo/amit-monday`  
**Target account:** existing AWS account (account ID is intentionally not recorded here)  
**Target region:** `us-east-1`  
**Status:** action inventory draft; no IAM policy has been attached and no AWS role has been created.

This document derives the initial IAM inventory from the Terraform resource types in the four modules. It is a review baseline, not a final attachable policy. Exact AWS API-to-IAM action mappings, provider read paths, condition-key support, and resource-level authorization must be validated against the pinned AWS provider version and AWS service authorization references before role creation.

## 1. Role separation

| Role | Scope | Permission model |
|---|---|---|
| `attendance-github-plan-dev` | Dev root and dev state | Read/describe/list permissions plus dev state and lock-file access only |
| `attendance-github-apply-dev` | Dev root and dev state | Dev read permissions plus narrowly scoped dev resource mutations |
| `attendance-github-plan-prod` | Prod root and prod state | Read/describe/list permissions plus prod state and lock-file access only |
| `attendance-github-apply-prod` | Prod root and prod state | Prod read permissions plus narrowly scoped prod resource mutations |

Plan and apply roles must be separate for each environment. A plan role must not receive create, update, delete, publish, subscribe, tag, or IAM mutation permissions. Apply roles must not be granted account-wide administrator policies.

The GitHub OIDC trust relationship must require:
- Audience: `sts.amazonaws.com`
- Exact subject for dev: `repo:amit-cloudops-ai/attendance-face-recognition:environment:dev`
- Exact subject for prod: `repo:amit-cloudops-ai/attendance-face-recognition:environment:prod`

The GitHub Environment branch restrictions remain mandatory: dev only from `develop`, prod only from `main`; prod requires reviewer approval.

## 2. Terraform-managed resource inventory

The current module source declares these resource families:

| Module | Terraform resource types |
|---|---|
| foundation | KMS key and alias; S3 buckets, public-access blocks, encryption, CORS, versioning, lifecycle, bucket policies; SNS topic and subscription; Lambda layer; AWS Budget |
| data | DynamoDB tables; CloudWatch log groups and metric alarms; IAM Lambda/scheduler roles and inline policies; Lambda functions; EventBridge Scheduler schedules |
| recognition | Rekognition collection; SQS queues and redrive policy; CloudWatch log groups and alarms; IAM Lambda roles and inline policies; Lambda functions, async invoke config, event source mapping and permission; S3 bucket notification |
| access | Cognito user pool, groups, domain and app client; API Gateway v2 API, authorizer, integrations, routes and stage; Lambda permissions; CloudFront OAC, cache/origin-request/response-header policies, function and distribution; S3 bucket policy and frontend objects |

## 3. Candidate read permissions for plan roles

The following are the service action families that must be evaluated for Terraform refresh and plan. Keep `List*` and account/global discovery calls on `Resource: "*"` only where AWS does not support resource-level scoping; constrain all other reads to the exact dev or prod resource ARNs.

- **S3:** `s3:GetBucketLocation`, `s3:GetBucketTagging`, `s3:GetBucketPolicy`, `s3:GetBucketPublicAccessBlock`, `s3:GetEncryptionConfiguration`, `s3:GetLifecycleConfiguration`, `s3:GetBucketVersioning`, `s3:GetBucketCORS`, `s3:GetBucketNotification`, `s3:GetBucketOwnershipControls`, `s3:ListBucket`, `s3:GetObject`, and required bucket/object tagging reads.
- **KMS:** `kms:DescribeKey`, `kms:GetKeyPolicy`, `kms:ListResourceTags`, `kms:ListAliases`.
- **SNS:** `sns:GetTopicAttributes`, `sns:GetSubscriptionAttributes`, `sns:ListSubscriptionsByTopic`, `sns:ListTagsForResource`.
- **Lambda and layers:** `lambda:GetFunction`, `lambda:GetFunctionConfiguration`, `lambda:GetPolicy`, `lambda:GetLayerVersion`, `lambda:ListLayerVersions`, `lambda:ListTags`, and event-source / async-invoke configuration reads.
- **DynamoDB:** `dynamodb:DescribeTable`, `dynamodb:DescribeContinuousBackups`, `dynamodb:DescribeTimeToLive`, `dynamodb:ListTagsOfResource`.
- **IAM:** `iam:GetRole`, `iam:GetRolePolicy`, `iam:ListRolePolicies`, `iam:ListAttachedRolePolicies`, `iam:ListRoleTags`, and boundary/policy metadata reads needed by the provider.
- **CloudWatch Logs and alarms:** `logs:DescribeLogGroups`, `logs:ListTagsForResource`, `cloudwatch:DescribeAlarms`.
- **EventBridge Scheduler:** `scheduler:GetSchedule`, `scheduler:ListTagsForResource`.
- **Rekognition:** `rekognition:DescribeCollection`, `rekognition:ListCollections`, `rekognition:ListTagsForResource`.
- **SQS:** `sqs:GetQueueAttributes`, `sqs:GetQueueUrl`, `sqs:ListQueueTags`.
- **Cognito:** `cognito-idp:DescribeUserPool`, `cognito-idp:DescribeUserPoolClient`, `cognito-idp:DescribeUserPoolDomain`, `cognito-idp:ListTagsForResource`, `cognito-idp:ListUserPoolClients`, `cognito-idp:ListGroups`.
- **API Gateway v2:** `apigateway:GET` for the specific API, authorizer, integration, route and stage paths.
- **CloudFront:** `cloudfront:GetDistribution`, `cloudfront:GetDistributionConfig`, `cloudfront:ListDistributions`, `cloudfront:GetOriginAccessControl`, cache/origin-request/response-header policy reads, function reads and `cloudfront:ListTagsForResource`.
- **Budgets:** `budgets:ViewBudget`, `budgets:DescribeBudget`, `budgets:DescribeNotificationsForBudget`, `budgets:DescribeSubscribersForNotification`.

This is a candidate inventory. Some AWS provider resources use additional describe/list calls or require `Resource: "*"`; confirm these through provider documentation and a non-mutating plan before finalizing.

## 4. Candidate apply permissions

Apply roles receive the read set above plus only the mutation families required by the declared Terraform resources:

- **S3:** `s3:CreateBucket`, `s3:DeleteBucket`, `s3:PutBucket*`, `s3:DeleteBucketPolicy`, `s3:PutBucketPolicy`, `s3:PutObject`, `s3:DeleteObject`, and the required object tagging operations. Scope bucket actions to the exact environment buckets and object actions to their object ARNs.
- **KMS:** `kms:CreateKey`, `kms:PutKeyPolicy`, `kms:EnableKeyRotation`, `kms:CreateAlias`, `kms:UpdateAlias`, `kms:DeleteAlias`, `kms:TagResource`, `kms:UntagResource`, plus deletion-scheduling actions only if destroy is deliberately supported.
- **SNS:** `sns:CreateTopic`, `sns:DeleteTopic`, `sns:SetTopicAttributes`, `sns:Subscribe`, `sns:Unsubscribe`, subscription attribute changes and topic tagging.
- **Lambda:** `lambda:CreateFunction`, `lambda:UpdateFunctionCode`, `lambda:UpdateFunctionConfiguration`, `lambda:DeleteFunction`, layer publish/delete, permission add/remove, event-source mapping create/update/delete, and async-invoke configuration put/delete.
- **DynamoDB:** `dynamodb:CreateTable`, `dynamodb:UpdateTable`, `dynamodb:DeleteTable`, `dynamodb:UpdateTimeToLive`, `dynamodb:UpdateContinuousBackups`, `dynamodb:TagResource`, `dynamodb:UntagResource`.
- **IAM:** role create/delete, trust-policy update, inline-policy put/delete, tagging and permissions-boundary attachment. Every role mutation must be constrained to the environment's exact role-name prefix and mandatory permissions boundary.
- **Logs / CloudWatch:** log group create/delete, retention updates and tagging; `cloudwatch:PutMetricAlarm`, `cloudwatch:DeleteAlarms`.
- **Scheduler:** schedule create/update/delete and tagging.
- **Rekognition:** collection create/delete and resource tagging.
- **SQS:** queue create/delete, attribute updates and queue tagging.
- **Cognito:** user pool/client/domain/group create/update/delete and tagging.
- **API Gateway v2:** API, authorizer, integration, route and stage create/update/delete actions through the API Gateway v2 IAM action namespace.
- **CloudFront:** distribution, OAC, cache policy, origin-request policy, response-header policy and function create/update/publish/delete actions, plus tagging.
- **Budgets:** budget create/modify/delete and the notification/subscriber create/delete operations managed by the budget resource.
- **PassRole:** `iam:PassRole` only for the exact environment Lambda execution roles and Scheduler target roles, conditioned on `iam:PassedToService` equal to `lambda.amazonaws.com` or `scheduler.amazonaws.com` as appropriate.

Do not treat wildcard suffixes such as `s3:PutBucket*` above as final policy statements. Expand them to the exact API actions required by each Terraform resource and provider version before attaching the policy.

## 5. Application execution roles are a separate trust boundary

The application Lambda and Scheduler execution roles are not the GitHub deployment roles. Their inline policies in Terraform must remain narrowly scoped to the runtime operations:

- Employee/admin functions: only the employee, audit and required attendance/config table operations.
- Attendance query: attendance table and date index queries, plus employee lookup.
- Daily/weekly jobs: employee/attendance/config reads, report-prefix object writes and alert-topic publish.
- Reports: report-prefix object reads only.
- Override/settings: narrowly scoped employee, attendance, config and audit table operations.
- Recognition/enrollment/cleanup functions: exact raw-bucket object operations, Rekognition collection operations, scan/employee/audit table operations, SQS/event destination operations, and KMS use required by the handler.
- Scheduler roles: invoke only their matching daily or weekly Lambda function.

The current Terraform declares these execution roles dynamically by environment and function/job name. Confirm each statement against the handler code before deployment; avoid broad DynamoDB, S3, Rekognition, SQS or KMS access.

## 6. Permissions boundary decision — required before CI can manage IAM

**Recommended design:** create one customer-managed execution-role permissions boundary per environment during a reviewed manual bootstrap, outside the application Terraform root. Require every Terraform-created Lambda and Scheduler role to attach that exact boundary ARN. Do not grant GitHub apply roles permission to edit or delete the boundary policy. The apply role may attach the boundary to approved role names, but must not remove or replace it.

The boundary must cap the union of the runtime permissions listed in Section 5. It does not grant permissions by itself; the execution role's inline policy must still grant each runtime action. Add a Terraform input for the boundary ARN and attach it to every `aws_iam_role` resource before granting CI role-creation permissions.

Without this control, an apply role with `iam:CreateRole` and `iam:PutRolePolicy` could create an execution role with permissions broader than the intended application policy and then pass it to Lambda or Scheduler. Do not create the GitHub apply roles until this boundary is designed and enforced.

## 7. State access remains separately scoped

For each environment, the deployment role may access only:
- `attendance/<env>/terraform.tfstate`
- `attendance/<env>/terraform.tfstate.tflock`

Use `s3:GetObject` and `s3:PutObject` for the state object; add `s3:DeleteObject` only for the lock object. Scope `s3:ListBucket` by `s3:prefix`. Do not allow dev to read or lock prod state, or vice versa.

The backend state bucket is a separate bootstrap resource and is not managed by the application Terraform roots. The backend region must be `us-east-1`.

## 8. Remaining verification gates

1. Confirm all provider and backend region literals use `us-east-1`, including Cognito issuer/domain and browser CSP endpoints.
2. Enumerate the full resource blocks and provider read paths in each module; validate action names and ARN support against AWS service authorization references.
3. Add and wire the execution-role boundary input across dev/prod roots and both modules that create IAM roles.
4. Produce four environment-specific policy documents with exact resource ARNs, tag conditions where supported, and minimal unavoidable wildcard actions.
5. Validate state bucket TLS/public-access/versioning/encryption policy separately.
6. Run static validation and CI on the updated branch.
7. Only then prepare the reviewed solo-only PR to `develop`.
8. Create AWS bootstrap resources only after presenting the exact resource list and obtaining explicit approval. Run a dev plan first; present the full plan and obtain separate explicit approval before any apply.

## Safety statement

No AWS resource has been provisioned by this work. No Terraform backend has been initialized against the account. No plan or apply has been run. The content above is an inventory and policy-design baseline, not authorization to create or modify AWS resources.
