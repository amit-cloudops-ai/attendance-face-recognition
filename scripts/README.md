# E2E smoke test

`e2e_smoke.sh` exercises a deployed dev stack without creating infrastructure. It creates one test employee, enrolls three JPEG photos, performs at least 20 kiosk upload/recognition cycles, verifies duplicate-scan debounce and queries the resulting attendance record. Its cleanup trap deactivates the test employee and deletes indexed face templates; the attendance/audit history remains.

## Safety requirements

- Run against **dev only**, never production.
- Use a consenting test participant and set `CONSENT_CONFIRMED=YES`.
- Do not put biometric photos or tokens in Git, screenshots, logs or shared shell history.
- Photos must be JPEGs between 1 KB and 1 MB. Supply three varied enrollment photos and a scan photo of the same consenting participant.
- Use an admin token and a kiosk-group token from the dev Cognito user pool.
- The test employee ID and email must be unique.

## Required environment

```bash
export API_BASE="https://<dev-api-or-cloudfront-origin>/api"
export ADMIN_TOKEN="<short-lived admin access token>"
export KIOSK_TOKEN="<short-lived kiosk access token>"
export EMPLOYEE_ID="E2E20261114"
export EMPLOYEE_NAME="Consent-based test participant"
export EMPLOYEE_EMAIL="unique-test-address@example.com"
export ENROLL_PHOTO_1="/secure/local/photo-1.jpg"
export ENROLL_PHOTO_2="/secure/local/photo-2.jpg"
export ENROLL_PHOTO_3="/secure/local/photo-3.jpg"
export SCAN_PHOTO="/secure/local/scan.jpg"
export CONSENT_CONFIRMED="YES"
```

Optional: `SHIFT_START`, `SHIFT_END`, `DEPARTMENT`, and `RUNS` (minimum 20; default 20).

Run:

```bash
bash scripts/e2e_smoke.sh
```

The reported p95 measures API request, S3 upload and recognition polling only. It does **not** include browser camera capture or result rendering, so it is not standalone evidence for SPEC N01. Complete the browser/device matrix in `docs/FRONTEND.md` separately.
