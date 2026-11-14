## Current status — 14 November 2026

### Working agreement and source of truth

- Repository rules are defined in `AGENTS.md`; the task queue is `docs/TASKS.md`; reusable ChatGPT operating instructions are in `docs/CHATGPT_PROJECT_INSTRUCTIONS.md`.
- Work is task-ID based and isolated on `ai/T##-short-description` branches. One task is active at a time. The owner prefers to continue in the current ChatGPT conversation until it becomes too long; do not force a new chat between tasks.
- The implementation baseline for this task is `solo/amit-monday` at `92e9bf53066145949bd430dd8dcbc0e7850df46d`. The governance task branch is `ai/T01-repository-governance`; T02 will continue from this branch so the restored rules stay in the working history.
- Do not commit to `main` or `develop`, alter teammate branches, or merge teammate PRs into solo work without explicit direction.
- Target AWS account: the owner's existing account. Target region: `us-east-1`.

### T01 — repository governance restoration

- **Status:** complete.
- Restored `AGENTS.md`, `docs/TASKS.md`, and `docs/CHATGPT_PROJECT_INSTRUCTIONS.md`.
- Created a 30-task queue. T01 is complete; T02 is the next task and covers KMS key-policy validation for Lambda asynchronous failure destinations.
- Updated CI push triggers to include `ai/**` so task branches receive the repository's existing Python and Terraform checks.
- The CI workflow currently runs Ruff, pytest, browser JavaScript/CSP checks, Bash syntax, workflow YAML parsing, Terraform formatting, and Terraform module/environment-root validation. A `cfn-lint` step is not present in the checked workflow, and no `template.yaml` was found in the checked repository tree; T17 explicitly verifies whether a CloudFormation template exists before adding linting.
- T01 branch validation: GitHub Actions runs [43611844694](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43611844694) and [43611848777](https://github.com/amit-cloudops-ai/attendance-face-recognition/actions/runs/43611848777) completed successfully. Both `python` and `terraform-fmt` jobs passed.

### Phase B — deployment readiness (not complete; no AWS provisioning)

- Region migration and separate dev/prod Terraform state keys are present on the solo implementation branch. The state bucket remains a manual prerequisite.
- The manual deployment workflow uses GitHub OIDC, separate plan/apply role variables, encrypted saved plans using age, commit/branch checks, and GitHub Environment gates. Its workflow logic still requires a dedicated least-privilege and protection review.
- The IAM inventory is a candidate review document, not an attachable policy. Runtime KMS grants have been narrowed by handler in the data and recognition modules; exact key-policy conditions and remaining runtime IAM mappings are not yet fully verified.
- Required execution-role boundary inputs exist, but dev/prod boundary policy documents and the four GitHub plan/apply policies are not finalized.
- Remaining gates are tracked as T02–T18 in `docs/TASKS.md`; PR promotion, dev deployment, production deployment, and acceptance tasks follow as T19–T24.
- CI validation on the implementation baseline is green as noted above. T01 branch CI is green; subsequent tasks will continue on their own `ai/T##` branches.

### Release acceptance

AWS integration, Rekognition accuracy, consent-gated end-to-end behavior, raw-image deletion evidence, 20-scan p95 latency, browser/device compatibility, budget alarms, dev acceptance and production readiness remain unverified.

### Safety boundary

No AWS resources, IAM roles, OIDC provider, permissions boundaries, state bucket or KMS keys have been created by this work. No remote Terraform backend initialization, Terraform plan or Terraform apply has been run. Any such operation requires an exact written plan and separate explicit owner approval before execution.

## Session log

- 14 Nov 2026: Audited repository governance and found the three expected governance files absent from the solo implementation branch. Created `ai/T01-repository-governance` from the verified solo baseline, restored the governance files, created the task board, and added AI task-branch push CI coverage. T01 closed after both CI jobs passed. The next task is T02; no AWS changes. No AWS changes.
