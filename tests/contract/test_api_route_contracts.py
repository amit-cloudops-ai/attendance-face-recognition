"""Static integration-contract checks across Terraform route outputs and API docs."""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTE = re.compile(r'^\s*"((?:GET|POST|PUT|PATCH|DELETE) /api/[^"]+)" = \{(?P<body>.*?)^\s{4}\}', re.MULTILINE | re.DOTALL)
FUNCTION = re.compile(r'aws_lambda_function\.lambda\["([^"]+)"\]\.function_name')
GROUP = re.compile(r'group\s*=\s*"([^"]+)"')


def _routes(module: str) -> dict[str, dict[str, str]]:
    path = ROOT / "infra" / "modules" / module / "outputs.tf"
    source = path.read_text(encoding="utf-8")
    result = {}
    for match in ROUTE.finditer(source):
        body = match.group("body")
        function = FUNCTION.search(body)
        group = GROUP.search(body)
        assert function, f"{path}: {match.group(1)} has no Lambda function mapping"
        assert group, f"{path}: {match.group(1)} has no authorization group"
        result[match.group(1)] = {
            "function": function.group(1),
            "group": group.group(1).replace(" ", ""),
        }
    return result


def test_terraform_api_routes_match_frozen_contracts():
    routes = _routes("recognition") | _routes("data")
    contracts = (ROOT / "docs" / "contracts.md").read_text(encoding="utf-8")
    api_section = contracts.split("## 7. HTTP API", 1)[1].split("## 8.", 1)[0]
    documented = set(re.findall(r"\x60((?:GET|POST|PUT|PATCH|DELETE) /api/[^\x60]+)\x60", api_section))
    assert set(routes) == documented, (
        f"Terraform/API contract drift. Missing from Terraform: {sorted(documented - set(routes))}; "
        f"missing from contracts: {sorted(set(routes) - documented)}"
    )


def test_each_api_route_has_an_existing_lambda_handler_and_group():
    for module in ("recognition", "data"):
        routes = _routes(module)
        service = "recognition" if module == "recognition" else "data"
        for route, contract in routes.items():
            handler = ROOT / "services" / service / contract["function"] / "handler.py"
            assert handler.is_file(), f"{route} maps to missing handler {handler}"
            assert contract["group"] in {"admin", "kiosk,admin"}, (
                f"{route} has unexpected authorization group {contract['group']}"
            )


def test_access_module_applies_cognito_jwt_authorization_to_all_exported_routes():
    source = (ROOT / "infra" / "modules" / "access" / "main.tf").read_text(encoding="utf-8")
    assert 'resource "aws_apigatewayv2_route" "api"' in source
    assert re.search(r"for_each\s*=\s*var.api_routes", source)
    assert 'authorization_type = "JWT"' in source
    assert "authorizer_id      = aws_apigatewayv2_authorizer.jwt.id" in source


def test_record_scan_request_idempotency_is_documented_and_optional():
    source = (ROOT / "shared" / "python" / "attendance_common" / "record_scan.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "record_scan")
    names = [arg.arg for arg in function.args.args]
    assert names[-1] == "request_id"
    assert isinstance(function.args.defaults[-1], ast.Constant)
    assert function.args.defaults[-1].value is None
    contracts = (ROOT / "docs" / "contracts.md").read_text(encoding="utf-8")
    assert "request_id: str | None = None" in contracts
    assert "Production recognition calls must supply" in contracts
