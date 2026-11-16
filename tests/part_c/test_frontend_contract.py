"""Part C contract tests: static checks on the frontend and the access module.

They need no AWS account or browser. They guard the frozen contract (routes, result codes,
config keys) and the security rules (no browser storage of secrets, no committed photos).
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
ACCESS = ROOT / "infra" / "modules" / "access"

CONTRACT_ROUTES = [
    "/api/kiosk/upload-url",
    "/api/kiosk/result/",
    "/api/admin/employees",
    "/api/admin/attendance",
    "/api/admin/reports",
    "/enroll-url",
    "/faces",
]
KIOSK_CODES = ["matched", "no_match", "no_face", "multiple_faces", "low_quality", "inactive", "error"]
ENROL_CODES = ["unknown_employee", "limit_reached", "duplicate_face"]


def read(path):
    return path.read_text(encoding="utf-8")


def frontend_js():
    parts = [read(FRONTEND / "common.js")]
    for page in FRONTEND.glob("*.html"):
        parts.append(read(page))
    return "\n".join(parts)


def test_config_has_required_keys():
    cfg = json.loads(read(FRONTEND / "config.json"))
    assert set(cfg) == {"apiBase", "cognitoDomain", "clientId"}


def test_all_pages_exist():
    for name in ["index.html", "kiosk.html", "admin.html", "common.js", "style.css"]:
        assert (FRONTEND / name).exists(), name


def test_frontend_calls_every_contract_route():
    js = frontend_js()
    for route in CONTRACT_ROUTES:
        assert route in js, f"route not used by frontend: {route}"


def test_kiosk_handles_every_result_code():
    kiosk = read(FRONTEND / "kiosk.html")
    for code in KIOSK_CODES:
        assert code in kiosk, f"kiosk missing message for {code}"


def test_admin_handles_every_enrolment_code():
    admin = read(FRONTEND / "admin.html")
    for code in ENROL_CODES:
        assert code in admin, f"admin missing message for {code}"


def test_uses_pkce_and_code_flow():
    common = read(FRONTEND / "common.js")
    assert "code_challenge_method:'S256'" in common
    assert "grant_type:'authorization_code'" in common


def test_no_persistent_browser_storage_or_secrets():
    js = frontend_js()
    assert "localStorage" not in js  # tokens live in sessionStorage only
    assert not re.search(r"AKIA[0-9A-Z]{16}", js)  # no AWS keys


def test_admin_requires_consent_and_admin_group():
    admin = read(FRONTEND / "admin.html")
    assert "consent:true" in admin
    assert "requireGroup(['admin']" in admin


def test_kiosk_group_check():
    assert "requireGroup(['kiosk','admin']" in read(FRONTEND / "kiosk.html")


def test_error_body_is_parsed():
    assert "d.error?.message" in read(FRONTEND / "common.js")


def test_terraform_module_files_and_security():
    for name in ["main.tf", "variables.tf", "outputs.tf", "versions.tf"]:
        assert (ACCESS / name).exists(), name
    tf = read(ACCESS / "main.tf")
    assert 'authorization_type = "JWT"' in tf  # every route behind the JWT authorizer
    assert "block_public_policy     = true" in tf
    assert "origin_access_control" in tf
    assert 'allowed_oauth_flows                  = ["code"]' in tf
    assert "allow_admin_create_user_only = true" in tf
    assert "attendance-${var.env}-" in tf


def test_terraform_exposes_hand_off_outputs():
    out = read(ACCESS / "outputs.tf")
    for key in ["api_id", "api_endpoint", "authorizer_id", "user_pool_id", "client_id", "web_bucket", "web_url"]:
        assert f'output "{key}"' in out


def test_example_tfvars_lists_contract_routes():
    example = read(ACCESS / "example.tfvars")
    for route in CONTRACT_ROUTES:
        assert route in example


def test_no_image_files_committed():
    bad = [p for p in ROOT.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"}]
    assert not bad, f"biometric/photo files must not be committed: {bad}"


def test_mock_mode_is_localhost_only():
    common = read(FRONTEND / "common.js")
    assert "['localhost','127.0.0.1'].includes(location.hostname)" in common
    assert "const mocking = () => LOCAL &&" in common
