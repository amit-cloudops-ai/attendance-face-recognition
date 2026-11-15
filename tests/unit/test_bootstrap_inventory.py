import json
import subprocess

import pytest

from scripts import render_bootstrap_inventory as bootstrap


def test_render_inventory_outputs_all_account_specific_policy_documents(tmp_path):
    output = tmp_path / "rendered"
    manifest = bootstrap.render_inventory(
        bootstrap.POLICY_DIR,
        output,
        "123456789012",
        "a1b2c3d4e5",
        "unit-test",
        "us-east-1",
        "test-only",
    )

    assert manifest["aws_writes_performed"] is False
    assert manifest["remote_backend_initialized"] is False
    assert manifest["terraform_plan_or_apply_run"] is False
    assert manifest["state_bucket"] == "attendance-tf-state-123456789012-unit-test"
    assert manifest["api_id"] == "a1b2c3d4e5"
    assert manifest["template_counts"] == {"trust": 6, "boundary": 2, "managed": 28}
    assert len(manifest["rendered_files"]) == 37

    for path in output.glob("*.json"):
        if path.name == "bootstrap-manifest.json":
            continue
        policy = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(policy["Statement"], list)
        assert "$" + "{account_id}" not in path.read_text(encoding="utf-8")
        assert "$" + "{state_bucket}" not in path.read_text(encoding="utf-8")
        assert "$" + "{api_id}" not in path.read_text(encoding="utf-8")

    trust = json.loads(
        (output / "github-oidc-trust-dev-plan.json").read_text(encoding="utf-8")
    )
    assert trust["Statement"][0]["Principal"]["Federated"] == (
        "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
    )
    state = json.loads(
        (output / "github-apply-dev-state.json").read_text(encoding="utf-8")
    )
    assert state["Statement"][0]["Resource"] == (
        "arn:aws:s3:::attendance-tf-state-123456789012-unit-test"
    )
    bucket_policy = json.loads(
        (output / "state-bucket-policy.json").read_text(encoding="utf-8")
    )
    assert bucket_policy["Statement"][0]["Condition"]["Bool"]["aws:SecureTransport"] == "false"


@pytest.mark.parametrize("suffix", ["UpperCase", "bad_suffix", "-starts-with-dash", "ends-with-dash-", "contains.dot"])
def test_state_bucket_suffix_rejects_invalid_names(suffix):
    with pytest.raises(ValueError):
        bootstrap.validate_suffix(suffix)


def test_state_bucket_suffix_enforces_s3_name_length():
    with pytest.raises(ValueError):
        bootstrap.state_bucket_name("123456789012", "a" * 31)


def test_head_bucket_404_is_the_only_absence_signal(monkeypatch):
    monkeypatch.setattr(
        bootstrap,
        "run_aws",
        lambda *args: subprocess.CompletedProcess(args[0], 1, "", "An error occurred (404) when calling HeadBucket"),
    )
    bootstrap.require_bucket_name_unclaimed("attendance-tf-state-123456789012-test", "default", "us-east-1")

    monkeypatch.setattr(
        bootstrap,
        "run_aws",
        lambda *args: subprocess.CompletedProcess(args[0], 1, "", "An error occurred (403) when calling HeadBucket"),
    )
    with pytest.raises(RuntimeError, match="Could not prove"):
        bootstrap.require_bucket_name_unclaimed("attendance-tf-state-123456789012-test", "default", "us-east-1")


def test_sts_account_id_must_be_12_digits(monkeypatch):
    monkeypatch.setattr(
        bootstrap,
        "run_aws",
        lambda *args: subprocess.CompletedProcess(args[0], 0, '{"Account":"not-an-account"}', ""),
    )
    with pytest.raises(RuntimeError, match="12-digit"):
        bootstrap.get_account_id("default", "us-east-1")


def test_api_id_must_be_exactly_ten_lowercase_alphanumeric_characters():
    assert bootstrap.validate_api_id("a1b2c3d4e5") == "a1b2c3d4e5"
    for api_id in ("ABC1234567", "short", "a1b2c3d4e5f", "contains-dash"):
        with pytest.raises(ValueError, match="10 lowercase alphanumeric"):
            bootstrap.validate_api_id(api_id)
