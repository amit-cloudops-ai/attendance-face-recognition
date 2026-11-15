"""Render account-specific AWS bootstrap policies without making AWS changes."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POLICY_DIR = ROOT / "infra" / "policies"
REGION_FILE = ROOT / "config" / "deployment.json"
EXPECTED_TEMPLATE_COUNTS = {"trust": 6, "boundary": 2, "managed": 26}
ACCOUNT_PLACEHOLDER = "$" + "{account_id}"
BUCKET_PLACEHOLDER = "$" + "{state_bucket}"
UNRESOLVED_PATTERN = re.compile(re.escape("$") + r"\{[^}]+\}")


def canonical_region() -> str:
    config = json.loads(REGION_FILE.read_text(encoding="utf-8"))
    region = config.get("aws_region")
    if not isinstance(region, str) or not region:
        raise ValueError("config/deployment.json must declare aws_region")
    for name in ("AWS_REGION", "AWS_DEFAULT_REGION"):
        current = os.environ.get(name)
        if current and current != region:
            raise ValueError(f"{name}={current} conflicts with canonical region {region}")
    return region


def validate_suffix(suffix: str) -> str:
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,28}[a-z0-9])?", suffix):
        raise ValueError("suffix must be lowercase letters, digits or hyphens and start/end alphanumeric")
    return suffix


def state_bucket_name(account_id: str, suffix: str) -> str:
    if not re.fullmatch(r"\d{12}", account_id):
        raise ValueError("STS account ID must contain exactly 12 digits")
    validate_suffix(suffix)
    name = f"attendance-tf-state-{account_id}-{suffix}"
    if len(name) > 63:
        raise ValueError("rendered S3 bucket name exceeds 63 characters")
    return name


def run_aws(args: list[str], profile: str, region: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["aws", *args, "--profile", profile, "--region", region],
        capture_output=True,
        text=True,
        check=False,
    )


def get_account_id(profile: str, region: str) -> str:
    result = run_aws(["sts", "get-caller-identity", "--output", "json"], profile, region)
    if result.returncode:
        raise RuntimeError(f"STS identity check failed: {result.stderr.strip()}")
    try:
        account_id = json.loads(result.stdout)["Account"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RuntimeError("STS did not return a valid account ID") from exc
    if not isinstance(account_id, str) or not re.fullmatch(r"\d{12}", account_id):
        raise RuntimeError("STS did not return a 12-digit AWS account ID")
    return account_id


def require_bucket_name_unclaimed(bucket: str, profile: str, region: str) -> None:
    result = run_aws(["s3api", "head-bucket", "--bucket", bucket], profile, region)
    if result.returncode == 0:
        raise RuntimeError(f"Candidate bucket {bucket} already exists or is accessible; inspect it and do not reuse blindly.")
    detail = f"{result.stdout}\n{result.stderr}"
    if re.search(r"\b404\b|Not Found|NoSuchBucket", detail, re.IGNORECASE):
        return
    raise RuntimeError(
        "Could not prove the candidate bucket is absent. Treat 403, 301, timeout and other errors as unknown. "
        f"AWS response: {detail.strip()}"
    )


def _render_policy_templates(
    policy_dir: Path, output_dir: Path, account_id: str, bucket: str
) -> dict[str, list[str]]:
    templates = sorted(policy_dir.glob("*.json.tftpl"))
    groups: dict[str, list[str]] = {"trust": [], "boundary": [], "managed": []}
    if not templates:
        raise RuntimeError(f"No JSON policy templates found in {policy_dir}")

    for template in templates:
        rendered = (
            template.read_text(encoding="utf-8")
            .replace(ACCOUNT_PLACEHOLDER, account_id)
            .replace(BUCKET_PLACEHOLDER, bucket)
        )
        unresolved = UNRESOLVED_PATTERN.findall(rendered)
        if unresolved:
            raise ValueError(f"Unresolved variables in {template.name}: {sorted(set(unresolved))}")
        try:
            policy: Any = json.loads(rendered)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Rendered policy is not valid JSON: {template.name}: {exc}") from exc
        if not isinstance(policy, dict) or not isinstance(policy.get("Statement"), list):
            raise TypeError(f"Unexpected policy document shape: {template.name}")

        if template.name.startswith("github-oidc-trust-"):
            group = "trust"
        elif template.name.startswith("execution-role-boundary-"):
            group = "boundary"
        else:
            group = "managed"

        compact = json.dumps(policy, separators=(",", ":"))
        if group != "trust" and len(compact) > 6144:
            raise ValueError(f"IAM managed policy exceeds 6,144 characters: {template.name} ({len(compact)})")

        output_name = template.name.removesuffix(".tftpl")
        (output_dir / output_name).write_text(
            json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        groups[group].append(output_name)

    actual = {key: len(value) for key, value in groups.items()}
    if actual != EXPECTED_TEMPLATE_COUNTS:
        raise RuntimeError(f"Unexpected bootstrap template inventory: {json.dumps(actual, sort_keys=True)}")
    return groups


def render_inventory(
    policy_dir: Path,
    output_dir: Path,
    account_id: str,
    suffix: str,
    region: str,
    bucket_check: str,
) -> dict[str, Any]:
    bucket = state_bucket_name(account_id, suffix)
    output_dir.mkdir(parents=True, exist_ok=False)
    groups = _render_policy_templates(policy_dir, output_dir, account_id, bucket)

    bucket_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Sid": "DenyInsecureTransport",
            "Effect": "Deny",
            "Principal": {"AWS": "*"},
            "Action": "s3:*",
            "Resource": [f"arn:aws:s3:::{bucket}", f"arn:aws:s3:::{bucket}/*"],
            "Condition": {"Bool": {"aws:SecureTransport": "false"}},
        }],
    }
    (output_dir / "state-bucket-policy.json").write_text(
        json.dumps(bucket_policy, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    manifest = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "account_id": account_id,
        "region": region,
        "state_bucket": bucket,
        "bucket_head_check": bucket_check,
        "aws_writes_performed": False,
        "remote_backend_initialized": False,
        "terraform_plan_or_apply_run": False,
        "template_counts": {key: len(value) for key, value in groups.items()},
        "rendered_files": sorted([*groups["trust"], *groups["boundary"], *groups["managed"], "state-bucket-policy.json"]),
    }
    (output_dir / "bootstrap-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    summary = [
        "# Rendered AWS bootstrap inventory",
        "",
        f"- Account: {account_id}",
        f"- Region: {region}",
        f"- Candidate state bucket: {bucket}",
        f"- HeadBucket result: {bucket_check}",
        "- AWS writes: NONE",
        "- Remote Terraform backend initialization: NOT PERFORMED",
        "- Terraform plan/apply: NOT PERFORMED",
        "",
        "## Rendered policy documents",
        "",
        f"- GitHub OIDC trust documents: {len(groups['trust'])}",
        f"- Runtime permissions boundaries: {len(groups['boundary'])}",
        f"- Plan/apply managed policies: {len(groups['managed'])}",
        "- State bucket TLS-only policy: 1",
        "",
        "Bucket availability is a point-in-time observation, not a reservation. Review every document and recheck immediately before any separately approved create operation.",
    ]
    (output_dir / "README.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render the account-specific bootstrap inventory using read-only AWS checks only."
    )
    parser.add_argument("--suffix", required=True, help="Owner-selected lowercase unique S3 bucket suffix")
    parser.add_argument("--profile", default=os.environ.get("AWS_PROFILE", "default"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / ".local" / "bootstrap-rendered",
        help="Local output directory; must not already exist",
    )
    args = parser.parse_args()

    try:
        region = canonical_region()
        validate_suffix(args.suffix)
        account_id = get_account_id(args.profile, region)
        bucket = state_bucket_name(account_id, args.suffix)
        require_bucket_name_unclaimed(bucket, args.profile, region)
        manifest = render_inventory(
            POLICY_DIR,
            args.output_dir,
            account_id,
            args.suffix,
            region,
            "HeadBucket returned 404 (candidate appeared absent at check time)",
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Bootstrap inventory not rendered: {exc}", file=sys.stderr)
        return 2

    print(f"Rendered {len(manifest['rendered_files'])} policy documents to {args.output_dir}")
    print(f"Candidate bucket: {manifest['state_bucket']}")
    print("Read-only STS and HeadBucket checks only; no AWS resources were changed.")
    print("Bucket availability is not reserved; recheck before any separately approved create.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
