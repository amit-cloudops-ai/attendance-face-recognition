#!/usr/bin/env bash
# Configure GitHub Actions environments for a solo repository owner.
# Dry-run by default. Requires gh CLI authenticated as a repository administrator.
set -euo pipefail

REPO="amit-cloudops-ai/attendance-face-recognition"
APPLY=false

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/configure_github_environments.sh
  bash scripts/configure_github_environments.sh --apply

Dry-run is the default. The script resolves the repository owner from GitHub,
uses that same owner as the sole manual deployment reviewer for apply environments,
and explicitly allows self-review. This is an owner checkpoint, NOT independent
separation of duties. It creates/updates six environments and their exact
deployment-branch restrictions. It does not set AWS variables or secrets.
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

OWNER="$(gh api "repos/$REPO" --jq '.owner.login')"
OWNER_ID="$(gh api "users/$OWNER" --jq '.id')"
if [[ ! "$OWNER_ID" =~ ^[0-9]+$ ]]; then
  echo "Could not resolve repository owner's GitHub numeric ID." >&2
  exit 2
fi

# environment|branch|owner approval required
ENVIRONMENTS=(
  "dev-plan|develop|false"
  "dev-apply|develop|true"
  "prod-plan|main|false"
  "prod-apply|main|true"
  "billing-plan|main|false"
  "billing-apply|main|true"
)

echo "Repository: $REPO"
echo "Repository owner / sole deployment reviewer: $OWNER (ID $OWNER_ID)"
echo "Self-review: allowed (solo-owner manual checkpoint; not independent approval)"
echo "Mode: $([[ "$APPLY" == true ]] && echo APPLY || echo DRY RUN)"
echo

for item in "${ENVIRONMENTS[@]}"; do
  IFS='|' read -r environment allowed_branch require_owner_approval <<<"$item"
  reviewers='[]'
  if [[ "$require_owner_approval" == true ]]; then
    reviewers="$(jq -cn --argjson id "$OWNER_ID" '[{type:"User",id:$id}]')"
  fi

  payload="$(jq -cn \
    --argjson reviewers "$reviewers" \
    '{
      wait_timer: 0,
      reviewers: $reviewers,
      prevent_self_review: false,
      can_admins_bypass: false,
      deployment_branch_policy: {
        protected_branches: false,
        custom_branch_policies: true
      }
    }')"

  endpoint="repos/$REPO/environments/$environment"
  policies_endpoint="$endpoint/deployment-branch-policies"

  echo "Environment: $environment"
  echo "  Allowed branch: $allowed_branch"
  echo "  Owner approval checkpoint: $require_owner_approval"
  echo "  Self-review: allowed"
  echo "  Admin bypass: disabled"

  if [[ "$APPLY" != true ]]; then
    echo "  DRY RUN: no changes made."
    continue
  fi

  gh api --method PUT "$endpoint" --input - <<<"$payload" >/dev/null

  # Replace any previous custom branch rules so exactly one branch is allowed.
  existing_ids="$(gh api "$policies_endpoint" --jq '.branch_policies[]?.id')"
  while IFS= read -r policy_id; do
    [[ -z "$policy_id" ]] && continue
    gh api --method DELETE "$policies_endpoint/$policy_id" >/dev/null
  done <<<"$existing_ids"

  gh api --method POST "$policies_endpoint" \
    -f name="$allowed_branch" \
    -f type=branch >/dev/null

  echo "  Configured."
done

if [[ "$APPLY" == true ]]; then
  echo
  echo "Environment protection and deployment-branch settings updated."
  echo "AWS_ROLE_ARN, AWS_ACCOUNT_ID, TF_STATE_BUCKET, boundary/config variables,"
  echo "age recipients and apply-only TF_PLAN_AGE_IDENTITY secrets remain unset."
  echo "Populate those only after the AWS bootstrap inventory and approved resource creation."
else
  echo
  echo "Dry run complete. Re-run with --apply to make the listed GitHub settings changes."
fi
