#!/usr/bin/env bash
# Create only the tagged API Gateway HTTP API that Terraform will import.
# Default behavior is a dry-run. --apply is a mutating AWS operation and
# requires separate explicit owner approval.
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/bootstrap_api_gateway.sh --env dev|prod --account-id 123456789012 [--profile default] [--apply]

Creates exactly one HTTP API named attendance-<env>-http-api with Project,
Environment and Component tags. If an API with that name already exists, the
script fails closed; inspect and verify it instead of creating a duplicate.
The returned API_ID must be recorded in the matching GitHub environment and
passed to scripts/render_bootstrap_inventory.py --api-id.
USAGE
}

ENVIRONMENT=""
EXPECTED_ACCOUNT_ID=""
PROFILE="${AWS_PROFILE:-default}"
APPLY=false

while (($#)); do
  case "$1" in
    --env)
      ENVIRONMENT="${2:?missing value for --env}"
      shift 2
      ;;
    --account-id)
      EXPECTED_ACCOUNT_ID="${2:?missing value for --account-id}"
      shift 2
      ;;
    --profile)
      PROFILE="${2:?missing value for --profile}"
      shift 2
      ;;
    --apply)
      APPLY=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$ENVIRONMENT" != "dev" && "$ENVIRONMENT" != "prod" ]]; then
  echo "--env must be dev or prod." >&2
  exit 2
fi
if [[ ! "$EXPECTED_ACCOUNT_ID" =~ ^[0-9]{12}$ ]]; then
  echo "--account-id must be exactly 12 digits." >&2
  exit 2
fi

REGION="$(python3 -c 'import json; print(json.load(open("config/deployment.json", encoding="utf-8"))["aws_region"])')"
ACTUAL_ACCOUNT_ID="$(aws sts get-caller-identity --profile "$PROFILE" --region "$REGION" --query Account --output text)"
if [[ "$ACTUAL_ACCOUNT_ID" != "$EXPECTED_ACCOUNT_ID" ]]; then
  echo "AWS profile resolved to account $ACTUAL_ACCOUNT_ID, expected $EXPECTED_ACCOUNT_ID. No resource created." >&2
  exit 1
fi

API_NAME="attendance-$ENVIRONMENT-http-api"
EXISTING_API_ID="$(aws apigatewayv2 get-apis --profile "$PROFILE" --region "$REGION" --query "Items[?Name=='$API_NAME'].ApiId | [0]" --output text)"
if [[ -n "$EXISTING_API_ID" && "$EXISTING_API_ID" != "None" ]]; then
  echo "An API named $API_NAME already exists (ID: $EXISTING_API_ID)." >&2
  echo "No resource created. Verify its ownership, tags and configuration; then use its ID only if it is the intended API." >&2
  exit 2
fi

CREATE_COMMAND=(
  aws apigatewayv2 create-api
  --name "$API_NAME"
  --protocol-type HTTP
  --tags "Project=attendance,Environment=$ENVIRONMENT,Component=access"
  --profile "$PROFILE"
  --region "$REGION"
  --query ApiId
  --output text
)

if [[ "$APPLY" != true ]]; then
  printf 'DRY RUN — no AWS resource will be created.\n'
  printf 'Account: %s\nRegion: %s\nAPI name: %s\n' "$EXPECTED_ACCOUNT_ID" "$REGION" "$API_NAME"
  printf 'Command:'
  printf ' %q' "${CREATE_COMMAND[@]}"
  printf '\nRe-run with --apply only after approving this exact API creation.\n'
  exit 0
fi

API_ID="$("${CREATE_COMMAND[@]}")"
if [[ ! "$API_ID" =~ ^[a-z0-9]{10}$ ]]; then
  echo "AWS returned an unexpected API ID: $API_ID. Inspect the created API before continuing." >&2
  exit 1
fi

printf 'Created API Gateway HTTP API.\nAPI_ID=%s\n' "$API_ID"
printf 'Record this ID in the %s GitHub environment as API_ID and use it when rendering IAM policies.\n' "$ENVIRONMENT"
printf 'Terraform will import this API; do not create a second API from Terraform.\n'
