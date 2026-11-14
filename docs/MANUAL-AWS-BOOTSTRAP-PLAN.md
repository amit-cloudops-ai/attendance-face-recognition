# Manual AWS deployment bootstrap plan — approval required

**Status:** prepared for owner review only. Nothing in this document has been executed. No AWS API calls, resource creation, IAM role/policy attachment, remote backend initialization, Terraform plan or apply has been performed.

## Target account and region

- AWS account: existing owner account; exact 12-digit account ID must be confirmed from the authenticated AWS identity before any mutation.
- Region: `us-east-1`, sourced from `config/deployment.json`. Do not configure a second region value in local backend files or GitHub variables.
- Repository: amit-cloudops-ai/attendance-face-recognition.
- GitHub OIDC issuer: https://token.actions.githubusercontent.com.
- OIDC audience: sts.amazonaws.com.

Do not assume an account ID, bucket suffix, existing OIDC provider state, or resource absence. The first step after approval is a read-only identity and inventory check. If an OIDC provider, bucket, role, policy or boundary already exists, inspect and reconcile it; do not create duplicates.

## Bootstrap inventory

| Resource | Proposed name | Purpose | Initial state |
|---|---|---|---|
| S3 state bucket | attendance-tf-state-<account-id>-<approved-suffix> | Remote state, versioned and SSE-S3 | Manual bootstrap |
| IAM OIDC provider | token.actions.githubusercontent.com | GitHub Actions federation | Create only if absent |
| IAM boundary | attendance-dev-execution-boundary | Restrict dev Lambda/Scheduler runtime roles | Attach to runtime roles |
| IAM boundary | attendance-prod-execution-boundary | Restrict prod Lambda/Scheduler runtime roles | Attach to runtime roles |
| IAM role | attendance-github-dev-plan | Read-only dev Terraform plan | Create after approval |
| IAM role | attendance-github-dev-apply | Dev Terraform apply | Create after approval |
| IAM role | attendance-github-prod-plan | Read-only prod Terraform plan | Create after approval |
| IAM role | attendance-github-prod-apply | Prod Terraform apply | Create after approval |
| IAM role | attendance-github-billing-plan | Billing plan only | Create after approval |
| IAM role | attendance-github-billing-apply | Billing apply only | Create after approval |
| Customer-managed IAM policies | Dev/prod plan and apply policy sets | Attach split least-privilege permissions | 22 environment policy templates validated |
| GitHub environments | dev-plan, dev-apply, prod-plan, prod-apply, billing-plan, billing-apply | Bind OIDC subjects and approvals | Owner configuration required |

The policy set counts are:
- Dev plan: core, edge, state (3 managed policies).
- Dev apply: core, data, Lambda, IAM, foundation, access, state, DynamoDB KMS (8 managed policies).
- Prod plan: core, edge, state (3 managed policies).
- Prod apply: core, data, Lambda, IAM, foundation, access, state, DynamoDB KMS (8 managed policies).
- Billing plan/apply: one budget policy and one state policy each (4 managed policies total).
- Runtime boundaries: one dev and one prod managed policy.

Total: 26 managed policies across dev, prod and billing, plus the two runtime permissions-boundary policies.

Each policy template has CI checks for JSON validity, 6,144-character size, environment isolation and the service-specific constraints documented in infra/policies/README.md.

## Explicitly separate billing permissions

T34 moved AWS Budgets to infra/billing with its own Terraform state key. Normal dev/prod plan/apply roles do not receive budgets:* or aws-portal:* permissions.

Billing has dedicated plan/apply policy templates and OIDC trust templates in T37. Do not attach account-level billing permissions to any dev/prod environment role. Billing role creation and the billing GitHub environments remain approval-gated.

## Bootstrap order

### 1. Read-only identity and existence checks

Before any write operation, use an authenticated read-only AWS session to verify the active STS identity and region. Inspect whether the OIDC provider, state bucket, boundary policies, deployment roles and policy names already exist. Record exact ARNs and current trust/permission documents. No writes in this step. No live inventory has been performed by this repository session.

### 2. State bucket

Use docs/STATE-BUCKET-BOOTSTRAP.md. Confirm the globally unique bucket name, create it in us-east-1, enable BucketOwnerEnforced ownership, all four public-access-block settings, versioning, SSE-S3 default encryption and the TLS-only deny bucket policy. Verify every setting with read-only S3 API calls. Do not enable Object Lock or automatic state expiration.

### 3. OIDC provider

If absent, create the IAM OIDC provider for issuer token.actions.githubusercontent.com with client ID sts.amazonaws.com. Verify issuer and audience after creation.

### 4. Runtime permissions boundaries

Render the dev/prod boundary templates with the verified account ID. Validate JSON, policy size, allowed runtime services, resource scopes, KMS alias/ViaService conditions and absence of IAM/STS administration or PassRole. Create the two customer-managed boundary policies only after review.

### 5. GitHub deployment roles

Create the six roles with trust policies:
- attendance-github-dev-plan trusts only repo:amit-cloudops-ai/attendance-face-recognition:environment:dev-plan.
- attendance-github-dev-apply trusts only ...:environment:dev-apply.
- attendance-github-prod-plan trusts only ...:environment:prod-plan.
- attendance-github-prod-apply trusts only ...:environment:prod-apply.
- attendance-github-billing-plan trusts only ...:environment:billing-plan.
- attendance-github-billing-apply trusts only ...:environment:billing-apply.

Every trust policy requires aud=sts.amazonaws.com and exact sub equality. Attach only the matching plan/apply managed policies. Do not allow these deployment roles to manage themselves, the OIDC provider, their own trust policies or the deployment policy attachments.

### 6. GitHub environment configuration

Complete docs/GITHUB-ENVIRONMENT-SETUP.md. Configure environment-scoped AWS_ROLE_ARN variables, account/bucket/boundary/configuration variables, plan age recipients and apply-only private age identity secrets. Enforce branch restrictions and independent apply reviewers. Verify actual settings before continuing.

### 7. First dev deployment

Only after the bootstrap and GitHub environment configuration are confirmed:
1. Run the dev-plan workflow on develop.
2. Review the encrypted plan artifact and its resource/action inventory.
3. Present the exact Terraform plan and cost/resource changes to the owner.
4. Obtain explicit approval before the dev-apply workflow.
5. Apply the saved plan only; do not regenerate a plan during apply.
6. Verify health checks, authentication, upload/recognition flow, data persistence, alarms and rollback readiness.

### 8. Production deployment

Do not deploy prod until dev acceptance criteria pass and the owner explicitly approves the production plan. Run prod-plan on main, review the exact plan, obtain separate production approval, then apply only the saved plan.

### 9. Billing root

Billing has a dedicated plan/apply policy and OIDC role pair. It must not share the dev/prod deployment role permissions.

## IAM security checks before approval

- All PassRole permissions are limited to the exact 14 environment Lambda roles and two Scheduler roles and require iam:PassedToService for the correct AWS service.
- Runtime role creation requires the exact environment permissions boundary and required Project/Environment tags.
- Plan roles have no infrastructure mutation actions; state lockfile writes are the only S3 write/delete actions.
- Apply roles cannot access the other environment's resources or state path.
- DynamoDB CMK operations are constrained by the environment KMS alias and kms:ViaService=dynamodb.us-east-1.amazonaws.com; CreateGrant additionally requires kms:GrantIsForAWSResource=true.
- CloudFront KMS decrypt is scoped to the exact distribution ARN.
- Billing permissions are excluded from environment roles.
- GitHub OIDC trust uses exact repository/environment subjects; no wildcard sub.
- No long-lived AWS access keys are used.

## Approval request required before any mutation

Before performing any bootstrap write, present to the owner:
1. Verified 12-digit account ID and region confirmation against `config/deployment.json` and the authenticated STS identity.
2. Final state bucket name and exact bucket configuration/policy.
3. Whether the OIDC provider already exists.
4. Exact IAM resource inventory (one OIDC provider if absent, two boundaries, six roles and 26 managed policy attachments/templates).
5. Fully rendered trust policies, boundaries and all role policy documents.
6. Exact GitHub environment names, variables, secrets and branch/reviewer controls.
7. Planned first Terraform backend init and dev plan scope.

No action may proceed from this plan until the owner explicitly approves the presented resource inventory and permissions. AWS resource creation and Terraform plan/apply remain separate approvals.
