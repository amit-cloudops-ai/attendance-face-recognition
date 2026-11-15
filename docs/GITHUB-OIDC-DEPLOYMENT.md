# GitHub OIDC deployment trust and environment configuration

**Status:** policy templates and workflow changes only. No OIDC provider, IAM role, trust policy or GitHub environment was created or modified.

## OIDC role model

Use six separate IAM roles and six GitHub deployment environments:

| Environment | Branch | IAM role | OIDC subject |
|---|---|---|---|
| dev-plan | develop | attendance-github-dev-plan | repo:amit-cloudops-ai/attendance-face-recognition:environment:dev-plan |
| dev-apply | develop | attendance-github-dev-apply | repo:amit-cloudops-ai/attendance-face-recognition:environment:dev-apply |
| prod-plan | main | attendance-github-prod-plan | repo:amit-cloudops-ai/attendance-face-recognition:environment:prod-plan |
| prod-apply | main | attendance-github-prod-apply | repo:amit-cloudops-ai/attendance-face-recognition:environment:prod-apply |
| billing-plan | main | attendance-github-billing-plan | repo:amit-cloudops-ai/attendance-face-recognition:environment:billing-plan |
| billing-apply | main | attendance-github-billing-apply | repo:amit-cloudops-ai/attendance-face-recognition:environment:billing-apply |

The trust policy templates are in infra/policies/github-oidc-trust-{dev|prod|billing}-{plan|apply}.json.tftpl. Each policy uses the account's exact token.actions.githubusercontent.com OIDC provider ARN, sts:AssumeRoleWithWebIdentity, aud=sts.amazonaws.com, and one exact environment subject. No wildcard subject is permitted.

The OIDC provider must use issuer https://token.actions.githubusercontent.com and client ID/audience sts.amazonaws.com. The provider and six roles are bootstrap resources and are not created by this change.

## Workflow controls

The manual Terraform deployment workflow now sets the GitHub environment to environment-operation (for example dev-plan or prod-apply) and reads only vars.AWS_ROLE_ARN from that environment. This prevents the plan/apply role selector from being shared across both operations. Immediately after OIDC credential configuration, the workflow verifies that the role ARN belongs to TF_VAR_account_id, the state-bucket name carries that account ID, and sts:GetCallerIdentity returns the same account. A mismatch fails before remote Terraform initialization.

The workflow branch gate remains:
- dev: only refs/heads/develop
- prod and billing: only refs/heads/main

The workflow permissions remain least-privilege:
- actions: read — verify and download the successful encrypted plan artifact
- contents: read — checkout the selected release revision
- id-token: write — request the short-lived GitHub OIDC token for AWS
- No static AWS access keys, contents write, pull request write or broad repository write permissions.

The apply path requires a numeric plan run ID, confirms the plan run is successful, manual workflow_dispatch, exact same commit SHA and expected release branch, downloads the artifact from that exact run, decrypts it using the apply environment's age identity, and applies only that saved plan. The encrypted plan artifact retention is one day. The plan owner must retain the matching private age identity locally, download the encrypted artifact, decrypt and inspect the exact saved plan with the same Terraform/provider lockfile version, and record the plan run ID and commit SHA before approving apply. Do not expose the private identity in CI logs or repository variables.

## GitHub environment protection rules

Configure the following branch restrictions and reviewers before enabling deployments:

| Environment | Allowed deployment branch | Required reviewers |
|---|---|---|
| dev-plan | develop only | None required |
| dev-apply | develop only | At least one independent reviewer; prevent self-review |
| prod-plan | main only | At least one independent reviewer; prevent self-review |
| prod-apply | main only | At least one independent reviewer; prevent self-review |
| billing-plan | main only | At least one independent reviewer; prevent self-review |
| billing-apply | main only | At least one independent reviewer; prevent self-review |

Protect main and develop with pull-request review requirements. Require CODEOWNERS review for .github/workflows/**, infra/policies/** and infra/** so changes to deployment logic, role policies and Terraform are reviewed before reaching the release branches. Restrict environment administration to repository maintainers.

The AWS trust policy only distinguishes repository and environment. GitHub environment branch restrictions and reviewer rules are therefore part of the security boundary, not optional housekeeping. The workflow's branch if-condition is an additional guard, not a replacement for GitHub environment deployment branch restrictions.

## Required environment variables

Each of the six GitHub environments must define:

- AWS_ROLE_ARN — only that environment's plan or apply role ARN.
- AWS_ACCOUNT_ID — verified 12-digit account ID.
- EXECUTION_ROLE_BOUNDARY_ARN — the matching dev or prod runtime permissions boundary ARN (dev/prod only).
- API_ID — the exact pre-created API Gateway HTTP API ID imported into this environment's Terraform state (dev/prod only).
- TF_STATE_BUCKET — final globally unique state bucket name.
- ALERT_EMAIL — alert subscription email.
- COGNITO_CALLBACK_URLS — non-empty JSON array of allowed callback URLs.
- COGNITO_LOGOUT_URLS — non-empty JSON array of allowed logout URLs.
- ALLOWED_ORIGINS — non-empty JSON array of allowed browser origins.

All three plan environments (dev-plan, prod-plan and billing-plan) additionally define TF_PLAN_AGE_RECIPIENT, the public age recipient used to encrypt the saved plan.

All three apply environments (dev-apply, prod-apply and billing-apply) additionally define the TF_PLAN_AGE_IDENTITY secret, the matching private age identity used to decrypt the reviewed artifact. Use separate dev, prod and billing identities and never store private identities in repository variables.

The temporary dev/prod CloudFront bootstrap policies grant Create actions only for OAC/cache/origin-request/response-header policy resources. They are attached only for the first approved deployment and must be detached immediately after creation. The permanent apply policy cannot update/delete those resource families; later changes require a separately reviewed policy scoped to exact resource IDs.

The production callback/logout URLs and allowed origins must be the final HTTPS site origins. Localhost values in example tfvars are placeholders only and must not be used for production deployment.

## Approval boundary

The six trust policies are templates only. OIDC provider creation, role creation, role permission attachments, GitHub environment creation/configuration, reviewer selection and branch protection changes remain manual, explicit approval gates. No AWS or GitHub environment configuration was changed by this task.


See `docs/GITHUB-ENVIRONMENT-SETUP.md` for the exact six environment names, variables, secrets, deployment branch restrictions, reviewer requirements and the verification limitation for repository settings.
