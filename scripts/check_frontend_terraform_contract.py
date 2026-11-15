"""Guard frontend callback and generated-config contracts used by Terraform."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    raise SystemExit(f"Frontend/Terraform contract check failed: {message}")


auth = (ROOT / "web/shared/auth.js").read_text(encoding="utf-8")
redirect_paths = re.findall(
    r"redirect_uri:\\s*`\\$\\{location\\.origin\\}(/[^\`]+)`",
    auth,
)
if len(redirect_paths) != 2 or any(path != "/callback.html" for path in redirect_paths):
    fail("both Cognito authorize and token requests must use /callback.html")

for environment in ("dev", "prod"):
    path = ROOT / f"infra/envs/{environment}/terraform.tfvars.example"
    example = path.read_text(encoding="utf-8")

    def value(name: str) -> str:
        match = re.search(rf"(?m)^{name}\\s*=\\s*\"([^\"]+)\"", example)
        if not match:
            fail(f"{path.relative_to(ROOT)} must define {name}")
        return match.group(1)

    account_id = value("account_id")
    api_id = value("api_id")
    boundary_arn = value("execution_role_boundary_arn")
    callback_match = re.search(r"(?m)^callback_urls\\s*=\\s*\\[\"([^\"]+)\"\\]", example)
    if not re.fullmatch(r"\\d{12}", account_id):
        fail(f"{environment} account_id must be a 12-digit account ID")
    if not re.fullmatch(r"[a-z0-9]{10}", api_id):
        fail(f"{environment} api_id must be a 10-character lowercase alphanumeric placeholder")
    expected_boundary = (
        f"arn:aws:iam::{account_id}:policy/attendance-{environment}-execution-boundary"
    )
    if boundary_arn != expected_boundary:
        fail(f"{environment} execution_role_boundary_arn must equal {expected_boundary}")
    if not callback_match:
        fail(f"{environment} must define exactly one callback_urls example")
    callback_url = callback_match.group(1)
    if urlparse(callback_url).path != "/callback.html":
        fail(f"{environment} Cognito callback URL must use /callback.html")

access = (ROOT / "infra/modules/access/main.tf").read_text(encoding="utf-8")
if 'fileset(local.frontend_root, "**")' not in access or 'path != "config.json"' not in access:
    fail("Terraform frontend fileset must exclude the generated config.json")

print("Frontend/Terraform config contract checks passed.")
