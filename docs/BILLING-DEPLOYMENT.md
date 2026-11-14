# Isolated AWS Budgets deployment

**Status:** policy and workflow templates only. No budget, IAM role or AWS resource has been created or modified.

## Terraform root and budget resources

The billing root is infra/billing and uses the independent S3 state key attendance/billing/terraform.tfstate with native lockfile attendance/billing/terraform.tfstate.tflock.

The Terraform root manages two monthly cost budgets:

| Budget | ARN |
|---|---|
| Dev | arn:aws:budgets::<account-id>:budget/attendance-dev-monthly-cost |
| Prod | arn:aws:budgets::<account-id>:budget/attendance-prod-monthly-cost |

Each budget is USD 15/month and emits actual-cost notifications at 80% and 100% to the configured ALERT_EMAIL. **Current defect:** neither budget has a `cost_filter`, so both track total account spend; the dev and prod budgets are duplicate account-wide monitors, not environment-specific budgets. Do not apply the billing root until the owner chooses either one account-wide budget or two environment-filtered budgets. Environment filtering can use the `Environment` cost-allocation tag only after that user-defined tag is activated in Billing. Budget alerts are notifications, not a hard spending cap, and AWS billing/budget data can be delayed. These budget resources are managed only from the billing root.

## Separate deployment roles

- attendance-github-billing-plan — read-only plan.
- attendance-github-billing-apply — budget changes and billing account permissions.

OIDC subjects are exact:
- repo:amit-cloudops-ai/attendance-face-recognition:environment:billing-plan
- repo:amit-cloudops-ai/attendance-face-recognition:environment:billing-apply

Both environments are restricted to main. The apply environment requires an repository owner's manual approval checkpoint, with self-review allowed. The workflow maps billing to infra/billing and does not require runtime permissions-boundary or Cognito variables.

## Billing IAM action sets

Plan role:
- budgets:ViewBudget on the two exact budget ARNs.
- aws-portal:ViewBilling on Resource=*.
- Billing state GetObject; billing lockfile Get/Put/Delete; ListBucket restricted to the billing state/lock prefixes.

Apply role:
- budgets:ModifyBudget and budgets:ViewBudget on the two exact budget ARNs.
- aws-portal:ModifyBilling and aws-portal:ViewBilling on Resource=* because these account-level billing actions do not support a budget resource ARN.
- Billing state Get/Put; billing lockfile Get/Put/Delete; ListBucket restricted to the billing state/lock prefixes.

The apply role does not receive broad IAM administration, PassRole, or permissions to manage dev/prod runtime resources. The dev/prod plan/apply roles do not receive budgets:* or aws-portal:*. The aws-portal:ModifyBilling permission is account-level and cannot be restricted to a single budget ARN in the provider action model; it is isolated to billing-apply, gated by the main branch and an repository-owner approval checkpoint, and must be explicitly approved in the bootstrap review.

## GitHub environment configuration

Create billing-plan and billing-apply. Each receives AWS_ROLE_ARN, AWS_ACCOUNT_ID, TF_STATE_BUCKET and ALERT_EMAIL. billing-plan additionally receives TF_PLAN_AGE_RECIPIENT; billing-apply receives the TF_PLAN_AGE_IDENTITY secret. Use a separate billing age identity/recipient pair from dev and prod.

## Approval boundary

The policies and trust documents are templates only. The billing roles and environments remain uncreated until the account ID is verified, the state bucket exists, T16 settings are configured, and the owner approves the exact rendered role permissions. Do not attach account billing actions to any normal environment role.
