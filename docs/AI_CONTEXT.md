# AI Context: paste this (or tell your AI to read it) at the START of every session

You are helping build a **serverless face-recognition attendance system on AWS** in the repo `amit-cloudops-ai/attendance-face-recognition`. Hard deadline: production-ready by **15 Nov 2026**. The design is **frozen**.

## Read first, in this order
1. `docs/SPEC.md` (what "done" means)
2. `docs/contracts.md` (exact names, schemas, endpoints, codes)
3. `docs/STATUS.md` (what is already built, known issues)
4. Your part guide in `docs/parts/` (PART-A, PART-B or PART-C)

## Rules for the AI
1. **Never rename or reshape anything in `docs/contracts.md`.** Use names exactly. If something seems wrong, STOP and tell the human; do not "fix" it silently.
2. Work only inside the files owned by my Part (see CODEOWNERS). Do not edit other Parts' files.
3. Lambdas: Python 3.12, boto3 only, read resource names from environment variables (contracts section 1). No hard-coded names, no new dependencies.
4. Every change needs a unit test. Run `pytest` and `ruff check .` before saying it works. If you cannot run them, say so.
5. Make the smallest change that fixes the problem. When fixing an error, first state the root cause, then list which other files/contracts the fix could affect, then change.
6. Never log or store face images, tokens or secrets. Never use `*` in IAM.
7. Do not add features outside SPEC. Do not refactor unrelated code.
8. At the end of the session: update `docs/STATUS.md` (module status + session log), and list what you changed.

## Project in 10 lines
Kiosk browser captures a still, POSTs it to S3 (pre-signed POST) at `captures/{request_id}.jpg`. S3 event triggers `recognize` Lambda: DetectFaces, SearchFacesByImage (collection `attendance-{env}-faces`), employee lookup, `record_scan` writes DynamoDB attendance, result row written to scan-results, image deleted. Browser polls `GET /api/kiosk/result/{request_id}`. Daily job 23:59 IST marks absences + daily summary to S3; weekly job Monday 00:30 IST writes analytics. Admin app (Cognito, groups admin/kiosk) filters attendance. Web + API served from one CloudFront domain. Terraform modules per Part; GitHub Actions deploys (`develop` to dev, `main` to prod). Deployment target region us-east-1, time zone Asia/Kolkata.

## Session start prompt (copy/paste)
"Read docs/AI_CONTEXT.md, docs/SPEC.md, docs/contracts.md, docs/STATUS.md and docs/parts/PART-<A|B|C>.md in the repo. Confirm in 5 bullets what the project is, which files I own, and the contracts that matter for my task. Then wait for my task."

## Session end prompt (copy/paste)
"List every file you changed and why. Confirm no contract changed. Run pytest and ruff. Update docs/STATUS.md (module status + session log) and commit on my branch."
