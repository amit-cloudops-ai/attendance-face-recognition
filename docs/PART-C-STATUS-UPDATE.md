Paste into docs/STATUS.md under Part C.

| Item | Status | Evidence |
|---|---|---|
| Frontend (kiosk, admin, sign-in, auth helper) | Implemented, not browser-tested | `frontend/`, JS syntax checked |
| Terraform `access` module | Implemented, not validated | `infra/modules/access/` |
| Contract tests | Passing locally (14) | `pytest tests/part_c` |
| Dev deployment and smoke test | Not started | Needs route map from Parts A and B |

Blockers: route-map inputs from Parts A and B; confirmation of API response shapes in docs/contracts.md; deactivate-employee route.
