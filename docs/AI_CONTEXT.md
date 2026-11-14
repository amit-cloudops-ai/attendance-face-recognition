# Solo project AI context — Attendance Face Recognition

This is Amit's solo release of `amit-cloudops-ai/attendance-face-recognition`. The active application baseline is `solo/amit-monday`. Do not assume teammate ownership or use the old Part A/B/C contributor branches as the active workflow.

## Read first
1. `AGENTS.md`
2. `docs/STATUS.md`
3. `docs/TASKS.md`
4. `docs/SPEC.md`
5. `docs/contracts.md`
6. The exact implementation, Terraform and tests relevant to the current task.

## Project objective
Build and deploy a secure serverless face-recognition attendance system in the owner's AWS account, region `us-east-1`. The application uses S3, Lambda, Rekognition, DynamoDB, SQS, EventBridge Scheduler, Cognito, API Gateway, CloudFront and Terraform.

## Solo workflow
- Keep the integrated solo application on `solo/amit-monday`.
- For fixes, create a dedicated branch from the current solo baseline and open a PR back into `solo/amit-monday`.
- Do not commit directly to `main` or `develop`.
- Do not merge teammate PRs or historical Part A/B/C branches into the solo release unless Amit explicitly asks.
- Promote to `develop` only after the solo release passes its readiness gates; promote to `main` only after dev acceptance and a separately approved production release.
- Treat `docs/parts/*` and `docs/TEAM_BRIEF.md` as historical team-planning material, not active ownership instructions.
- Keep `docs/contracts.md` stable unless a required interface change is explicitly approved and updated with tests.

## Engineering method
- Audit before changing. Read the actual branch files and current CI evidence; do not rely on old summaries.
- Distinguish implemented, unit-tested, contract-tested, CI-validated, AWS-validated and production-accepted.
- Diagnose root cause, make the smallest safe correction, add regression coverage, and update `docs/STATUS.md` and `docs/TASKS.md`.
- Never weaken tests, hide failures, claim a clean deploy without evidence, or call Terraform validate a substitute for a live plan.
- Check IAM resource scope, trust policy subjects, account/region guards, encryption, logging, retries, idempotency, cleanup and cost before AWS deployment.

## AWS safety — mandatory
- No AWS resources may be created, modified or deleted without showing Amit the exact change plan and receiving explicit approval.
- Read-only AWS inventory is allowed when the owner has selected the account/profile.
- Bootstrap writes, remote backend initialization, Terraform plan, Terraform apply and production apply are separate approval gates.
- Target account verified by read-only STS on 14 November 2026: `924422830139`; target region: `us-east-1`. Reverify identity before any future AWS action.
- Never use static AWS credentials or expose tokens/private age identities in source, logs or artifacts.

## Governance
The project uses a solo-owner approval model. The repository owner is the sole manual reviewer on apply environments and self-review is allowed. This is a manual owner checkpoint, not independent separation of duties. Never ask for a teammate reviewer username.
