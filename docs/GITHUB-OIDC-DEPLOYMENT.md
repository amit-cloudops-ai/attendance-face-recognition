# GitHub OIDC deployment trust and environment configuration

**Status:** policy templates and workflow changes only. No OIDC provider, IAM role, trust policy or GitHub environment was created or modified.

## OIDC role model

Use six separate IAM roles and six GitHub deployment environments:

| Environment | Allowed branch | IAM role | OIDC subject | Manual owner checkpoint |
|---|---|---|---|---|
| dev-plan | develop | attendance-github-dev-plan | repo:amit-cloudops-ai/attendance-face-recognition:environment:dev-plan | No |
| dev-apply | develop | attendance-github-dev-apply | repo:amit-cloudops-ai/attendance-face-recognition:environment:dev-apply | Yes |
| prod-plan | main | attendance-github-prod-plan | repo:amit-cloudops-ai/attendance-face-recognition:environment:prod-plan | No |
| prod-apply | main | attendance-github-prod-apply | repo:amit-cloudops-ai/attendance-face-recognition:environment:prod-apply | Yes |
| billing-plan | main | attendance-github-billing-plan | repo:amit-cloudops-ai/attendance-face-recognition:environment:billing-plan | No |
| billing-apply | main | attendance-github-billing-apply | repo:amit-cloudops-ai/attendance-face-recognition:environment:billing-apply | Yes |

The trust policy templates are in `infra/policies/github-oidc-trust-{dev|prod|billing}-{plan|apply}.json.tftpl`. Each policy uses the account's exact `token.actions.githubusercontent.com` OIDC provider ARN, `sts:AssumeRoleWithWebIdentity`, `aud=sts.amazonaws.com`, and one exact environment subject. No wildcard subject is permitted.

The OIDC provider must use issuer `https://token.actions.githubusercontent.com` and client ID/audience `sts.amazonaws.com`. The provider and six roles are bootstrap resources and are not created by this change.

## Solo-owner approval model

This repository is operated by one owner. The owner is the sole required reviewer on apply environments, and self-review is allowed. This creates a deliberate manual pause before deployment, but it is **not independent approval or separation of duties**. No teammate or second GitHub username is required.

- Plan environments have no required reviewer.
- Apply environments require the repository owner's manual approval checkpoint.
- Environment branch restrictions remain mandatory.
- The owner must inspect the exact Terraform plan and approve each apply separately.
- Production and billing remain separate from dev and each require their own plan/apply workflow.

## Workflow controls

The manual Terraform deployment workflow sets the GitHub environment to `environment-operation` (for example `dev-plan` or `prod-apply`) and reads only `vars.AWS_ROLE_ARN` from that environment. This prevents the plan/apply role selector from being shared across both operations.

The workflow branch gate remains:
- dev: only `refs/heads/develop`
- prod and billing: only `refs/heads/main`

The workflow permissions remain:
- `actions: read` — verify and download the successful encrypted plan artifact
- `contents: read` — checkout the selected release revision
- `id-token: write` — request the short-lived GitHub OIDC token for AWS

No static AWS access keys, contents write, pull request write or broad repository write permissions are used.

The apply path requires a numeric plan run ID, confirms the plan run is successful, manually dispatched, from the exact deployment workflow path, on the expected release branch and on the exact same commit. It downloads the artifact from that exact run and attempt, decrypts it using the apply environment's age identity, and applies only that saved plan. The encrypted plan artifact retention is one day.

## GitHub environment protection rules

Configure exact deployment branch restrictions:

| Environment | Allowed deployment branch | Required reviewer |
|---|---|---|
| dev-plan | develop only | None |
| dev-apply | develop only | Repository owner; self-review allowed |
| prod-plan | main only | None |
| prod-apply | main only | Repository owner; self-review allowed |
| billing-plan | main only | None |
| billing-apply | main only | Repository owner; self-review allowed |

The owner reviews each pull request diff and confirms CI before merging. Branch protection should require PRs, CI checks and conversation resolution, while blocking force pushes and branch deletion. It must not require an independent approval or latest-push approval because that would contradict the solo-owner model. `.github/CODEOWNERS` assigns ownership to the repository owner only; it must not contain teammate placeholders.

The AWS trust policy distinguishes repository and environment. GitHub environment branch restrictions and the owner-controlled apply checkpoint are therefore part of the deployment boundary. The workflow's branch if-condition is an additional guard, not a replacement for GitHub environment restrictions.

## Required environment variables

All six environments define:
- `AWS_ROLE_ARN` — only that environment's plan or apply role ARN.
- `AWS_ACCOUNT_ID` — verified 12-digit account ID.
- `TF_STATE_BUCKET` — final globally unique state bucket name.
- `ALERT_EMAIL` — approved alert subscription email.

Dev/prod environments additionally define:
- `EXECUTION_ROLE_BOUNDARY_ARN` — matching dev or prod runtime boundary ARN.
- `COGNITO_CALLBACK_URLS`, `COGNITO_LOGOUT_URLS`, `ALLOWED_ORIGINS` — non-empty JSON arrays.
- Plan environments define `TF_PLAN_AGE_RECIPIENT`, the public age recipient.

Billing environments do not consume runtime boundary or Cognito callback/origin variables. `billing-plan` defines `TF_PLAN_AGE_RECIPIENT`; `billing-apply` defines the `TF_PLAN_AGE_IDENTITY` secret if required by its workflow.

Apply environments define `TF_PLAN_AGE_IDENTITY` as a secret, containing only the matching private age identity. Use distinct identities for dev, prod and billing. Never store private identities in repository variables, source control, artifacts or logs.

Production callback/logout URLs and allowed origins must be final HTTPS site origins. Localhost values in example tfvars are placeholders only and must not be used for production deployment.

## Approval boundary

The six trust policies are templates only. OIDC provider creation, role creation, role permission attachments, GitHub environment creation/configuration, variables/secrets and branch protection remain explicit approval gates. No AWS resources or GitHub environment settings were changed by this task.

See `docs/GITHUB-ENVIRONMENT-SETUP.md` for the owner configuration checklist and verification limitations.
