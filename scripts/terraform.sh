#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$ROOT/scripts/check_region_consistency.py"
REGION="$(python3 "$ROOT/scripts/check_region_consistency.py" --print-region)"

for variable in AWS_REGION AWS_DEFAULT_REGION; do
  current="${!variable:-}"
  if [[ -n "$current" && "$current" != "$REGION" ]]; then
    echo "Refusing Terraform execution: $variable=$current conflicts with canonical region $REGION." >&2
    exit 2
  fi
done

export AWS_REGION="$REGION"
export AWS_DEFAULT_REGION="$REGION"

terraform_command=""
backend_false=0
for argument in "$@"; do
  [[ "$argument" == "-backend=false" ]] && backend_false=1
  if [[ "$argument" != -* && -z "$terraform_command" ]]; then
    terraform_command="$argument"
  fi
done

needs_account_guard=0
case "$terraform_command" in
  init)
    (( backend_false == 1 )) || needs_account_guard=1
    ;;
  plan|apply|destroy|import|refresh|output|state|workspace|force-unlock|test)
    needs_account_guard=1
    ;;
esac

if (( needs_account_guard )); then
  EXPECTED_AWS_ACCOUNT_ID="${EXPECTED_AWS_ACCOUNT_ID:-${TF_VAR_account_id:-}}"
  if [[ ! "$EXPECTED_AWS_ACCOUNT_ID" =~ ^[0-9]{12}$ ]]; then
    echo "Set EXPECTED_AWS_ACCOUNT_ID to the approved 12-digit account before Terraform init/plan/apply." >&2
    exit 2
  fi
  command -v aws >/dev/null || { echo "AWS CLI is required for the Terraform account guard." >&2; exit 2; }
  ACTUAL_AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text --region "$REGION")"
  if [[ "$ACTUAL_AWS_ACCOUNT_ID" != "$EXPECTED_AWS_ACCOUNT_ID" ]]; then
    echo "Refusing Terraform: credentials resolve to account $ACTUAL_AWS_ACCOUNT_ID, expected $EXPECTED_AWS_ACCOUNT_ID." >&2
    exit 2
  fi
fi

cd "$ROOT"
exec terraform "$@"
