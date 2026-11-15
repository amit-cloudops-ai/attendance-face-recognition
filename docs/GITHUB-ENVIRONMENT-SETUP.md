# GitHub environment and deployment variable setup

**Status:** configuration checklist. The repository connector can update code and workflows but cannot read or configure GitHub Actions environment protection rules or branch protection settings. These settings have not been verified or changed.

## Create six environments

Create these exact repository environments:

| Environment | Allowed branch | Review requirement |
|---|---|---|
| dev-plan | develop only | No required reviewer |
| dev-apply | develop only | No required reviewer; owner self-review allowed |
| prod-plan | main only | No required reviewer |
| prod-apply | main only | No required reviewer; owner self-review allowed |
| billing-plan | main only | No required reviewer |
| billing-apply | main only | No required reviewer; owner self-review allowed |

Use deployment branch restrictions, not only the workflow's if-condition. The workflow's OIDC subject is bound to the exact environment name, so the environment names must match exactly. Do not create generic dev/prod environments for this workflow.

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
- Do not set TF_PLAN_AGE_IDENTITY in plan environments.
- Do not reuse the same private identity between dev and prod.
- Never store the private identity in repository variables, source control, artifacts or logs.

## Branch protection

For `main`, `develop` and `solo/amit-monday`, configure:
- Require pull requests before merging.
- Required approvals: 0 (solo-owner model); the repository owner may merge their own PR after all required CI checks pass, and self-review is allowed.
- Require the Python and terraform-fmt status checks.
- Require conversation resolution.
- Block force pushes and branch deletion.
- Optional independent CODEOWNERS review can be introduced when another trusted code owner is available; it is not a current release gate.

During the solo-owner phase, do not require an external reviewer or CODEOWNERS approval. The owner may merge after required CI checks pass. When a second trusted maintainer is added, introduce CODEOWNERS review for .github/workflows/**, infra/**, infra/policies/** and docs/security/** as an additional gate.

## Preflight checklist before any AWS bootstrap

- All six environments exist with exact names.
- Allowed deployment branches match the table above.
- Apply environments have no required external reviewers; owner self-review is allowed.
- AWS_ROLE_ARN points to the matching role only.
- Account ID, state bucket and boundary ARN match the approved AWS account/environment.
- Age recipients and private identities are different per environment and the private identities exist only as apply-environment secrets.
- Production callback URLs, logout URLs and origins are HTTPS and point to the final production site.
- Branch protection and required CI checks are enabled.
- The owner confirms the configuration before OIDC roles are created or any remote backend is initialized.

## Verification limitation

GitHub branch protection API reads returned 403 Resource not accessible by integration, and the repository connector does not expose GitHub Actions environment settings. Therefore the environment list, variable values, secret presence, reviewer configuration (intentionally not required in the solo-owner model) and branch restrictions cannot be verified from this session. This task remains blocked until a repository administrator configures the six environments and provides confirmation or an authorized read-only verification path.
