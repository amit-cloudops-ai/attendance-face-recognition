## Current deployment preparation update (2026-11-14)

- Target account: existing AWS account; target region: `us-east-1`.
- Region migration is present in the solo workflow, dev/prod Terraform provider and backend settings, bootstrap guide, Cognito issuer/domain, CSP endpoints and frontend config. The older `main` branch has not been promoted and still contains the original `ap-south-1` README description; do not deploy from `main`.
- Added the IAM action inventory and required pre-created permissions-boundary input. The inventory remains a draft: action/resource mapping and runtime boundary statements require verification before any policy is attached.
- Fixed the Terraform formatting reported by CI on the previous latest commit. Formatting-only commits were applied to the dev/prod root files and data/recognition module files.
- The Python job passed on the previous failing run; Terraform validation was skipped because formatting stopped the Terraform job. New CI runs for the formatting corrections were queued/in progress at this update. Confirm their final results before declaring CI green.
- No AWS resources, IAM roles, OIDC provider or state bucket have been created; no backend init, Terraform plan or apply has been run.

# Project Status (source of truth for "what is built")

**Update this file at the end of every work session (human or AI).** Newest entries at the top of the log.

## Current execution decision (14 Nov 2026)
- **Solo-first delivery is the governing plan.** `solo/amit-monday` is the working implementation and source of truth for completing the application independently. Do not merge teammate branches or PRs into this branch.
- Complete Phase B security and deployment-readiness work on the solo branch. Do not deploy or provision AWS resources until the exact proposed resources, IAM permissions, and reviewed dev Terraform plan have been presented and explicitly approved.
- `main`, `develop`, and teammate branches remain untouched by solo implementation work.

## Phase B deployment readiness (in progress; no AWS provisioning)

- Dev and prod use separate Terraform S3 state keys and native S3 lock files (`use_lockfile = true`); the state bucket remains a manual prerequisite.
- The manual deployment workflow uses GitHub OIDC, distinct plan/apply role selection per environment, encrypted saved plan artifacts (`age`), exact commit/branch validation, and GitHub Environment gates. The workflow only permits dev from `develop` and prod from `main`.
- The IAM inventory identifies Terraform resource families, candidate read/write action groups, state isolation, `iam:PassRole` scope and execution-role permissions-boundary intent. It is not an attachable policy.
- All Lambda and Scheduler execution role resources in the application modules receive a required `execution_role_boundary_arn` input. The boundary policy documents themselves have not yet been finalized or created.
- The latest CI failure remains `terraform fmt -check`; the Python job passed. The four environment/module files received an initial alignment pass, but CI still reports formatting differences in `infra/modules/data/main.tf` and `infra/modules/recognition/main.tf`. Terraform CLI 1.10.5 was not available in the local validation container and its download was blocked by DNS, so those files are not yet confirmed formatted. Do not call this branch CI-green.
- No AWS resources, OIDC provider/roles, state bucket, remote backend initialization, Terraform plan or apply have been created/run.

## Phase B remaining gates

1. Verify completion of the new CI runs and address any further failures.
2. Reconcile the actual runtime Lambda policies against every handler, including Rekognition, S3, DynamoDB, SQS, KMS, SNS and CloudWatch operations.
3. Build two environment-specific execution-role permissions-boundary policies, capped to the union of necessary runtime permissions. The boundary must not grant permissions itself and the GitHub apply roles must not be able to edit or delete it.
4. Validate exact AWS IAM action names, resource-level support, condition keys and Terraform provider read/write calls for all four modules.
5. Produce four attachable GitHub plan/apply policies, with dev/prod state key isolation and strict `iam:PassRole` scopes. Avoid wildcard actions except where AWS requires them.
6. Validate the backend state bucket policy template: block public access, versioning, SSE-S3, bucket-owner-enforced ownership, TLS-only policy, and key/lock object permissions.
7. Review the manual workflow for least-privilege GitHub token permissions, protected environment branch rules, artifact retention and saved-plan provenance.
8. Reconcile GitHub variables/secrets and environment protections. Do not place private age identities in variables or repository files.
9. Prepare a solo-only PR to `develop` after security and CI gates pass. Do not merge teammate PR #2 as part of this solo release.
10. Present the exact bootstrap resource list and policies for approval. Only after separate approval may manual bootstrap be performed; then generate a dev plan, present the complete plan, and obtain explicit approval before apply.

## Phase A reliability hardening

- Recognition retry/recovery, idempotent attendance writes, request-scoped enrollment recovery, SQS failure reconciliation, and safe audited offboarding are implemented locally.
- Repository status records 91 passing Python tests, Ruff, frontend syntax/CSP, Bash, workflow YAML, Terraform formatting and Terraform validation across all modules and environment roots on an earlier commit. This historical validation is not a substitute for verifying the latest commit.
- AWS integration, Rekognition accuracy, browser/device flows, raw-image deletion behaviour and end-to-end latency remain unverified.

## Release acceptance still outstanding

- Dev deployment and post-CloudFront Cognito/CORS configuration.
- Dev integration tests and consent-gated end-to-end smoke test.
- 20-scan p95 latency measurement and raw-image deletion evidence.
- Browser/device checks on Chrome desktop/Android and Safari iOS.
- Security, encryption, IAM and budget alarm evidence.
- Production release only after dev acceptance and a separate production review.

## Session log
- 14 Nov: Resumed repository audit from the previous handoff. Confirmed the target region migration on `solo/amit-monday`, inspected IAM/Phase B docs, deployment workflow, bootstrap notes, Terraform roots and modules. Diagnosed latest CI failure as Terraform formatting only; Python checks passed. Applied formatting-only fixes to the four Terraform files. New CI runs were pending at the time of this update. No AWS resources provisioned.
