"""Verify the non-secret provenance metadata bundled with an encrypted Terraform plan."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXPECTED_FIELDS = (
    "format_version",
    "environment",
    "operation",
    "run_id",
    "run_attempt",
    "commit_sha",
    "branch",
    "terraform_root",
    "account_id",
    "api_id",
    "region",
)


def verify_metadata(metadata_path: Path, expected: dict[str, str]) -> dict[str, str]:
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read plan metadata: {exc}") from exc
    if not isinstance(metadata, dict):
        raise ValueError("Plan metadata must be a JSON object")

    missing = [field for field in EXPECTED_FIELDS if field not in metadata]
    if missing:
        raise ValueError(f"Plan metadata is missing required fields: {', '.join(missing)}")

    if metadata["format_version"] != 1:
        raise ValueError("Unsupported plan metadata format version")

    mismatches = {
        key: (metadata.get(key), value)
        for key, value in expected.items()
        if metadata.get(key) != value
    }
    if mismatches:
        details = "; ".join(
            f"{key}: artifact={actual!r}, current={wanted!r}"
            for key, (actual, wanted) in sorted(mismatches.items())
        )
        raise ValueError(f"Saved plan metadata does not match this apply run: {details}")

    if metadata.get("operation") != "plan":
        raise ValueError("Only a plan artifact can be applied")
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True)
    for name in (
        "environment",
        "run-id",
        "run-attempt",
        "commit-sha",
        "branch",
        "terraform-root",
        "account-id",
        "api-id",
        "region",
    ):
        parser.add_argument(f"--{name}", required=True)
    args = parser.parse_args()

    expected = {
        "environment": args.environment,
        "operation": "plan",
        "run_id": args.run_id,
        "run_attempt": args.run_attempt,
        "commit_sha": args.commit_sha,
        "branch": args.branch,
        "terraform_root": args.terraform_root,
        "account_id": args.account_id,
        "api_id": args.api_id,
        "region": args.region,
    }
    try:
        metadata = verify_metadata(args.metadata, expected)
    except ValueError as exc:
        print(f"Plan artifact rejected: {exc}", file=sys.stderr)
        return 2

    print(
        "Verified saved plan metadata: "
        f"environment={metadata['environment']} "
        f"run={metadata['run_id']}/{metadata['run_attempt']} "
        f"commit={metadata['commit_sha']} "
        f"root={metadata['terraform_root']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
