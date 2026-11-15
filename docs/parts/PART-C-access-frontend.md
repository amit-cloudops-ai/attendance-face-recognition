# Part C — Access and Frontend (Gopi)

> **Historical contributor guide:** this Part A/B/C assignment is retained for technical context only. The active release is owned and integrated on `solo/amit-monday`; do not follow old contributor ownership, teammate or branch instructions for current work.

**Owner:** Gopi. **Integration target:** `develop`. Suggested branch: `team/gopi-part-c`.
**Deadline:** Sunday 15 November 2026, 18:00 IST for a reviewable PR.
**Read first:** `docs/contracts.md` sections 2, 7 and 11; `docs/FINISH_LINE.md`.

## Mission
Deliver the browser-facing kiosk and admin experience using the frozen API. Prioritize correct end-to-end interaction and clear states over visual polish.

## Files you own
- `web/shared/**`
- `web/kiosk/**`
- `web/admin/**`
- Frontend-specific run instructions
Do not edit backend handlers, shared Python modules, Terraform access module, frozen contracts, contract tests or other contributor paths.

## Required implementation
1. **Authentication/API client:** Cognito Hosted UI authorization-code + PKCE with public SPA client; callback exchange, logout and token handling; attach Bearer access token to protected routes; handle missing/expired token, 401/403 and network errors. Never log tokens or place them in URLs.
2. **Kiosk:** camera preview; capture and JPEG resize/compress within the upload limits; request upload URL; submit every returned pre-signed POST field with file last; poll result endpoint; render pending, present, late, duplicate_ignored, no_match, no_face, multiple_faces, low_quality, inactive and error in clear language. Handle camera denial, unsupported browser, offline, timeout and session expiry.
3. **Admin:** require admin group; employee list/create with mandatory consent, enroll 3–5 photos with per-photo result, deactivate employee; attendance filters and pagination; daily/weekly report viewer; CSV link only if supplied by API.
4. **UI quality:** kiosk readable from distance with one primary action; color never the only status signal. Admin is responsive, semantic and keyboard usable. Escape all server-provided text; do not render untrusted values through innerHTML.
5. **Local verification:** document exact run steps and test using mock API or deployed API.

## Verification
Provide screenshots or short recording. Test desktop Chrome and Android Chrome at minimum; mark Safari/iOS not tested if unavailable. Verify camera denied, expired session, offline, missing config, API failure and unknown face. Include browser/device matrix and console-error check.

## Deliverables
- Frontend code only in owned paths.
- PR into develop with route list, changed-file summary, local run steps, screenshots/recording, verification matrix and known gaps.
- Update docs/STATUS.md only for completed and verified behavior.
- No AWS provisioning, credentials, tokens or employee biometric images in Git.

## Out of scope
Attendance calculation, Lambda/data code, Terraform access module, API/schema changes and contract-test edits. Ask Amit before adding dependencies or changing interfaces.
