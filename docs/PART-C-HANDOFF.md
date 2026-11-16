# Part C: Access & Frontend, hand-off

Owner: Gopi. Branch: `c/access-frontend`. PR target: `develop`.

## What is in this PR
| Path | Purpose |
|---|---|
| `frontend/` | Kiosk, admin and sign-in pages. Plain HTML/JS (ES modules), no build step. |
| `frontend/common.js` | Auth helper (Cognito Hosted UI, Authorization Code + PKCE, token refresh), API client, S3 pre-signed POST upload, result polling. |
| `infra/modules/access/` | Cognito, HTTP API with JWT authorizer, route integrations from the route map, CORS, private web bucket, CloudFront (OAC), generated `config.json`. |
| `scripts/deploy_frontend.sh` | Syncs `frontend/` to the web bucket and invalidates CloudFront. |
| `tests/part_c/` | Contract and security tests (14), run by the existing pytest CI. |

## Hand-off outputs (module `access`)
`api_id`, `api_endpoint`, `authorizer_id`, `user_pool_id`, `client_id`, `cognito_domain`, `web_bucket`, `cloudfront_distribution_id`, `web_url`.

## Inputs the module needs from other Parts
`route_map`: map of route key to `{ invoke_arn, function_name }`. See `infra/modules/access/example.tfvars`.
Part A supplies the presign, result, enroll-url and delete-faces functions. Part B supplies employees, attendance and reports.

## Cross-Part requirements
- **Part A / lead:** add `web_url` to CORS `AllowedOrigins` on the raw-capture S3 bucket, with method POST and headers `*`. The browser uploads directly to S3.
- **Lead:** after `terraform apply`, create Cognito users and add them to the `admin` or `kiosk` group.
- Handlers must still check the `cognito:groups` claim. The authorizer checks only that the token is valid.

## Deploy
1. `terraform apply` the module with a real `route_map`.
2. `scripts/deploy_frontend.sh <web_bucket> <cloudfront_distribution_id>`.
3. Open `web_url`, sign in, run the kiosk and admin journeys.

## Local test
Add `extra_origins = ["http://localhost:8000"]`, apply, copy the outputs into `frontend/config.json` (do not commit real values), then run `python -m http.server 8000` inside `frontend/`.

## Assumed API shapes (verify against docs/contracts.md)
- Presign: `{request_id, url, fields}` or the same fields under `upload`.
- Result: `{code, name, time, action, message}`. Success code `matched`. Enrolment success code assumed `enrolled`.
- Lists: `{items, next_token}`. Attendance query: `from, to, employee_id, status, limit, next_token`.
- Reports: `{summary, csv_url}` with `period, date`.
If the contract differs, change only `frontend/common.js` and the page that uses the field, and update the tests.

## Known gaps
- No "deactivate employee" button: no route for it was visible in the briefing. Offboarding currently deletes faces only.
- Terraform not yet validated with `init/validate/plan` (needs the Terraform CLI and AWS credentials).
- No browser or end-to-end test has been run.
- The web bucket uses S3-managed encryption unless `kms_key_arn` is set.
