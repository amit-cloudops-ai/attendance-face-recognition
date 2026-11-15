#!/usr/bin/env bash
# Configure GitHub Actions environments and deployment-branch restrictions.
# Dry-run by default. Requires gh CLI authenticated as a repository administrator.
set -euo pipefail

REPO="amit-cloudops-ai/attendance-face-recognition"
REVIEWER=""
APPLY=false

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/configure_github_environments.sh --reviewer GITHUB_USERNAME
  bash scripts/configure_github_environments.sh --reviewer GITHUB_USERNAME --apply

Dry-run is the default. --apply creates/updates six environments, applies exact
deployment-branch restrictions, and configures independent reviewers.
It does not set AWS variables or secrets; those require verified AWS resource ARNs
and generated age identities after bootstrap.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --reviewer) REVIEWER="${2:?Missing GitHub username}"; shift 2 ;;
    --apply) APPLY=true; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$REVIEWER" ]]; then
  echo "An independent GitHub reviewer username is required." >&2
  usage >&2
  exit 2
fi

command -v gh >/dev/null || { echo "GitHub CLI (gh) is required." >&2; exit 2; }
command -v jq >/dev/null || { echo "jq is required." >&2; exit 2; }
gh auth status >/dev/null

ADMIN="$(gh api "repos/$REPO" --jq '.permissions.admin')"
if [[ "$ADMIN" != "true" ]]; then
  echo "The authenticated GitHub user must have repository admin permission." >&2
  exit 2
fi

ACTOR="$(gh api user --jq '.login')"
if [[ "$REVIEWER" == "$ACTOR" ]]; then
  echo "The authenticated administrator cannot be the independent deployment reviewer." >&2
  exit 2
fi

REVIEWER_ID="$(gh api "users/$REVIEWER" --jq '.id')"
if [[ ! "$REVIEWER_ID" =~ ^[0-9]+$ ]]; then
  echo "Could not resolve reviewer GitHub numeric ID." >&2
  exit 2
fi

OWNER="$(gh api "repos/$REPO" --jq '.owner.login')"
if [[ "$REVIEWER" == "$OWNER" ]]; then
  echo "The repository owner cannot be the independent reviewer." >&2
  exit 2
fi
REVIEWER_PERMISSION="$(gh api "repos/$REPO/collaborators/$REVIEWER/permission" --jq '.permission')"
case "$REVIEWER_PERMISSION" in
  write|maintain|admin) ;;
  *) echo "Reviewer must have repository access; current permission: $REVIEWER_PERMISSION" >&2; exit 2 ;;
esac

# environment|branch|require independent reviewer
ENVIRONMENTS=(
  "dev-plan|develop|false"
  "dev-apply|develop|true"
  "prod-plan|main|true"
  "prod-apply|main|true"
  "billing-plan|main|true"
  "billing-apply|main|true"
)

echo "Repository: $REPO"
echo "Independent reviewer: $REVIEWER (ID $REVIEWER_ID)"
echo "Mode: $([[ "$APPLY" == true ]] && echo APPLY || echo DRY RUN)"
echo

for item in "${ENVIRONMENTS[@]}"; do
  IFS='|' read -r environment allowed_branch require_reviewer <<<"$item"
  reviewers='[]'
  if [[ "$require_reviewer" == true ]]; then
    reviewers="$(jq -cn --argjson id "$REVIEWER_ID" '[{type:"User",id:$id}]')"
  fi

  payload="$(jq -cn \
    --argjson reviewers "$reviewers" \
    '{
      wait_timer: 0,
      reviewers: $reviewers,
      prevent_self_review: true,
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
  echo "  Independent reviewer required: $require_reviewer"
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
