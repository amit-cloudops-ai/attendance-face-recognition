# AGENTS.md — execution rules

Repository: serverless face-recognition attendance on AWS, Python 3.12, region ap-south-1.
Deadline: mentor demonstration Monday 16 November 2026. Code freeze: Sunday 15 November 2026, 21:00 IST.

## Read first
1. docs/FINISH_LINE.md
2. docs/TASKS.md
3. docs/contracts.md
4. docs/STATUS.md
5. The relevant Part guide under docs/parts/

## Branch ownership
- Amit's independent implementation: `solo/amit-monday`.
- Team integration: `develop`.
- Sushmita: Part B (data and attendance); her branch/PR targets `develop`.
- Gopi: Part C (frontend); his branch/PR targets `develop`.
- Never automatically merge or copy team changes into Amit's solo branch.
- Never push directly to main or develop. Do not overwrite another contributor's branch.

## Engineering rules
- One task ID per work session/PR.
- Read each file and identify callers before editing.
- Do not alter frozen API/data contracts or tests to make implementation pass.
- State root cause and evidence before fixing; smallest change first; maximum two attempts, then revert and report.
- No secrets, AWS account IDs, tokens, credentials, or biometric images in Git.
- Do not log face images, access tokens, or unnecessary personal data.
- Python 3.12; keep Lambda dependencies boto3-only unless Amit approves otherwise.
- Read resource identifiers from environment variables; do not hard-code account-specific names or ARNs.
- Business dates/times use Asia/Kolkata (IST).
- Every PR lists changed files, checks, evidence, contract impact, and known gaps.
- Update docs/STATUS.md only for completed and verified work.

## Required checks
`pytest -q`, `ruff check .`, and when present `cfn-lint template.yaml`, `sam validate --lint`, `sam build`.

## Safety
- Never provision or modify AWS resources without Amit's explicit approval.
- Do not claim production readiness unless security, privacy, operations and end-to-end gates have evidence.
- The Monday SAM direction in docs/FINISH_LINE.md supersedes older Terraform deployment instructions for this sprint.
