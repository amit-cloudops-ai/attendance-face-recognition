# Phase B — Deployment readiness and AWS access design

**Working branch:** `solo/amit-monday`  
**Scope:** Prepare a controlled development deployment. This document does not authorize AWS resource creation or Terraform apply.

## Verified deployment baseline

- Target account: existing user AWS account; target region: `us-east-1`.
- Dev state key: `attendance/dev/terraform.tfstate`; prod state key: `attendance/prod/terraform.tfstate`.
- Terraform S3 native lock file is enabled (`use_lockfile = true`); Terraform version is constrained to >= 1.10.
- The solo deployment workflow uses GitHub OIDC, separate plan/apply role variables per environment, encrypted saved plan artifacts using `age`, exact plan commit/branch checks and environment branch gates.
- Dev workflow runs only from `develop`; prod only from `main`. The solo branch must be promoted through a reviewed PR before workflow dispatch.
- The workflow and Terraform roots have been migrated to `us-east-1`. The repository's current `main` branch has not been promoted and must not be used as the deployment source.

## Security design requirements

1. Plan roles must only refresh/read infrastructure and access the matching environment state/lock object. They must not mutate AWS infrastructure.
2. Apply roles may mutate only the resources in their matching environment root. They must not receive `AdministratorAccess`.
3. Dev and prod roles must never access each other's Terraform state or lock file.
4. `iam:PassRole` must be limited to exact application execution-role ARNs and the correct service principal.
5. Every Terraform-created Lambda and Scheduler role must have the exact pre-created environment permissions boundary. GitHub apply roles may attach the boundary but must not modify/delete its policy or create an unbounded role.
6. The public repository must not upload cleartext Terraform plan files. The current workflow encrypts the plan artifact and decrypts it only during its matching apply job.
7. GitHub environment branch restrictions are required: dev from `develop`, prod from `main`; prod must require reviewer approval.

## Required policy artifacts before bootstrap

- Two runtime permissions-boundary policies: dev and prod. Each caps the allowed runtime actions for the Lambda and Scheduler execution roles. Boundary policies do not grant access by themselves.
- Four GitHub deployment policies: dev plan, dev apply, prod plan, prod apply.
- Two exact OIDC trust documents per environment role pair (dev/prod subjects), with audience `sts.amazonaws.com`.
- A state bucket policy template with public-access block, versioning, SSE-S3, bucket-owner-enforced ownership and TLS-only access.
- Explicit resource ARNs and condition keys wherever supported; unavoidable wildcard resource actions documented individually.

The action inventory in `docs/IAM-LEAST-PRIVILEGE-INVENTORY.md` is an initial candidate list, not a final policy. Before bootstrap, each action must be checked against the pinned AWS provider's actual refresh and mutation calls and AWS service authorization resource-level support. Runtime policies must be reconciled against actual handlers, not inferred only from Terraform resource blocks.

## Remaining Phase B sequence

1. Verify all post-format CI runs are green.
2. Inspect every Lambda handler and reconcile exact runtime actions with each Terraform execution-role policy.
3. Verify AWS service action names, resource ARN support, request condition keys and provider read/write calls for all four modules.
4. Produce the two execution-role boundary policies and four deployment policies, including strict state object/lock isolation.
5. Review workflow and GitHub environment protections, including plan artifact provenance, key isolation and minimum GitHub token permissions.
6. Validate the state bucket security configuration and create the manual bootstrap proposal.
7. Open a reviewed solo-only PR from `solo/amit-monday` into `develop` once the release candidate is ready.

## Manual bootstrap proposal — not yet approved

The eventual bootstrap proposal is expected to include:
- One state bucket in `us-east-1` with public access blocked, versioning, SSE-S3, bucket-owner-enforced ownership and TLS-only bucket policy.
- One GitHub Actions OIDC identity provider, reusing an existing matching provider if present.
- Two customer-managed application execution-role permissions boundaries (dev and prod).
- Four GitHub deployment roles: dev plan/apply and prod plan/apply, with exact trust and permission policies.
- GitHub environments and environment-specific variables/secrets, including separate `age` identity pairs.

No account discovery, account mutation or remote state initialization is part of this proposal. Exact bucket name, account-specific ARNs and policies must be shown before any bootstrap action. Nothing in this document authorizes creating these resources.

## Dev release gates after approved bootstrap

1. Trigger a manual dev `plan` from `develop`.
2. Download/decrypt and review the exact plan artifact. Check for unexpected creates, deletes, replacements, public access, broad IAM grants, incorrect region or data-loss risks.
3. Present the complete plan and exact resource changes for explicit approval.
4. Only after separate approval, trigger `apply` for that exact plan run and commit.
5. Perform CloudFront-origin URL second pass for Cognito callbacks/logout and S3 CORS.
6. Run consent-gated dev integration and end-to-end tests; record latency, deletion and browser evidence.

Production remains blocked until dev acceptance, separate policy review and explicit production approval.

## Safety boundary

No AWS resources have been created by this preparation. No IAM roles, OIDC provider, state bucket, or permissions boundaries have been created; no remote backend has been initialized; no Terraform plan or apply has been run.
