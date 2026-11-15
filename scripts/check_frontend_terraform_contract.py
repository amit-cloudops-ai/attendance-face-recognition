"""Guard frontend callback and generated-config contracts used by Terraform."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    raise SystemExit(f"Frontend/Terraform contract check failed: {message}")


auth = (ROOT / "web/shared/auth.js").read_text(encoding="utf-8")
redirect = "redirect_uri: `${location.origin}/callback.html`"
if auth.count(redirect) != 2:
    fail("both Cognito authorize and token requests must use /callback.html")

for environment in ("dev", "prod"):
    path = ROOT / f"infra/envs/{environment}/terraform.tfvars.example"
    example = path.read_text(encoding="utf-8")

    def value(name: str) -> str:
        line = next(
            (line for line in example.splitlines() if line.strip().startswith(f"{name} ")),
            None,
        )
        if line is None or "=" not in line:
            fail(f"{path.relative_to(ROOT)} must define {name}")
        raw = line.split("=", 1)[1].split("#", 1)[0].strip()
        if len(raw) < 2 or raw[0] != '"' or raw[-1] != '"':
            fail(f"{path.relative_to(ROOT)} {name} must be a quoted string")
        return raw[1:-1]

    account_id = value("account_id")
    api_id = value("api_id")
    boundary_arn = value("execution_role_boundary_arn")
    callback_line = next(
        (line for line in example.splitlines() if line.strip().startswith("callback_urls")),
        None,
    )
    if callback_line is None or '["' not in callback_line or '"]' not in callback_line:
        fail(f"{environment} must define one callback_urls URL")
    callback_url = callback_line.split('["', 1)[1].split('"]', 1)[0]
    if not re.fullmatch(r"\d{12}", account_id):
        fail(f"{environment} account_id must be a 12-digit account ID")
    if not re.fullmatch(r"[a-z0-9]{10}", api_id):
        fail(f"{environment} api_id must be a 10-character lowercase alphanumeric placeholder")
    expected_boundary = (
        f"arn:aws:iam::{account_id}:policy/attendance-{environment}-execution-boundary"
    )
    if boundary_arn != expected_boundary:
        fail(f"{environment} execution_role_boundary_arn must equal {expected_boundary}")
    if urlparse(callback_url).path != "/callback.html":
        fail(f"{environment} Cognito callback URL must use /callback.html")

access = (ROOT / "infra/modules/access/main.tf").read_text(encoding="utf-8")
if 'fileset(local.frontend_root, "**")' not in access or 'path != "config.json"' not in access:
    fail("Terraform frontend fileset must exclude the generated config.json")

print("Frontend/Terraform config contract checks passed.")
