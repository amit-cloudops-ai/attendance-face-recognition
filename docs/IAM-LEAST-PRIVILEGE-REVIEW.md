# IAM least-privilege review

**Status: code scope improved; live policy validation not yet complete.** This review is based on the policy templates in the release candidate. It is not evidence that any policy has been rendered for the real account, attached, or exercised.

## Findings and controls

| Area | Current scope | Assessment / required control |
|---|---|---|
| API Gateway v2 | Plan and apply access is scoped to the exact environment API ID. Parent API mutations also require `Project=attendance` and the matching `Environment` resource tags. Child route/integration/authorizer/stage operations are scoped to `/apis/<api-id>/*`. | The API must be created first with the matching tags, then imported into Terraform. The bootstrap script fails closed if an API with the expected name already exists. No deployment role may create or modify child resources under another API. |
| Cognito user pool | Create requires `aws:RequestTag/Project=attendance` and the exact environment tag. Pool/client/domain/group operations require matching resource tags. | Verify that the AWS provider sends the required tags during CreateUserPool and that all subsequent calls carry the pool resource ARN. Validate with Access Analyzer and a dev plan. |
| CloudFront distribution | Create requires attendance/project and environment request tags. Get/update/delete/tag operations require matching resource tags. | This prevents the apply role from modifying unrelated distributions, provided the provider creates the distribution with those tags. Verify this with a dev plan and live IAM simulation. |
| CloudFront function | Management is restricted to the exact environment function name and matching resource tags. Creation requires matching request tags. | Verify tag behavior in the dev plan. |
| CloudFront OAC/cache/origin-request/response-header policies | Permanent apply policies are read-only for these resource families. A separate temporary bootstrap policy grants only the four Create actions with `Resource: "*"`. | Attach the temporary policy only for the first approved deployment. It cannot update or delete existing policies. Detach it immediately after creation. Future changes require a separately reviewed, time-bounded policy scoped to the exact generated IDs; that break-glass policy is not yet implemented. |
| DynamoDB and S3 | Exact environment table/bucket/object ARNs and prefixes; KMS operations are in the KMS key policy and use the environment alias and DynamoDB `kms:ViaService` conditions. | Keep data and raw biometric object access restricted to handler-specific execution roles and boundaries. |
| Lambda and IAM | Exact function and role name families; `iam:PassRole` is separated by Lambda/Scheduler service and constrained by the environment execution boundary. | Validate every rendered ARN and PassRole service principal. Do not attach deployment roles to runtime workloads. |
| CloudWatch, Rekognition and collection creation | Some read/list or create actions require collection-level or `Resource: "*"` scope because the target resource does not yet exist or the service action does not support resource-level authorization. | Retain only the minimum documented action set, with function/region/tag conditions where supported. Treat Access Analyzer findings as required review evidence, not automatic approval. |
| Billing | Separate billing plan/apply roles and state key; account billing actions are not attached to dev/prod roles. | Verify exact GitHub OIDC subject and ensure billing permissions remain isolated. |

## API Gateway bootstrap sequence

The API ID is service-generated, so a permanent role cannot safely scope child operations before the API exists.

1. Run `bash scripts/bootstrap_api_gateway.sh --env dev --account-id <verified-account-id> --profile <approved-profile>` without `--apply`. This is a dry run.
2. Review the exact API name, account and region. Obtain explicit approval for creating that one tagged API.
3. Only after approval, rerun with `--apply`. The script checks STS account identity, checks that the API name is not already present, and creates only the tagged HTTP API.
4. Record the returned API ID as `API_ID` in the matching GitHub environment. The Terraform root imports that exact API into state.
5. Render the IAM inventory with `--api-id <returned-id>`. The plan/apply policies then authorize only the imported API and its child paths.

The script does not create routes, stages, integrations, authorizers, Lambda functions or any other AWS resource.

## Temporary CloudFront bootstrap policy

The permanent dev/prod access policies cannot update or delete OAC/cache/origin-request/response-header policies. The temporary `github-apply-<env>-cloudfront-bootstrap` policy contains only:

- `cloudfront:CreateOriginAccessControl`
- `cloudfront:CreateCachePolicy`
- `cloudfront:CreateOriginRequestPolicy`
- `cloudfront:CreateResponseHeadersPolicy`

It uses `Resource: "*"` because these create operations do not expose an existing resource ARN. It must be attached only for the first approved deployment, then detached. The permanent policy remains read-only for these resource families. A later modification/replacement must use a separately reviewed temporary policy restricted to the exact IDs obtained from Terraform state; do not restore wildcard Update/Delete permissions.

## Offline and AWS-side validation

CI currently performs local JSON/template shape checks, IAM managed-policy size checks, region/account/state isolation checks, role/boundary/PassRole checks, and verifies the exact API ID and create-only CloudFront bootstrap policy shape.

After the API ID and account-specific inventory are rendered, run AWS IAM Access Analyzer policy validation using the approved read-only profile:

```bash
aws accessanalyzer validate-policy \
  --policy-document file://<rendered-policy.json> \
  --policy-type IDENTITY_POLICY \
  --region us-east-1
```

Repeat for every rendered identity policy and boundary. Review all ERROR, SECURITY_WARNING and WARNING findings. Record the complete output and disposition of each finding. This API call validates policy syntax and findings; it does not create an analyzer or AWS resource.

After the roles exist, use `aws iam simulate-principal-policy` with exact action/resource contexts to test allowed and denied cases. Include negative tests for another API ID, another environment's distribution, another user pool, another state key, and untagged CloudFront resources.

## Release-gate decision

IAM readiness is **not passed** until:

1. The owner-approved API ID is recorded for each environment and the rendered policies contain no API Gateway wildcard IDs.
2. The temporary CloudFront create-only policy lifecycle is documented in the bootstrap approval and detachment checklist.
3. Every rendered policy has an Access Analyzer result and reviewed findings.
4. Positive and negative IAM simulations pass after bootstrap.
5. A dev plan confirms the provider's actual resource calls are authorized without broadening the policies.

No AWS policy has been created, attached or simulated in this repository-readiness pass.
