# Foundation module — Terraform provider IAM action inventory

**Task:** T06  
**Target:** AWS provider v6.73.0, region `us-east-1`  
**Status:** static provider-source/API mapping; no AWS authorization test performed.

## Provider version evidence

GitHub Actions run [43613054015](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43613054015) resolved `hashicorp/aws v6.73.0` and `hashicorp/archive v2.8.1`. The environment roots currently allow AWS provider `>= 5.0, < 7.0`, and no `.terraform.lock.hcl` is committed. The mapping below is therefore specific to the v6.73.0 provider source used by that run, not a guarantee for every allowed version. T33 tracks pinning and committing the lockfiles.

Provider source inspected at tag `v6.73.0`:
- [S3 bucket resource](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/s3/bucket.go) and split bucket resources under `internal/service/s3/`.
- [KMS key resource](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/kms/key.go), [KMS alias](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/kms/alias.go), and generated [KMS tagging operations](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/kms/tags_gen.go).
- [SNS topic](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/sns/topic.go) and [SNS subscription](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/sns/topic_subscription.go).
- [Lambda layer version](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/lambda/layer_version.go).
- [AWS Budget](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/budgets/budget.go).

## Resource-to-API mapping

| Terraform resource | Provider API operations | IAM actions required |
|---|---|---|
| `aws_kms_key.attendance` | CreateKey; DescribeKey; GetKeyPolicy; GetKeyRotationStatus; UpdateKeyDescription; PutKeyPolicy; Enable/DisableKey; Enable/DisableKeyRotation; ScheduleKeyDeletion; ListResourceTags; TagResource/UntagResource | `kms:CreateKey`, `kms:DescribeKey`, `kms:GetKeyPolicy`, `kms:PutKeyPolicy`, `kms:GetKeyRotationStatus`, `kms:UpdateKeyDescription`, `kms:EnableKeyRotation`, `kms:DisableKeyRotation`, `kms:EnableKey`, `kms:DisableKey`, `kms:ScheduleKeyDeletion`, `kms:ListResourceTags`, `kms:TagResource`, `kms:UntagResource` |
| `aws_kms_alias.attendance` | CreateAlias; ListAliases; UpdateAlias; DeleteAlias | `kms:CreateAlias`, `kms:ListAliases`, `kms:UpdateAlias`, `kms:DeleteAlias` |
| `aws_s3_bucket.{raw,reports,web}` | CreateBucket; HeadBucket; GetBucketLocation; read bucket policy/ACL/CORS/website/versioning/accelerate/request-payment/logging/lifecycle/replication/encryption/object-lock; DeleteBucket; S3 Control tag operations | `s3:CreateBucket`, `s3:DeleteBucket`, `s3:ListBucket`, `s3:GetBucketLocation`, `s3:GetBucketPolicy`, `s3:GetBucketAcl`, `s3:GetBucketCORS`, `s3:GetBucketWebsite`, `s3:GetBucketVersioning`, `s3:GetAccelerateConfiguration`, `s3:GetBucketRequestPayment`, `s3:GetBucketLogging`, `s3:GetLifecycleConfiguration`, `s3:GetReplicationConfiguration`, `s3:GetEncryptionConfiguration`, `s3:GetBucketObjectLockConfiguration`, `s3:TagResource`, `s3:UntagResource`, `s3:ListTagsForResource` |
| `aws_s3_bucket_public_access_block.buckets` | GetPublicAccessBlock; PutPublicAccessBlock; DeletePublicAccessBlock | `s3:GetBucketPublicAccessBlock`, `s3:PutBucketPublicAccessBlock` |
| `aws_s3_bucket_server_side_encryption_configuration.buckets` | GetBucketEncryption; PutBucketEncryption; DeleteBucketEncryption | `s3:GetEncryptionConfiguration`, `s3:PutEncryptionConfiguration` |
| `aws_s3_bucket_cors_configuration.raw` | GetBucketCors; PutBucketCors; DeleteBucketCors | `s3:GetBucketCORS`, `s3:PutBucketCORS` |
| `aws_s3_bucket_versioning.reports` | GetBucketVersioning; PutBucketVersioning | `s3:GetBucketVersioning`, `s3:PutBucketVersioning` |
| `aws_s3_bucket_lifecycle_configuration.raw` | GetBucketLifecycleConfiguration; PutBucketLifecycleConfiguration; DeleteBucketLifecycle | `s3:GetLifecycleConfiguration`, `s3:PutLifecycleConfiguration` |
| `aws_s3_bucket_policy.buckets` (raw/reports) | GetBucketPolicy; PutBucketPolicy; DeleteBucketPolicy | `s3:GetBucketPolicy`, `s3:PutBucketPolicy`, `s3:DeleteBucketPolicy` |
| `aws_sns_topic.alerts` | CreateTopic; GetTopicAttributes; SetTopicAttributes; DeleteTopic; tag/list-tag operations | `sns:CreateTopic`, `sns:GetTopicAttributes`, `sns:SetTopicAttributes`, `sns:DeleteTopic`, `sns:TagResource`, `sns:UntagResource`, `sns:ListTagsForResource` |
| `aws_sns_topic_subscription.email` | Subscribe; GetSubscriptionAttributes; SetSubscriptionAttributes; Unsubscribe | `sns:Subscribe`, `sns:GetSubscriptionAttributes`, `sns:SetSubscriptionAttributes`, `sns:Unsubscribe` |
| `aws_lambda_layer_version.common` | PublishLayerVersion; GetLayerVersion; DeleteLayerVersion | `lambda:PublishLayerVersion`, `lambda:GetLayerVersion`, `lambda:DeleteLayerVersion` |
| AWS Budgets | Moved to the isolated `infra/billing` root; excluded from foundation and environment apply roles | Dedicated billing plan/apply role only; requires `budgets:ModifyBudget`, `budgets:ViewBudget`, `aws-portal:ModifyBilling`, `aws-portal:ViewBilling` |
| `data.archive_file.common_layer`; `data.aws_iam_policy_document.*` | Local archive/policy-document generation only | No AWS IAM actions |

## Important provider behavior and least-privilege scope

### S3 bucket reads are broader than the split configuration resources

The v6.73.0 `aws_s3_bucket` read path inspects legacy bucket attributes even though this configuration manages those settings with split resources. The apply and plan roles therefore need the read actions in the `aws_s3_bucket` row for all three bucket ARNs. `HeadBucket` maps to `s3:ListBucket`; the provider also resolves the bucket region, requiring `s3:GetBucketLocation`. Do not grant `s3:ListAllMyBuckets`; it is not part of this resource's read path.

The configured `force_destroy = false` means bucket deletion must not enumerate/delete objects. Do not grant object deletion or object listing to the foundation deployment role for bucket destruction.

Provider v6.23+ uses S3 Control `TagResource`, `UntagResource`, and `ListTagsForResource` for general-purpose bucket tags; the provider can fall back to legacy `PutBucketTagging`/ `GetBucketTagging` if those permissions are absent. The policy should grant the current S3 Control tag operations rather than relying on fallback behavior.

### KMS resources

- `kms:CreateKey` has no resource type and must use `Resource: "*"`; constrain it with request-tag conditions for Project=attendance and Environment=dev or prod.
- Key read/write actions are scoped to the one environment key ARN. KMS tag operations are scoped to that key ARN and environment tags.
- `kms:CreateAlias` and `kms:UpdateAlias` require the alias and key resources; `kms:DeleteAlias` is scoped to the exact alias ARN. `kms:ListAliases` has no resource-level scope.
- KMS key creation itself does not require runtime cryptographic permissions. However, T07 found that the data module creates DynamoDB tables encrypted with this customer-managed key; AWS requires the principal selecting that key for a table to have `kms:Encrypt`, `kms:Decrypt`, `kms:ReEncryptFrom`, `kms:ReEncryptTo`, `kms:GenerateDataKey`, `kms:GenerateDataKeyWithoutPlaintext`, `kms:DescribeKey`, and `kms:CreateGrant`, constrained to DynamoDB via `kms:ViaService`. These are deployment-role permissions, not Lambda runtime permissions. See `docs/security/DATA-RECOGNITION-PROVIDER-IAM.md` and task T36 for the missing DynamoDB service-principal key-policy statement.

### SNS email subscription

The configured endpoint protocol is `email`. In provider v6.73.0, `waitForConfirmation` returns false for email, so the resource does not use the `ListSubscriptionsByTopic` confirmation lookup path. Do not grant `sns:ListSubscriptionsByTopic` for this configuration. The subscription still needs Subscribe, Get/SetSubscriptionAttributes and Unsubscribe for lifecycle operations.

### AWS Budgets — elevated account-level dependency

The AWS Service Authorization Reference maps budget creation/update/deletion and notification create/delete operations to `budgets:ModifyBudget` plus `aws-portal:ModifyBilling`; describe operations map to `budgets:ViewBudget` plus `aws-portal:ViewBilling`. The `budgets:*` actions can be scoped to the exact budget ARN, but the `aws-portal` actions have no resource-level scope and require `Resource: "*"`.

This is materially broader than the rest of the foundation module. The budget resources are isolated in `infra/billing`, a separate Terraform root with its own `attendance/billing/terraform.tfstate` state key. The standard dev/prod environment roots no longer manage budgets and their deployment policies must not receive `aws-portal:ModifyBilling` or `aws-portal:ViewBilling`. Only a dedicated billing role should manage this root.

## Resource and condition scoping requirements

- S3 bucket-level actions use exact bucket ARNs. S3 Control tag actions use the corresponding bucket ARN. Object ARNs are not needed by Terraform for these bucket-configuration resources.
- KMS key actions use the exact key ARN except `kms:CreateKey` (no resource-level support) and `kms:ListAliases` (list action). Use request-tag conditions on CreateKey and resource-tag conditions on key mutation where AWS supports them.
- KMS alias actions use the exact alias ARN and target key ARN as required by the action's resource types.
- SNS topic actions use the exact topic ARN; subscription actions use the exact topic ARN for Subscribe and subscription ARN pattern for subscription read/update/delete.
- Lambda layer actions use the exact `attendance-<env>-common` layer ARN, with version wildcard only where the API requires a version ARN.
- Budget actions use `arn:aws:budgets::${account_id}:budget/attendance-<env>-monthly-cost`; the dependent `aws-portal` permissions remain account-wide.

## Additional blockers discovered

- **T33 — Provider reproducibility:** root constraints allow AWS provider `>=5,<7` and no lockfile is committed. Pin the reviewed provider version and commit dev/prod lockfiles before finalizing IAM policies.
- **T34 — Budget isolation:** implemented in `infra/billing`; CI validates the root. Dedicated billing plan/apply policy and role wiring remain a separate deployment gate.
- **T35 — CloudFront KMS scope:** foundation key policy currently permits CloudFront OAC decrypt for any distribution in the account. Move the grant to a point where the exact distribution ARN is available, or otherwise constrain it to the single project distribution before bootstrap.

## AWS authorization references

- [Amazon S3 Service Authorization Reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_s3.html)
- [AWS KMS Service Authorization Reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_kms.html)
- [Amazon SNS Service Authorization Reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_sns.html)
- [AWS Lambda Service Authorization Reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_lambda.html)
- [AWS Budgets Service Authorization Reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_budgets.html)
