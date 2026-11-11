# Part C: Access and Frontend

**Owner:** ______  **Folders you own:** `web/*`, `infra/modules/access/`, `shared/python/attendance_common/auth.py`
**Read first:** SPEC (F02 F09 F10 F11 F13, N03 N05 N11), contracts sections 2, 7, 11.

## Mission
Everything the user touches and everything that guards the door: Cognito login, the API Gateway that fronts all Lambdas, CloudFront with HTTPS, the kiosk app (clock in/out) and the admin app (employees, attendance, reports).

## You depend on / provide
- From Lead: buckets (web bucket name, raw bucket name), KMS key, SNS topic.
- From Parts A and B: their `api_routes` outputs (map of `"METHOD /path"` to function name, invoke ARN, group).
- You provide: the live HTTPS site, `auth.py` (`require_group`, `get_username`), `/config.json`.

## Design direction (CONFIRMED: option A, frozen)
Kiosk: huge, high-contrast, readable from 1 m, one button, big colour-coded result (green present, amber late, red failure). Admin: clean light enterprise style (white, generous spacing, subtle shadows). This is confirmed; build to it, no alternatives.

## Build steps (with why)
**1. Cognito (Terraform).** User pool `attendance-{env}-users` (email sign-in, admin-created users only, self sign-up off), groups `admin` and `kiosk`, app client `attendance-{env}-web` (public, no secret, authorization code + PKCE, scopes `openid email`, access token 60 min, refresh token 30 days), hosted UI domain prefix `attendance-{env}-<account_id>`. Callback URL `https://<cloudfront_domain>/callback.html`, logout URL `https://<cloudfront_domain>/`. Optional TOTP MFA for admins is LATER.

**2. API Gateway HTTP API.** One API, `$default` stage with throttling (10 rps, burst 20) and access logs, JWT authorizer (issuer = the pool, audience = the client id). Build routes with `for_each` over the merged map of `api_routes` from Parts A and B: for each entry create an `AWS_PROXY` integration (payload format 2.0), a route with the authorizer, and an `aws_lambda_permission` (`source_arn = execute-api ARN`). Route keys already contain `/api/...`, so CloudFront forwards the path unchanged.

**3. `auth.py` (shared layer).** `require_group(event, group)` reads `event["requestContext"]["authorizer"]["jwt"]["claims"]["cognito:groups"]`. **Gotcha:** HTTP API stringifies arrays, so the value looks like `"[admin]"` or `"[admin kiosk]"`; match with a word-boundary regex, do not `json.loads`. Return a 403 `forbidden` response if missing. `get_username(event)` returns the `username` claim. An `admin` may call `kiosk` routes.

**4. CloudFront.** One distribution: default origin = web bucket via **OAC** (bucket policy allows only this distribution); second origin = API Gateway domain with behaviour `/api/*` (cache policy CachingDisabled, origin request policy AllViewerExceptHostHeader so the Authorization header passes and the Host header is correct, all HTTP methods allowed). Viewer protocol redirect-to-https, TLS 1.2+, default root object `index.html`. Add a small **CloudFront Function** (viewer request) that rewrites a URI ending in `/` to `/index.html` (so `/admin/` works). Response headers policy: HSTS, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy: camera=(self)`, CSP: `default-src 'self'; connect-src 'self' https://<raw bucket>.s3.ap-south-1.amazonaws.com https://<cognito domain>; img-src 'self' blob: data:; media-src 'self' blob:; script-src 'self'; style-src 'self'`. *Why one domain:* HTTPS (webcam requires it) and no CORS for the API.

**5. Raw bucket CORS (your module owns this one resource).** `aws_s3_bucket_cors_configuration` on the raw bucket: origin = the CloudFront domain, method POST, headers `*`. *Why here:* only you know the CloudFront domain.

**6. `/config.json`.** Terraform `aws_s3_object` in the web bucket with the contract section 11 values, `Cache-Control: no-cache`.

**7. Shared web code (`web/shared`).** `auth.js` (PKCE login redirect, `callback.html` token exchange, refresh with the refresh token, logout, `authFetch` that adds `Authorization: Bearer`), `api.js` (typed wrappers per contract), `ui.css` (tokens). No framework, no build step; ES modules; no inline scripts (CSP).

**8. Kiosk app (`web/kiosk`).**
- Login once (kiosk user), then the camera page: `getUserMedia` (front camera, 1280x720 ideal), live `<video>` with a face-position oval, one big "Clock In / Out" button.
- On click: draw the frame to a canvas scaled to 640 px wide, `toBlob("image/jpeg", 0.8)`; `POST /api/kiosk/upload-url`; send the blob to S3 as `multipart/form-data` with all `fields` first and **`file` as the last field**; then poll `GET /api/kiosk/result/{request_id}` every 500 ms up to 8 s.
- Render by `code`: `matched` shows big name, time, status colour, and "Already clocked in" when `action = duplicate_ignored`; `no_match`, `no_face`, `multiple_faces`, `low_quality`, `inactive`, `error` each get a clear instruction ("Look straight at the camera", "One person at a time", "Move to better light", "Contact HR"). Auto-reset after 4 s. Handle camera permission denied, offline, timeout, expired token (silent refresh, else show login).
- Show a progress state immediately (spinner + "Checking...") so 3 s feels fast. Disable the button while a scan is running.

**9. Admin app (`web/admin`).** Login (admin group; kiosk users are rejected). Pages: **Attendance** (filters: employee, from/to date, status; table with status chips; pagination via `next_cursor`; CSV export of the current filter, SHOULD), **Reports** (pick daily date or ISO week; render the summary; button for `csv_url`), **Employees** (list, add with consent checkbox, deactivate which calls DELETE employee then DELETE faces), **Enroll** (capture 3 to 5 photos; for each: `POST .../enroll-url`, upload, poll the result; show per-photo outcome codes in plain words), **Override** (SHOULD; mandatory reason), **Settings** (SHOULD; threshold, grace, debounce). Escape all server text (no `innerHTML` with data) to avoid XSS.

**10. Deployment of web files.** CI syncs `web/` to the web bucket and invalidates `/*` (Lead owns the workflow; you own cache headers: `no-cache` for HTML and `config.json`, long cache for versioned assets).

## Tests and verification
- Terraform: `terraform validate` and `fmt` clean; plan shows no wildcard policies.
- `auth.py` unit tests: admin ok, kiosk on admin route 403, `"[admin kiosk]"` parsing, missing claim 403.
- Manual matrix (record in STATUS): Chrome desktop, Chrome Android, Safari iOS; camera denied; offline; expired token; slow network.
- Accessibility basics: labels, focus states, colour is never the only signal (text + icon too).

## Pitfalls
- S3 requires the `file` field last in the POST form.
- `/api/*` behaviour must forward `Authorization` and must NOT forward the viewer `Host` header.
- Directory URLs (`/admin/`) need the CloudFront Function or the root-object trick.
- Cognito callback URL must match exactly (scheme, host, path).
- Camera only works on HTTPS (or localhost); test on the CloudFront URL, not file://.
- Tokens: keep access tokens in memory + refresh token in localStorage for the kiosk only; never log them.

## Done when
- [ ] Kiosk at `https://<cloudfront_domain>/` clocks a real enrolled person in, end to end, under 3 s
- [ ] Admin at `/admin/` logs in, filters, paginates, shows reports, enrolls and deactivates an employee
- [ ] Kiosk user cannot call admin endpoints (403 verified); anonymous gets 401
- [ ] Web bucket is private (Block Public Access on); only CloudFront reads it
- [ ] Works on the 3 target browsers; unit tests green in CI
