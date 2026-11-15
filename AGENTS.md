# Repository working rules

These rules apply to every human and AI contribution in this repository. Read this file before inspecting or changing code.

## 1. Source of truth and branch safety

- Read `docs/STATUS.md`, `docs/TASKS.md`, and the task-specific files before starting work.
- Work on exactly one task ID at a time. The active task must have an entry in `docs/TASKS.md`.
- Create a dedicated branch named `ai/T##-short-description` from the explicitly selected implementation baseline. Do not commit directly to `main` or `develop`.
- Do not modify teammate branches or merge teammate work into the solo implementation unless the repository owner explicitly asks.
- Keep work isolated. Open a pull request when the task is complete; do not merge it without explicit approval.
- The owner has asked to keep work in the current ChatGPT conversation until it becomes too long. Do not force a new chat for each task. Still close one task, update its status, and explicitly select the next task before changing scope.

## 2. Task discipline

- Every work session has one active task ID from `docs/TASKS.md`. Do not silently combine unrelated tasks.
- Before editing, state the task ID, objective, files likely to change, acceptance criteria, and constraints.
- Read the current versions of every file before editing. Do not rely on summaries or stale excerpts.
- Update `docs/STATUS.md` and `docs/TASKS.md` at the end of the task with verified facts, commit/PR references, test results, and remaining blockers.
- Do not mark work complete based only on code inspection. Identify the validation actually performed.

## 3. Fix protocol (mandatory)

1. Reproduce or locate the failure and record the exact evidence: command, CI run/job/log, failing test, or relevant code path.
2. Explain the root cause before editing. Distinguish confirmed facts from hypotheses.
3. Make the smallest change that addresses that root cause. Do not bundle unrelated cleanup or refactoring.
4. Validate the change with the narrowest relevant check, then the full applicable CI suite.
5. Allow at most two fix attempts for the same root cause. If the second attempt does not resolve it, revert the attempted change with `git revert` (or an equivalent isolated revert commit), record the evidence, and report the blocker. Do not stack speculative fixes.
6. Never edit, weaken, skip, delete, or rewrite tests/contracts merely to make a change pass. A legitimate test update requires a separately justified behavior or contract change and explicit owner approval.

## 4. Contracts, security, and infrastructure

- Treat documented API schemas, event payloads, environment variables, data models, and files marked frozen/contract as immutable unless the owner explicitly approves a contract change.
- Never alter tests or contracts to hide a regression.
- Least privilege is required. Verify AWS action names, resource-level support, condition keys, service principals, encryption contexts, and provider operations before calling a policy final.
- No AWS resource creation, IAM/OIDC bootstrap, remote Terraform backend initialization, Terraform plan, or apply without first presenting the exact action/resource/policy/plan and obtaining explicit approval.
- The target AWS region for this project is `us-east-1`. Use the existing AWS account only after the owner approves the specific operation.
- Do not store credentials, private age identities, access keys, or secrets in the repository, GitHub variables, logs, or generated artifacts. Private age identities belong only in protected GitHub environment secrets.

## 5. Validation and reporting

- CI is the authoritative validation environment when local tools are unavailable. Cite the exact run URL, commit SHA, job conclusion, and scope.
- Separate historical results from validation of the current commit.
- Report unverified AWS integration, deployment, performance, browser, and privacy behavior as unverified.
- Do not claim production-ready or deployment-ready while acceptance gates remain open.
- Prefer precise, evidence-backed updates over optimistic summaries.
