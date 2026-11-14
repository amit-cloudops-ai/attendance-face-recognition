# Billing environment

This root provisions the project's AWS Budgets. It uses the shared state bucket with its own state key, `attendance/billing/terraform.tfstate`.

## Prerequisites

- Complete the approved AWS bootstrap and create the shared state bucket.
- Copy `backend.hcl.example` to `backend.hcl` and replace the placeholder with the approved bucket name.
- Copy `terraform.tfvars.example` to `terraform.tfvars` and set the alert email.
- Export the intended profile and expected account from the repository root:

```bash
export AWS_PROFILE=default
export EXPECTED_AWS_ACCOUNT_ID=924422830139
```

## Commands

Only after the owner approves remote backend initialization:

```bash
bash scripts/terraform.sh -chdir=infra/billing init -backend-config=backend.hcl
bash scripts/terraform.sh -chdir=infra/billing validate
bash scripts/terraform.sh -chdir=infra/billing plan -var-file=terraform.tfvars
```

**Do not apply the billing root yet.** The two current USD 15 budgets have no cost filters and both monitor total account spend. Resolve T26 by choosing one account-wide budget or separate Environment-tag-filtered budgets before any billing apply. Budget notifications are not a hard spending cap.
