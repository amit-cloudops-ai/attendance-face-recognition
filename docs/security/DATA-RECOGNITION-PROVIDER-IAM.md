# Data and recognition modules — Terraform provider IAM action inventory

**Task:** T07  
**Target:** AWS provider v6.73.0, region `us-east-1`  
**Status:** static provider-source/API mapping; no AWS authorization test performed.

## Provider source reviewed

- [DynamoDB table](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/dynamodb/table.go)
- [CloudWatch Logs group](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/logs/group.go)
- [CloudWatch metric alarm](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/cloudwatch/metric_alarm.go)
- [IAM role](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/iam/role.go) and [inline role policy](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/iam/role_policy.go)
- [Lambda function](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/lambda/function.go), [permission](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/lambda/permission.go), [event source mapping](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/lambda/event_source_mapping.go), and [event invoke config](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/lambda/function_event_invoke_config.go)
- [EventBridge Scheduler schedule](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/scheduler/schedule.go)
- [SQS queue](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/sqs/queue.go) and [redrive allow policy](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/sqs/queue_redrive_allow_policy.go)
- [Rekognition collection](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/rekognition/collection.go)
- [S3 bucket notification](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/s3/bucket_notification.go)

The exact resolved provider version is evidenced by CI run [43613054015](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43613054015). T33 separately tracks pinning and committing the lockfiles.

## Resource-to-API mapping

| Terraform resource | Provider/API operations | IAM actions |
|---|---|---|
| `aws_dynamodb_table` (employees, attendance, scan-results, config, audit) | CreateTable; DescribeTable; UpdateTable; DeleteTable; DescribeTimeToLive; UpdateTimeToLive; DescribeContinuousBackups; UpdateContinuousBackups; ListTagsOfResource; TagResource/UntagResource | `dynamodb:CreateTable`, `dynamodb:DescribeTable`, `dynamodb:UpdateTable`, `dynamodb:DeleteTable`, `dynamodb:DescribeTimeToLive`, `dynamodb:UpdateTimeToLive`, `dynamodb:DescribeContinuousBackups`, `dynamodb:UpdateContinuousBackups`, `dynamodb:ListTagsOfResource`, `dynamodb:TagResource`, `dynamodb:UntagResource` |
| `aws_cloudwatch_log_group` | CreateLogGroup; DescribeLogGroups; PutRetentionPolicy; DeleteLogGroup; ListTagsForResource; TagResource/UntagResource | `logs:CreateLogGroup`, `logs:DescribeLogGroups`, `logs:PutRetentionPolicy`, `logs:DeleteLogGroup`, `logs:ListTagsForResource`, `logs:TagResource`, `logs:UntagResource` |
| `aws_cloudwatch_metric_alarm` | PutMetricAlarm; DescribeAlarms; DeleteAlarms | `cloudwatch:PutMetricAlarm`, `cloudwatch:DescribeAlarms`, `cloudwatch:DeleteAlarms` |
| `aws_iam_role` | CreateRole; GetRole; UpdateAssumeRolePolicy; PutRolePermissionsBoundary; DeleteRole; ListRoleTags; TagRole/UntagRole | `iam:CreateRole`, `iam:GetRole`, `iam:UpdateAssumeRolePolicy`, `iam:PutRolePermissionsBoundary`, `iam:DeleteRole`, `iam:ListRoleTags`, `iam:TagRole`, `iam:UntagRole` |
| `aws_iam_role_policy` | PutRolePolicy; GetRolePolicy; DeleteRolePolicy | `iam:PutRolePolicy`, `iam:GetRolePolicy`, `iam:DeleteRolePolicy` |
| `aws_lambda_function` | CreateFunction; GetFunction; GetFunctionConfiguration; UpdateFunctionCode; UpdateFunctionConfiguration; DeleteFunction; PublishVersion; Get/Put/DeleteFunctionConcurrency; ListTags; TagResource/UntagResource; GetLayerVersion for configured layer | `lambda:CreateFunction`, `lambda:GetFunction`, `lambda:GetFunctionConfiguration`, `lambda:UpdateFunctionCode`, `lambda:UpdateFunctionConfiguration`, `lambda:DeleteFunction`, `lambda:PublishVersion`, `lambda:GetFunctionConcurrency`, `lambda:PutFunctionConcurrency`, `lambda:DeleteFunctionConcurrency`, `lambda:ListTags`, `lambda:TagResource`, `lambda:UntagResource`, `lambda:GetLayerVersion`, plus `iam:PassRole` on the exact execution role |
| `aws_lambda_permission` | AddPermission; GetPolicy; RemovePermission | `lambda:AddPermission`, `lambda:GetPolicy`, `lambda:RemovePermission` |
| `aws_lambda_event_source_mapping` | CreateEventSourceMapping; GetEventSourceMapping; UpdateEventSourceMapping; DeleteEventSourceMapping | `lambda:CreateEventSourceMapping`, `lambda:GetEventSourceMapping`, `lambda:UpdateEventSourceMapping`, `lambda:DeleteEventSourceMapping` |
| `aws_lambda_function_event_invoke_config` | PutFunctionEventInvokeConfig; GetFunctionEventInvokeConfig; DeleteFunctionEventInvokeConfig | `lambda:PutFunctionEventInvokeConfig`, `lambda:GetFunctionEventInvokeConfig`, `lambda:DeleteFunctionEventInvokeConfig` |
| `aws_scheduler_schedule_group.attendance` | CreateScheduleGroup; GetScheduleGroup; DeleteScheduleGroup; tag operations | `scheduler:CreateScheduleGroup`, `scheduler:GetScheduleGroup`, `scheduler:DeleteScheduleGroup`, `scheduler:TagResource`, `scheduler:UntagResource`, `scheduler:ListTagsForResource` |
| `aws_scheduler_schedule` | CreateSchedule; GetSchedule; UpdateSchedule; DeleteSchedule | `scheduler:CreateSchedule`, `scheduler:GetSchedule`, `scheduler:UpdateSchedule`, `scheduler:DeleteSchedule`, plus `iam:PassRole` on the exact Scheduler role |
| `aws_sqs_queue` | CreateQueue; GetQueueAttributes; SetQueueAttributes; DeleteQueue; ListQueueTags; TagQueue/UntagQueue | `sqs:CreateQueue`, `sqs:GetQueueAttributes`, `sqs:SetQueueAttributes`, `sqs:DeleteQueue`, `sqs:ListQueueTags`, `sqs:TagQueue`, `sqs:UntagQueue` |
| `aws_sqs_queue_redrive_allow_policy` | GetQueueAttributes; SetQueueAttributes | `sqs:GetQueueAttributes`, `sqs:SetQueueAttributes` |
| `aws_rekognition_collection` | CreateCollection; DescribeCollection; DeleteCollection | `rekognition:CreateCollection`, `rekognition:DescribeCollection`, `rekognition:DeleteCollection` |
| `aws_s3_bucket_notification` | GetBucketNotificationConfiguration; PutBucketNotificationConfiguration | `s3:GetBucketNotification`, `s3:PutBucketNotification` |
| Local `aws_iam_policy_document` data and package files | Local generation only | No AWS IAM actions |

## Resource scoping

### DynamoDB

Use exact table ARNs:
- `attendance-<env>-employees`
- `attendance-<env>-attendance`
- `attendance-<env>-scan-results`
- `attendance-<env>-config`
- `attendance-<env>-audit`

The attendance date GSI is `arn:aws:dynamodb:us-east-1:<account>:table/attendance-<env>-attendance/index/date-index`. Table and index ARNs must be separated where an action requires the index. Tag actions apply only to the table ARN.

### CloudWatch Logs and alarms

- `logs:DescribeLogGroups` is a list operation with no resource-level scope; use `Resource: "*"` for that action only.
- Log-group create/read/retention/delete/tag actions use `arn:aws:logs:us-east-1:<account>:log-group:/aws/lambda/attendance-<env>-*:* `.
- Alarm actions use `arn:aws:cloudwatch:us-east-1:<account>:alarm:attendance-<env>-*`. The configured alarms are standard metric alarms, not composite alarms; keep DescribeAlarms scoped to those alarm ARNs.

### IAM roles and PassRole

- Lambda execution role ARNs use `arn:aws:iam::<account>:role/attendance-<env>-<function>`.
- Scheduler role ARNs use the exact daily/weekly scheduler role names in the module.
- `iam:CreateRole` must be constrained by `iam:PermissionsBoundary` to the matching environment boundary ARN and the role-name prefix `attendance-<env>-*`.
- `iam:PutRolePermissionsBoundary` must be constrained to that same boundary. Do not grant `iam:DeleteRolePermissionsBoundary`; the boundary is mandatory.
- `iam:PassRole` is limited to the exact Lambda execution roles with `iam:PassedToService=lambda.amazonaws.com`, and the exact Scheduler roles with `iam:PassedToService=scheduler.amazonaws.com`.
- The modules use inline role policies; do not grant `iam:AttachRolePolicy`, `iam:ListAttachedRolePolicies`, or managed-policy administration.

### Lambda

- Function actions use exact `attendance-<env>-<function>` function ARNs.
- `lambda:GetLayerVersion` uses the exact versioned common-layer ARN returned by the foundation module.
- `lambda:CreateEventSourceMapping` does not support a resource ARN at creation time; use `Resource: "*"` with the `lambda:FunctionArn` condition fixed to the failure-processor function. Read/update/delete use the event-source-mapping ARN pattern and the same function condition.
- Lambda permission and function event-invoke-config actions are limited to the recognize/enroll functions and the exact raw-bucket source ARN where the provider request supports it.
- The function execution role's inline policy is separate from the deployment role's ability to create/update that policy.

### SQS, Rekognition and S3 notification

- SQS queue actions use the exact three queue ARNs: recognize DLQ, enroll DLQ and failure-processor redrive target. The event-source mapping consumes the recognize/enroll queues; the failure-processor queue is only the redrive target and is not consumed by the failure Lambda.
- Rekognition `CreateCollection` has no resource-level authorization; it requires `Resource: "*"`. `DescribeCollection` and `DeleteCollection` are scoped to `arn:aws:rekognition:us-east-1:<account>:collection/attendance-<env>-faces`. No collection tags are configured, so no Rekognition tagging actions are needed.
- S3 notification read/write actions are scoped to the raw bucket ARN only.

## KMS dependency for DynamoDB table provisioning

The five DynamoDB tables are configured with the foundation customer-managed KMS key. AWS requires the principal selecting a customer-managed key for a DynamoDB table to have, at minimum:

- `kms:Encrypt`
- `kms:Decrypt`
- `kms:ReEncryptFrom` and `kms:ReEncryptTo`
- `kms:GenerateDataKey` and `kms:GenerateDataKeyWithoutPlaintext`
- `kms:DescribeKey`
- `kms:CreateGrant`

These are deployment-role permissions for the DynamoDB table provisioning path, not runtime Lambda permissions. Constrain the cryptographic actions to the exact environment key ARN, `kms:ViaService=dynamodb.us-east-1.amazonaws.com`, and the environment alias. Constrain `kms:CreateGrant` with `kms:GrantIsForAWSResource=true` and the DynamoDB ViaService condition. The customer-managed-key policy uses the AWS-documented `kms:ViaService` authorization model for DynamoDB. AWS's direct `dynamodb.amazonaws.com` key-metadata statement is part of the AWS-managed-key example and is not required by the customer-managed-key policy example.

The runtime boundary templates in T05 intentionally do not include DynamoDB KMS operations because Lambda handlers do not directly call KMS for DynamoDB encryption. GitHub apply roles are not subject to those runtime boundaries.

## Deployment-policy implications

- Plan roles need the read actions for every configured resource, including DynamoDB table/TTL/PITR reads, IAM role reads, Lambda configuration reads, log group/alarm reads, Scheduler schedule reads, SQS queue reads, Rekognition collection describe, and S3 notification reads.
- Apply roles add the create/update/delete/tag actions listed above, exact `iam:PassRole`, and DynamoDB KMS use actions.
- No data/recognition provider resource requires `iam:AttachRolePolicy`, `iam:CreatePolicy`, `lambda:InvokeFunction`, `sqs:SendMessage`, or application runtime DynamoDB/S3 permissions for the deployment principal.
- Do not use service-wide wildcards. The only required `Resource: "*"` cases identified here are `logs:DescribeLogGroups`, `lambda:CreateEventSourceMapping` with a function condition, and `rekognition:CreateCollection`.

## AWS authorization references

- [DynamoDB Service Authorization Reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazondynamodb.html)
- [CloudWatch Logs Service Authorization Reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazoncloudwatchlogs.html)
- [CloudWatch Service Authorization Reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_cloudwatch.html)
- [IAM Service Authorization Reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_awsidentityandaccessmanagementiam.html)
- [Lambda Service Authorization Reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_awslambda.html)
- [EventBridge Scheduler Service Authorization Reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazoneventbridgescheduler.html)
- [SQS Service Authorization Reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazonsqs.html)
- [Rekognition Service Authorization Reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_rekognition.html)
- [S3 Service Authorization Reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_s3.html)
- [DynamoDB customer-managed key permissions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/encryption.usagenotes.html)
