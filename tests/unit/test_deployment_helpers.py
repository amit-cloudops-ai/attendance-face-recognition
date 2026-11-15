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
  *"api user"*) echo "${FAKE_GH_LOGIN:-repo-admin}" ;;
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



@pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("jq") is None,
    reason="Bash and jq are required to exercise the GitHub setup helper",
)
def test_github_environment_setup_rejects_configuring_admin_as_reviewer(tmp_path):
    fake_gh = tmp_path / "gh"
    fake_gh.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == "auth" ]]; then exit 0; fi
case "$*" in
  *".permissions.admin"*) echo true ;;
  *"users/reviewer-user"*) echo 123456 ;;
  *"api user"*) echo reviewer-user ;;
  *".owner.login"*) echo repository-owner ;;
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
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "cannot be the independent deployment reviewer" in result.stderr



@pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("jq") is None,
    reason="Bash and jq are required to exercise the GitHub protection helper",
)
def test_branch_protection_helper_dry_run_lists_all_release_branches(tmp_path):
    fake_gh = tmp_path / "gh"
    fake_gh.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == "auth" ]]; then exit 0; fi
case "$*" in
  *".permissions.admin"*) echo true ;;
  *) echo '{}' ;;
esac
""",
        encoding="utf-8",
    )
    fake_gh.chmod(0o755)
    env = {**os.environ, "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}"}
    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "configure_branch_protection.sh")],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    for branch_name in ("main", "develop", "solo/amit-monday"):
        assert f"Branch: {branch_name}" in result.stdout
    assert result.stdout.count("DRY RUN: no changes made.") == 3
    assert "Required checks: python, terraform-fmt" in result.stdout
    assert "Required independent approvals: 1" in result.stdout
