#!/usr/bin/env python3
"""Fail CI when the repository drifts from its canonical AWS deployment region."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGION_FILE = ROOT / "config" / "deployment.json"
LEGACY_REGION = "ap-" + "south-1"
EXPECTED_REGION = "us-east-1"

def load_region() -> str:
    config = json.loads(REGION_FILE.read_text(encoding="utf-8"))
    region = config.get("aws_region")
    if region != EXPECTED_REGION:
        raise SystemExit(
            f"config/deployment.json must declare {EXPECTED_REGION!r}; found {region!r}"
        )
    return region

def validate() -> None:
    region = load_region()
    errors: list[str] = []

    # These files are human-facing contracts and deployment entry points.
    required_markers = {
        "README.md": f"AWS ({region})",
        "docs/contracts.md": f"| Region | `{region}` |",
        "docs/SPEC.md": f"Single region ({region})",
        "docs/ARCHITECTURE.md": f"Single region {region}",
        "docs/FRONTEND.md": f'"region": "{region}"',
        "docs/parts/PART-A-recognition.md": "AWS_REGION",
        ".github/workflows/deploy.yml": "scripts/check_region_consistency.py --print-region",
    }
    for relative, marker in required_markers.items():
        path = ROOT / relative
        if not path.exists() or marker not in path.read_text(encoding="utf-8"):
            errors.append(f"{relative} is missing the canonical region marker: {marker}")

    # All Terraform roots read the provider region from the same manifest.
    terraform_roots = {
        "infra/envs/dev/versions.tf": "../../../config/deployment.json",
        "infra/envs/prod/versions.tf": "../../../config/deployment.json",
        "infra/billing/versions.tf": "../../config/deployment.json",
    }
    for relative, manifest_path in terraform_roots.items():
        content = (ROOT / relative).read_text(encoding="utf-8")
        if manifest_path not in content or "region = local.deployment_region" not in content:
            errors.append(f"{relative} must load its provider region from {manifest_path}")
        backend = content.split('backend "s3" {', 1)[1].split("}", 1)[0]
        if "region" in backend:
            errors.append(f"{relative} must not duplicate the backend region; use AWS_REGION")

    # Backend examples intentionally omit region; scripts/workflows export the manifest value.
    for relative in (
        "infra/envs/dev/backend.hcl.example",
        "infra/envs/prod/backend.hcl.example",
    ):
        content = (ROOT / relative).read_text(encoding="utf-8")
        if "region" in content:
            errors.append(f"{relative} must not duplicate the canonical region")

    # No active repository file may retain the superseded regional identifier.
    ignored_parts = {".git", ".terraform", "__pycache__", ".venv", "node_modules"}
    scan_roots = (
        ROOT / "README.md",
        ROOT / "config",
        ROOT / "docs",
        ROOT / "infra",
        ROOT / "services",
        ROOT / "shared",
        ROOT / "web",
        ROOT / "scripts",
        ROOT / "tests",
        ROOT / ".github",
    )
    for scan_root in scan_roots:
        candidates = [scan_root] if scan_root.is_file() else scan_root.rglob("*")
        for path in candidates:
            if not path.is_file() or ignored_parts.intersection(path.parts):
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if LEGACY_REGION in content:
                errors.append(f"{path.relative_to(ROOT)} contains a superseded region reference")

    if errors:
        print("AWS region consistency check failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        raise SystemExit(1)

    print(f"AWS region consistency check passed: {region}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--print-region", action="store_true")
    args = parser.parse_args()
    if args.print_region:
        print(load_region())
    else:
        validate()
