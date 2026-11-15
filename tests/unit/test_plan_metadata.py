import json

import pytest

from scripts.verify_plan_metadata import verify_metadata


def _metadata() -> dict[str, str | int]:
    return {
        "format_version": 1,
        "environment": "dev",
        "operation": "plan",
        "run_id": "12345",
        "run_attempt": "2",
        "commit_sha": "a" * 40,
        "branch": "develop",
        "terraform_root": "infra/envs/dev",
        "account_id": "123456789012",
        "state_bucket": "attendance-tf-state-123456789012-ci-test",
        "api_id": "a1b2c3d4e5",
        "region": "us-east-1",
    }


def test_plan_metadata_accepts_exact_apply_context(tmp_path):
    metadata = _metadata()
    path = tmp_path / "tfplan.metadata.json"
    path.write_text(json.dumps(metadata), encoding="utf-8")

    expected = {key: str(value) for key, value in metadata.items() if key != "format_version"}
    expected.pop("operation")
    expected["operation"] = "plan"

    assert verify_metadata(path, expected)["run_attempt"] == "2"


def test_plan_metadata_rejects_wrong_environment_commit_or_api_id(tmp_path):
    metadata = _metadata()
    path = tmp_path / "tfplan.metadata.json"
    path.write_text(json.dumps(metadata), encoding="utf-8")
    expected = {
        "environment": "prod",
        "operation": "plan",
        "run_id": "12345",
        "run_attempt": "2",
        "commit_sha": "b" * 40,
        "branch": "main",
        "terraform_root": "infra/envs/prod",
        "account_id": "123456789012",
        "state_bucket": "attendance-tf-state-123456789012-ci-test",
        "api_id": "z9y8x7w6v5",
        "region": "us-east-1",
    }

    with pytest.raises(ValueError, match="does not match"):
        verify_metadata(path, expected)


def test_plan_metadata_rejects_apply_as_source_operation(tmp_path):
    metadata = _metadata()
    metadata["operation"] = "apply"
    path = tmp_path / "tfplan.metadata.json"
    path.write_text(json.dumps(metadata), encoding="utf-8")
    expected = {key: str(value) for key, value in metadata.items() if key != "format_version"}

    with pytest.raises(ValueError, match="Only a plan artifact"):
        verify_metadata(path, expected)


def test_plan_metadata_rejects_missing_provenance_fields(tmp_path):
    path = tmp_path / "tfplan.metadata.json"
    path.write_text(json.dumps({"format_version": 1}), encoding="utf-8")

    with pytest.raises(ValueError, match="missing required fields"):
        verify_metadata(path, {})
