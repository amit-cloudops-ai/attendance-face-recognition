"""Cross-check the frozen API contract against Terraform route exports."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _terraform_routes() -> dict[str, tuple[str, str]]:
    routes: dict[str, tuple[str, str]] = {}
    for path in (
        ROOT / "infra/modules/recognition/outputs.tf",
        ROOT / "infra/modules/data/outputs.tf",
    ):
        current_route = None
        function = None
        group = None
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith('"') and stripped.endswith('" = {') and "/api/" in stripped:
                current_route = stripped[1:-5]
                function = None
                group = None
            elif current_route is not None and stripped.startswith("function_name = aws_lambda_function.lambda["):
                function = stripped.split('lambda["', 1)[1].split('"]', 1)[0]
            elif current_route is not None and stripped.startswith("group = "):
                group = stripped.split('"', 2)[1]
            elif current_route is not None and stripped == "}":
                if function is None or group is None:
                    raise AssertionError(f"incomplete Terraform route contract: {current_route}")
                if current_route in routes:
                    raise AssertionError(f"duplicate Terraform API route: {current_route}")
                routes[current_route] = (function, group)
                current_route = None
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
