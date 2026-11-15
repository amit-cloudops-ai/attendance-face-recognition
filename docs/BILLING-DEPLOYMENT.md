# Isolated AWS Budgets deployment

**Status:** policy and workflow templates only. No budget, IAM role or AWS resource has been created or modified.

## Terraform root and budget resources

The billing root is infra/billing and uses the independent S3 state key attendance/billing/terraform.tfstate with native lockfile attendance/billing/terraform.tfstate.tflock.

The Terraform root manages two monthly cost budgets:

| Budget | ARN |
|---|---|
| Dev | arn:aws:budgets::<account-id>:budget/attendance-dev-monthly-cost |
| Prod | arn:aws:budgets::<account-id>:budget/attendance-prod-monthly-cost |

Each budget is USD 15/month and emits actual-cost notifications at 80% and 100% to the configured ALERT_EMAIL. These budget resources are managed only from the billing root.

## Separate deployment roles

- attendance-github-billing-plan — read-only plan.
- attendance-github-billing-apply — budget changes and billing account permissions.

OIDC subjects are exact:
- repo:amit-cloudops-ai/attendance-face-recognition:environment:billing-plan
- repo:amit-cloudops-ai/attendance-face-recognition:environment:billing-apply

Both environments are restricted to main. The apply environment requires an independent reviewer and prevents self-review. The workflow maps billing to infra/billing and does not require runtime permissions-boundary or Cognito variables.

## Billing IAM action sets

Plan role:
- budgets:ViewBudget on the two exact budget ARNs.
- aws-portal:ViewBilling on Resource=*.
- Billing state GetObject; billing lockfile Get/Put/Delete; ListBucket restricted to the billing state/lock prefixes.

Apply role:
- budgets:ModifyBudget and budgets:ViewBudget on the two exact budget ARNs.
- aws-portal:ModifyBilling and aws-portal:ViewBilling on Resource=* because these account-level billing actions do not support a budget resource ARN.
- Billing state Get/Put; billing lockfile Get/Put/Delete; ListBucket restricted to the billing state/lock prefixes.

The apply role does not receive broad IAM administration, PassRole, or permissions to manage dev/prod runtime resources. The dev/prod plan/apply roles do not receive budgets:* or aws-portal:*. The aws-portal:ModifyBilling permission is account-level and cannot be restricted to a single budget ARN in the provider action model; it is isolated to billing-apply, gated by the main branch and an independent GitHub environment reviewer, and must be explicitly approved in the bootstrap review.

## GitHub environment configuration

Create billing-plan and billing-apply. Each receives AWS_ROLE_ARN, AWS_ACCOUNT_ID, TF_STATE_BUCKET and ALERT_EMAIL. billing-plan additionally receives TF_PLAN_AGE_RECIPIENT; billing-apply receives the TF_PLAN_AGE_IDENTITY secret. Use a separate billing age identity/recipient pair from dev and prod.

## Approval boundary

The policies and trust documents are templates only. The billing roles and environments remain uncreated until the account ID is verified, the state bucket exists, T16 settings are configured, and the owner approves the exact rendered role permissions. Do not attach account billing actions to any normal environment role.


## Project budget attribution and apply order

The billing root manages one $15/month budget filtered by the `Project=attendance` cost-allocation tag. Dev and prod resources share this Project tag, so one budget measures the combined project rather than creating two unfiltered account-wide budgets.

Apply order matters:
1. Deploy the dev foundation and data/recognition/access resources so AWS has resources carrying `Project=attendance`.
2. In Cost Explorer / Billing, confirm the `Project` user-defined tag appears in cost-allocation tags. AWS may take up to 24 hours after the tag is first applied for it to appear.
3. Apply the billing root. Terraform activates the `Project` tag and then creates the tag-filtered budget.
4. Verify the tag status is Active and the budget filter is `Project=attendance`. Cost data can lag tag activation; do not treat the alert as effective until cost allocation data is visible.

The budget sends actual-spend alerts at 80% and 100%. It does not stop or throttle AWS resources. The $15 threshold is for tagged attendance-project usage; unrelated account resources are intentionally excluded.
