"""Cross-check the frozen API contract against Terraform route exports."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTE_BLOCK = re.compile(
    r'"(?P<method>GET|POST|PUT|PATCH|DELETE) (?P<path>/api/[^"]+)"\\s*=\\s*\\{'
    r'(?:(?!\\n\\s*\\}).)*?'
    r'function_name\\s*=\\s*aws_lambda_function\\.lambda\\["(?P<function>[^"]+)"\\]\\.function_name'
    r'(?:(?!\\n\\s*\\}).)*?group\\s*=\\s*"(?P<group>[^"]+)"',
    re.DOTALL,
)


def _terraform_routes() -> dict[str, tuple[str, str]]:
    routes: dict[str, tuple[str, str]] = {}
    for path in (
        ROOT / "infra/modules/recognition/outputs.tf",
        ROOT / "infra/modules/data/outputs.tf",
    ):
        content = path.read_text(encoding="utf-8")
        for match in ROUTE_BLOCK.finditer(content):
            route = f"{match.group('method')} {match.group('path')}"
            if route in routes:
                raise AssertionError(f"duplicate Terraform API route: {route}")
            routes[route] = (match.group("function"), match.group("group"))
    return routes


def _documented_routes() -> dict[str, tuple[str, str]]:
    content = (ROOT / "docs/contracts.md").read_text(encoding="utf-8")
    routes: dict[str, tuple[str, str]] = {}
    for line in content.splitlines():
        if not line.startswith("|") or "/api/" not in line:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 4 or not cells[0].startswith("`"):
            continue
        route = cells[0].strip("`")
        group = cells[1].replace(" ", "")
        function = cells[2].split()[0].replace("-", "_")
        if route in routes:
            raise AssertionError(f"duplicate documented API route: {route}")
        routes[route] = (function, group)
    return routes


def test_frozen_api_routes_match_terraform_module_exports() -> None:
    expected = _documented_routes()
    actual = _terraform_routes()
    assert expected, "docs/contracts.md must declare API routes"
    assert actual == expected
