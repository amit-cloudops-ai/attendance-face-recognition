# GitHub environment and deployment variable setup

**Status:** solo-owner configuration checklist. The repository connector cannot read or configure GitHub Actions environment protection rules or branch protection settings. These settings have not been verified or changed.

## Six deployment environments

Create these exact repository environments:

| Environment | Allowed branch | Owner approval checkpoint |
|---|---|---|
| dev-plan | develop only | No |
| dev-apply | develop only | Yes — repository owner |
| prod-plan | main only | No |
| prod-apply | main only | Yes — repository owner |
| billing-plan | main only | No |
| billing-apply | main only | Yes — repository owner |

This is a **solo-owner workflow**. The repository owner is the sole reviewer on apply environments and self-review is allowed. This provides a deliberate manual deployment checkpoint, not independent approval or separation of duties. Do not request or configure a teammate as a reviewer. If independent separation of duties becomes a requirement later, the governance model must be deliberately changed.

Use deployment branch restrictions, not only the workflow's if-condition. The workflow's OIDC subject is bound to the exact environment name, so the environment names must match exactly. Do not create generic dev/prod environments for this workflow.

Run the helper in dry-run mode first:

```bash
bash scripts/configure_github_environments.sh
```

Only after inspecting the output and deciding to change GitHub settings, run:

```bash
bash scripts/configure_github_environments.sh --apply
```

## Variables to define in each environment

| Variable | dev-plan | dev-apply | prod-plan | prod-apply |
|---|---|---|---|---|
| AWS_ROLE_ARN | dev plan role ARN | dev apply role ARN | prod plan role ARN | prod apply role ARN |
| AWS_ACCOUNT_ID | verified account ID | same | same | same |
| EXECUTION_ROLE_BOUNDARY_ARN | dev boundary ARN | dev boundary ARN | prod boundary ARN | prod boundary ARN |
| TF_STATE_BUCKET | final state bucket | same | same | same |
| ALERT_EMAIL | approved alert mailbox | same | same | same |
| COGNITO_CALLBACK_URLS | non-empty JSON array | same | production HTTPS callback array | same |
| COGNITO_LOGOUT_URLS | non-empty JSON array | same | production HTTPS logout array | same |
| ALLOWED_ORIGINS | non-empty JSON array | same | production HTTPS origin array | same |
| TF_PLAN_AGE_RECIPIENT | dev public age recipient | not required | prod public age recipient | not required |

For billing-plan and billing-apply, define only AWS_ROLE_ARN, AWS_ACCOUNT_ID, TF_STATE_BUCKET and ALERT_EMAIL; the billing root does not consume runtime boundary or Cognito callback/origin variables. Billing plan additionally defines TF_PLAN_AGE_RECIPIENT; billing apply defines the TF_PLAN_AGE_IDENTITY secret.

The role ARNs are non-secret configuration values. The account ID, bucket name and boundary ARN are also configuration values, not credentials. Do not place access keys or private key material in variables.

## Secrets

- dev-apply: TF_PLAN_AGE_IDENTITY containing only the dev private age identity.
- prod-apply: TF_PLAN_AGE_IDENTITY containing only the prod private age identity.
- billing-apply: TF_PLAN_AGE_IDENTITY containing only the billing private age identity, if required by the billing workflow.
- Do not set TF_PLAN_AGE_IDENTITY in plan environments.
- Do not reuse the same private identity between dev, prod and billing.
- Never store the private identity in repository variables, source control, artifacts or logs.

## Branch protection

For `main`, `develop` and `solo/amit-monday`, configure:

- Require pull requests before merging.
- Require the Python and terraform-fmt status checks.
- Require conversation resolution.
- Block force pushes and branch deletion.
- Enforce the rules for administrators.
- Do not require independent approving reviews or latest-push approval; those settings are incompatible with the agreed solo-owner model.

The owner must personally inspect every PR diff, verify CI and security evidence, and consciously merge. This is an owner-controlled review checkpoint, not an independent review. The branch-protection helper defaults to dry-run:

```bash
bash scripts/configure_branch_protection.sh
```

Apply only after reviewing its output:

```bash
bash scripts/configure_branch_protection.sh --apply
```

## Preflight checklist before any AWS bootstrap

- All six environments exist with exact names.
- Allowed deployment branches match the table above.
- Apply environments require the repository owner's manual approval, with self-review allowed.
- AWS_ROLE_ARN points to the matching role only.
- Account ID, state bucket and boundary ARN match the approved AWS account/environment.
- Age recipients and private identities are different per environment and the private identities exist only as apply-environment secrets.
- Production callback URLs, logout URLs and origins are HTTPS and point to the final production site.
- Branch protection and required CI checks are enabled.
- The owner confirms the configuration before OIDC roles are created or any remote backend is initialized.

## Verification limitation

The GitHub connector cannot inspect or configure Actions environment settings, and branch-protection reads returned 403 Resource not accessible by integration. Therefore the environment list, variable values, secret presence, owner-review configuration and branch restrictions remain unverified until checked through an authorized GitHub CLI session or GitHub UI.
