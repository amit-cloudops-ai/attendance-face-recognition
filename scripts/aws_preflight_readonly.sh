#!/usr/bin/env bash
# Read-only AWS inventory. This script contains no create/update/delete/attach commands.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v aws >/dev/null || { echo "AWS CLI v2 is required." >&2; exit 2; }
python scripts/check_region_consistency.py
REGION="$(python scripts/check_region_consistency.py --print-region)"

for variable in AWS_REGION AWS_DEFAULT_REGION; do
  current="${!variable:-}"
  if [[ -n "$current" && "$current" != "$REGION" ]]; then
    echo "Refusing inventory: $variable=$current conflicts with canonical region $REGION." >&2
    exit 2
  fi
done
export AWS_REGION="$REGION"
export AWS_DEFAULT_REGION="$REGION"

echo "=== Canonical deployment region ==="
echo "$REGION"

echo
echo "=== Authenticated AWS identity (read-only STS) ==="
IDENTITY="$(aws sts get-caller-identity --output json)"
printf '%s\n' "$IDENTITY"
ACCOUNT_ID="$(python -c 'import json,sys; print(json.load(sys.stdin)["Account"])' <<<"$IDENTITY")"
if [[ ! "$ACCOUNT_ID" =~ ^[0-9]{12}$ ]]; then
  echo "STS did not return a 12-digit AWS account ID." >&2
  exit 2
fi

report() {
  local label="$1"
  shift
  echo
  echo "=== $label ==="
  if "$@"; then
    :
  else
    echo "NOT CONFIRMED: resource may be absent or caller may lack read permission."
  fi
}

OIDC_ARN="arn:aws:iam::$ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
report "GitHub OIDC provider" aws iam get-open-id-connect-provider \
  --open-id-connect-provider-arn "$OIDC_ARN" --output json

for policy in attendance-dev-execution-boundary attendance-prod-execution-boundary; do
  report "Managed policy: $policy" aws iam list-policies --scope Local \
    --query "Policies[?PolicyName=='$policy'].[PolicyName,Arn,DefaultVersionId]" --output table
done

for role in \
  attendance-github-dev-plan attendance-github-dev-apply \
  attendance-github-prod-plan attendance-github-prod-apply \
  attendance-github-billing-plan attendance-github-billing-apply; do
  echo
  echo "=== IAM role: $role ==="
  if aws iam get-role --role-name "$role" --output json; then
    report "Attached managed policies: $role" aws iam list-attached-role-policies \
      --role-name "$role" --output table
    report "Inline policy names: $role" aws iam list-role-policies \
      --role-name "$role" --output table
  else
    echo "NOT CONFIRMED: role may be absent or caller may lack read permission."
  fi
done

BUCKET="${TF_STATE_BUCKET:-}"
if [[ -z "$BUCKET" ]]; then
  echo
  echo "=== Terraform state bucket ==="
  echo "Skipped: set TF_STATE_BUCKET to the candidate bucket name after choosing the approved suffix."
else
  report "State bucket HEAD: $BUCKET" aws s3api head-bucket --bucket "$BUCKET"
  report "State bucket region: $BUCKET" aws s3api get-bucket-location --bucket "$BUCKET" --output json
  report "State bucket ownership: $BUCKET" aws s3api get-bucket-ownership-controls --bucket "$BUCKET" --output json
  report "State bucket public access block: $BUCKET" aws s3api get-public-access-block --bucket "$BUCKET" --output json
  report "State bucket versioning: $BUCKET" aws s3api get-bucket-versioning --bucket "$BUCKET" --output json
  report "State bucket encryption: $BUCKET" aws s3api get-bucket-encryption --bucket "$BUCKET" --output json
  report "State bucket policy: $BUCKET" aws s3api get-bucket-policy --bucket "$BUCKET" --output json
fi

echo
echo "Read-only inventory finished. No AWS resources or policies were changed."
echo "Treat any access-denied result as unknown, not as proof that a resource is absent."
