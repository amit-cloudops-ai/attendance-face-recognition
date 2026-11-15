import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("jq") is None,
    reason="Bash and jq are required to exercise the GitHub setup helper",
)
def test_github_environment_setup_dry_run_lists_all_six_environments(tmp_path):
    fake_gh = tmp_path / "gh"
    fake_gh.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == "auth" ]]; then
  exit 0
fi
case "$*" in
  *".permissions.admin"*) echo true ;;
  *".owner.login"*) echo repository-owner ;;
  *"users/reviewer-user"*) echo 123456 ;;
  *".permission"*) echo write ;;
  *) echo '{}' ;;
esac
""",
        encoding="utf-8",
    )
    fake_gh.chmod(0o755)
    env = {**os.environ, "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}"}

    result = subprocess.run(
        [
            "bash",
            str(ROOT / "scripts" / "configure_github_environments.sh"),
            "--reviewer",
            "reviewer-user",
        ],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    for environment, branch in (
        ("dev-plan", "develop"),
        ("dev-apply", "develop"),
        ("prod-plan", "main"),
        ("prod-apply", "main"),
        ("billing-plan", "main"),
        ("billing-apply", "main"),
    ):
        assert f"Environment: {environment}" in result.stdout
        assert f"Allowed branch: {branch}" in result.stdout
    assert result.stdout.count("DRY RUN: no changes made.") == 6
    assert "Mode: DRY RUN" in result.stdout
