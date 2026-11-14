# Access module — Terraform provider IAM action inventory

**Task:** T08  
**Target:** AWS provider v6.73.0; canonical region is `config/deployment.json` (`us-east-1`)  
**Status:** static provider-source/API mapping; no AWS authorization test performed.

## Provider source reviewed

- Cognito user pool: [pool](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/cognitoidp/user_pool.go), [app client](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/cognitoidp/user_pool_client.go), [domain](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/cognitoidp/user_pool_domain.go), [groups](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/cognitoidp/user_group.go).
- API Gateway v2: [API](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/apigatewayv2/api.go), [authorizer](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/apigatewayv2/authorizer.go), [integration](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/apigatewayv2/integration.go), [route](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/apigatewayv2/route.go), [stage](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/apigatewayv2/stage.go).
- CloudFront: [distribution](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/cloudfront/distribution.go), [origin access control](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/cloudfront/origin_access_control.go), [cache policy](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/cloudfront/cache_policy.go), [origin request policy](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/cloudfront/origin_request_policy.go), [response headers policy](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/cloudfront/response_headers_policy.go), [function](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/cloudfront/function.go).
- S3 object and bucket policy: [object](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/s3/object.go), [bucket policy](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/s3/bucket_policy.go).
- API Gateway v2 and CloudFront resource/action scopes cross-checked against the current AWS Service Authorization References. Cognito user-pool management action names and resource granularity cross-checked against AWS Cognito security/IAM guidance.

The provider version is the exact version resolved in CI run [43613054015](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43613054015). T33 tracks pinning the provider and committing lockfiles.

## Resource-to-API mapping

| Terraform resource | Provider/API operations | IAM actions |
|---|---|---|
| `aws_cognito_user_pool.main` | CreateUserPool; DescribeUserPool; UpdateUserPool; DeleteUserPool; SetUserPoolMfaConfig; GetUserPoolMfaConfig; AddCustomAttributes | `cognito-idp:CreateUserPool`, `DescribeUserPool`, `UpdateUserPool`, `DeleteUserPool`, `SetUserPoolMfaConfig`, `GetUserPoolMfaConfig`, `AddCustomAttributes` |
| `aws_cognito_user_pool_client.web` | CreateUserPoolClient; DescribeUserPoolClient; UpdateUserPoolClient; DeleteUserPoolClient | `cognito-idp:CreateUserPoolClient`, `DescribeUserPoolClient`, `UpdateUserPoolClient`, `DeleteUserPoolClient` |
| `aws_cognito_user_pool_domain.hosted` | CreateUserPoolDomain; DescribeUserPoolDomain; UpdateUserPoolDomain; DeleteUserPoolDomain | `cognito-idp:CreateUserPoolDomain`, `DescribeUserPoolDomain`, `UpdateUserPoolDomain`, `DeleteUserPoolDomain` |
| `aws_cognito_user_group.{admin,kiosk}` | CreateGroup; GetGroup; UpdateGroup; DeleteGroup | `cognito-idp:CreateGroup`, `GetGroup`, `UpdateGroup`, `DeleteGroup` |
| Cognito pool tags | TagResource; UntagResource; ListTagsForResource | `cognito-idp:TagResource`, `UntagResource`, `ListTagsForResource` |
| `aws_apigatewayv2_api.http` | CreateApi; GetApi; UpdateApi; DeleteApi; DeleteCorsConfiguration; tag operations | `apigateway:POST`, `GET`, `PATCH`, `PUT`, `DELETE` |
| `aws_apigatewayv2_authorizer.jwt` | CreateAuthorizer; GetAuthorizer; UpdateAuthorizer; DeleteAuthorizer | `apigateway:POST`, `GET`, `PATCH`, `DELETE` |
| `aws_apigatewayv2_integration.lambda` | CreateIntegration; GetIntegration; UpdateIntegration; DeleteIntegration | `apigateway:POST`, `GET`, `PATCH`, `DELETE` |
| `aws_apigatewayv2_route.api` | CreateRoute; GetRoute; UpdateRoute; DeleteRoute | `apigateway:POST`, `GET`, `PATCH`, `DELETE` |
| `aws_apigatewayv2_stage.default` | CreateStage; GetStage; UpdateStage; DeleteStage; DeleteRouteSettings | `apigateway:POST`, `GET`, `PATCH`, `DELETE` |
| `aws_cloudfront_distribution.site` | CreateDistributionWithTags; GetDistribution; GetDistributionConfig; UpdateDistribution; DeleteDistribution; tag reads/writes | `cloudfront:CreateDistribution`, `GetDistribution`, `GetDistributionConfig`, `UpdateDistribution`, `DeleteDistribution`, `TagResource`, `UntagResource`, `ListTagsForResource` |
| `aws_cloudfront_origin_access_control.web` | CreateOriginAccessControl; GetOriginAccessControl; GetOriginAccessControlConfig; UpdateOriginAccessControl; DeleteOriginAccessControl | `cloudfront:CreateOriginAccessControl`, `GetOriginAccessControl`, `GetOriginAccessControlConfig`, `UpdateOriginAccessControl`, `DeleteOriginAccessControl` |
| `aws_cloudfront_cache_policy.{static,api}` | CreateCachePolicy; GetCachePolicy; GetCachePolicyConfig; UpdateCachePolicy; DeleteCachePolicy | `cloudfront:CreateCachePolicy`, `GetCachePolicy`, `GetCachePolicyConfig`, `UpdateCachePolicy`, `DeleteCachePolicy` |
| `aws_cloudfront_origin_request_policy.api` | CreateOriginRequestPolicy; GetOriginRequestPolicy; GetOriginRequestPolicyConfig; UpdateOriginRequestPolicy; DeleteOriginRequestPolicy | `cloudfront:CreateOriginRequestPolicy`, `GetOriginRequestPolicy`, `GetOriginRequestPolicyConfig`, `UpdateOriginRequestPolicy`, `DeleteOriginRequestPolicy` |
| `aws_cloudfront_response_headers_policy.security` | CreateResponseHeadersPolicy; GetResponseHeadersPolicy; GetResponseHeadersPolicyConfig; UpdateResponseHeadersPolicy; DeleteResponseHeadersPolicy | `cloudfront:CreateResponseHeadersPolicy`, `GetResponseHeadersPolicy`, `GetResponseHeadersPolicyConfig`, `UpdateResponseHeadersPolicy`, `DeleteResponseHeadersPolicy` |
| `aws_cloudfront_function.directory_index` | CreateFunction; DescribeFunction; GetFunction; PublishFunction; UpdateFunction; DeleteFunction | `cloudfront:CreateFunction`, `DescribeFunction`, `GetFunction`, `PublishFunction`, `UpdateFunction`, `DeleteFunction` |
| `aws_s3_bucket_policy.web` | GetBucketPolicy; PutBucketPolicy; DeleteBucketPolicy | `s3:GetBucketPolicy`, `s3:PutBucketPolicy`, `s3:DeleteBucketPolicy` |
| `aws_s3_object.frontend` and `frontend_config` | PutObject; HeadObject; DeleteObject | `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` |
| `aws_cloudwatch_log_group.api` | Managed by access module but same provider resource as T07 | See T07: `logs:CreateLogGroup`, `DescribeLogGroups`, `PutRetentionPolicy`, `DeleteLogGroup`, `ListTagsForResource`, `TagResource`, `UntagResource` |

No API Gateway IAM service role is configured for the Lambda proxy integrations. The deployment policy does not need `iam:PassRole` for API Gateway. The Lambda resource-based permission resources are covered by T07's `lambda:AddPermission`, `GetPolicy` and `RemovePermission` mapping.

## Resource scope and policy constraints

### Cognito user pools

The pool ARN is `arn:aws:cognito-idp:us-east-1:<account>:userpool/<pool-id>`. Cognito's IAM resource granularity is at user-pool level; IAM cannot isolate individual app clients, domains or groups from other operations on the same pool. Scope all supported Cognito actions to the one environment pool ARN. The initial `CreateUserPool` operation may require `Resource: "*"` because the pool ARN does not exist yet; constrain creation with request tags where the API supports them and the Project/Environment tag set by Terraform. Do not grant Cognito user administration, identity-pool, or end-user authentication actions: they are not Terraform resource operations in this module.

### API Gateway v2

The service prefix is `apigateway`; it uses HTTP-verb IAM actions rather than one action per API operation. The API ARN family is `arn:aws:apigateway:us-east-1::/apis/<api-id>`, with child paths for `authorizers`, `integrations`, `routes`, and `stages`. The API create collection ARN is `arn:aws:apigateway:us-east-1::/apis`. Use only these resource paths; do not grant `apigateway:*` or use the legacy `/restapis/*` path. Restrict `apigateway:POST` create requests using `apigateway:Request/ApiName=attendance-<env>-http-api` where the action supports the condition; restrict later operations with the corresponding resource path and `apigateway:Resource/ApiName` where supported. Tag operations are HTTP verb actions and must be scoped to the same API ARN.

The configured stage has access logs and detailed metrics. Its log destination is the exact API Gateway log group already scoped under the CloudWatch Logs permissions in T07.

### CloudFront

CloudFront is a global service; its ARNs omit the region. Scope resource-level actions to the environment's resources:
- Distribution: `arn:aws:cloudfront::<account>:distribution/<distribution-id>`.
- Function: `arn:aws:cloudfront::<account>:function/attendance-<env>-directory-index`.
- OAC: `arn:aws:cloudfront::<account>:origin-access-control/<id>`.
- Cache policy: `arn:aws:cloudfront::<account>:cache-policy/<id>`.
- Origin request policy: `arn:aws:cloudfront::<account>:origin-request-policy/<id>`.
- Response headers policy: `arn:aws:cloudfront::<account>:response-headers-policy/<id>`.

Creation actions for these resources generally do not support resource-level ARNs because the resource identifiers are not known before creation. Use `Resource: "*"` for the specific create action only, and apply request-tag conditions where supported. For distribution creation, the provider uses `CreateDistributionWithTags`, which requires `cloudfront:CreateDistribution` and `cloudfront:TagResource`. Read/update/delete actions use the returned exact resource ARN. Distribution tag operations use that distribution ARN. Do not grant CloudFront account-wide List* actions unless provider-source evidence demonstrates a required list operation.

CloudFront policy creation/update/delete and distribution/function creation APIs are global but not interchangeable; each resource family gets its own action list. No invalidation, monitoring subscription, WAF, certificate, custom domain or origin identity operation is configured.

### S3 web bucket objects and policy

- `aws_s3_object` uses `PutObject` to create/update, `HeadObject` to refresh state, and `DeleteObject` to remove the object. S3 authorizes HeadObject using `s3:GetObject`.
- Object actions are scoped to `arn:aws:s3:::attendance-<env>-<account>-web/*`. They do not need `s3:ListBucket`, bucket-wide object listing, ACL, tagging, multipart-abort or object-version permissions for this configuration.
- Bucket policy actions use the exact web bucket ARN and are limited to `s3:GetBucketPolicy`, `s3:PutBucketPolicy`, and `s3:DeleteBucketPolicy`.

### Plan and apply role split

- Plan role needs read-only API verbs and read operations on exact known resource ARNs. It must not receive `POST`, `PUT`, `PATCH`, or `DELETE` for API Gateway, Cognito write actions, CloudFront write actions, S3 Put/Delete, or bucket policy mutation.
- Apply role adds the resource create/update/delete/tag actions above. The only unavoidable create-time wildcards are action-specific and must not be broadened to service-wide wildcard actions.
- No runtime permissions (Cognito user CRUD, API invoke, CloudFront invalidation, S3 bucket listing) belong in the deployment roles.

## AWS authorization references

- [API Gateway v2 Service Authorization Reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_apigatewayv2.html)
- [CloudFront Service Authorization Reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_cloudfront.html)
- [Cognito user-pool IAM guidance](https://docs.aws.amazon.com/cognito/latest/developerguide/security_iam_service-with-iam.html)
- [Cognito user-pool management API authorization model](https://docs.aws.amazon.com/cognito/latest/developerguide/authentication-flows-public-server-side.html)
- [API Gateway ARN reference](https://docs.aws.amazon.com/apigateway/latest/developerguide/arn-format-reference.html)
- [S3 Service Authorization Reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_s3.html)


### KMS key policy dependency

The access module owns the final `aws_kms_key_policy.attendance` resource because only this module has the created CloudFront distribution ARN. The policy grants `kms:Decrypt` to `cloudfront.amazonaws.com` only when `aws:SourceAccount` matches the account and `aws:SourceArn` equals `aws_cloudfront_distribution.site.arn`. The key itself is created in the foundation module with the default account-root policy, then the access module installs the complete service policy. This avoids a Terraform dependency cycle and removes the previous distribution wildcard. Deployment IAM must scope `kms:PutKeyPolicy` and `kms:GetKeyPolicy` to the exact environment KMS key ARN.
