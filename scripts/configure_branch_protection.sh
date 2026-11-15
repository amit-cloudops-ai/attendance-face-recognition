#!/usr/bin/env bash
# Apply PR/status-check protection to the release branches for a solo owner.
# Dry-run by default. Requires gh CLI authenticated as a repository administrator.
set -euo pipefail

REPO="amit-cloudops-ai/attendance-face-recognition"
APPLY=false

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/configure_branch_protection.sh
  bash scripts/configure_branch_protection.sh --apply

Dry-run is the default. --apply protects main, develop and solo/amit-monday:
- PR required; zero mandatory approvals so the solo owner can merge after CI
- python and terraform-fmt checks required and branch must be up to date
- conversations resolved, admin enforcement enabled
- force pushes and branch deletion disabled
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) APPLY=true; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

command -v gh >/dev/null || { echo "GitHub CLI (gh) is required." >&2; exit 2; }
command -v jq >/dev/null || { echo "jq is required." >&2; exit 2; }
gh auth status >/dev/null

ADMIN="$(gh api "repos/$REPO" --jq '.permissions.admin')"
if [[ "$ADMIN" != "true" ]]; then
  echo "The authenticated GitHub user must have repository admin permission." >&2
  exit 2
fi

payload="$(jq -cn '{
  required_status_checks: {
    strict: true,
    contexts: ["python", "terraform-fmt"]
  },
  enforce_admins: true,
  required_pull_request_reviews: {
    dismiss_stale_reviews: true,
    require_code_owner_reviews: false,
    required_approving_review_count: 0,
    require_last_push_approval: false
  },
  restrictions: null,
  required_conversation_resolution: {
    enabled: true
  },
  allow_force_pushes: false,
  allow_deletions: false
}')"

for branch in main develop solo/amit-monday; do
  encoded_branch="$(jq -rn --arg value "$branch" '$value | @uri')"
  endpoint="repos/$REPO/branches/$encoded_branch/protection"
  echo "Branch: $branch"
  echo "  Required checks: python, terraform-fmt"
  echo "  Required approvals: 0 (solo-owner model)"
  echo "  Self-review: allowed"
  echo "  Admin bypass: disabled"
  echo "  Force pushes/deletion: disabled"
  if [[ "$APPLY" == true ]]; then
    gh api --method PUT "$endpoint" --input - <<<"$payload" >/dev/null
    echo "  Protection configured."
  else
    echo "  DRY RUN: no changes made."
  fi
done

if [[ "$APPLY" == true ]]; then
  echo
  echo "Branch protection updated. Verify required check names in GitHub before relying on the rules."
else
  echo
  echo "Dry run complete. Re-run with --apply to apply branch protection."
fi
