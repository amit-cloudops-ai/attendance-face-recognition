#!/usr/bin/env bash
# Read-only AWS inventory. This script contains no create/update/delete/attach commands.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v aws >/dev/null || { echo "AWS CLI v2 is required." >&2; exit 2; }
python3 scripts/check_region_consistency.py
REGION="$(python3 scripts/check_region_consistency.py --print-region)"

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
ACCOUNT_ID="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["Account"])' <<<"$IDENTITY")"
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

inspect_managed_policy() {
  local policy_arn="$1"
  local version_id
  echo
  echo "=== Managed policy document: $policy_arn ==="
  if version_id="$(aws iam get-policy --policy-arn "$policy_arn" --query 'Policy.DefaultVersionId' --output text)"; then
    report "Default policy version: $policy_arn" aws iam get-policy-version \
      --policy-arn "$policy_arn" --version-id "$version_id" \
      --query PolicyVersion.Document --output json
  else
    echo "NOT CONFIRMED: unable to read managed policy metadata."
  fi
}

for policy in attendance-dev-execution-boundary attendance-prod-execution-boundary; do
  echo
  echo "=== Runtime permissions boundary: $policy ==="
  if policy_arn="$(aws iam list-policies --scope Local \
      --query "Policies[?PolicyName=='$policy']|[0].Arn" --output text)"; then
    if [[ -n "$policy_arn" && "$policy_arn" != "None" ]]; then
      inspect_managed_policy "$policy_arn"
    else
      echo "NOT CONFIRMED: no matching policy was returned."
    fi
  else
    echo "NOT CONFIRMED: caller may lack IAM read permission."
  fi
done

for role in \
  attendance-github-dev-plan attendance-github-dev-apply \
  attendance-github-prod-plan attendance-github-prod-apply \
  attendance-github-billing-plan attendance-github-billing-apply; do
  echo
  echo "=== IAM role: $role ==="
  if aws iam get-role --role-name "$role" --output json; then
    if attached_arns="$(aws iam list-attached-role-policies --role-name "$role" \
        --query 'AttachedPolicies[].PolicyArn' --output text)"; then
      for policy_arn in $attached_arns; do
        [[ "$policy_arn" == "None" ]] || inspect_managed_policy "$policy_arn"
      done
    else
      echo "NOT CONFIRMED: unable to list attached managed policies."
    fi
    if inline_names="$(aws iam list-role-policies --role-name "$role" \
        --query 'PolicyNames' --output text)"; then
      for policy_name in $inline_names; do
        [[ "$policy_name" == "None" ]] || report "Inline policy document: $role/$policy_name" \
          aws iam get-role-policy --role-name "$role" --policy-name "$policy_name" --output json
      done
    else
      echo "NOT CONFIRMED: unable to list inline policy names."
    fi
  else
    echo "NOT CONFIRMED: role may be absent or caller may lack read permission."
  fi
done

echo
echo "=== Existing application resources (read-only, project prefixes only) ==="
report "Project DynamoDB tables" aws dynamodb list-tables --region "$REGION" \
  --query "TableNames[?starts_with(@, 'attendance-dev-') || starts_with(@, 'attendance-prod-')]" --output json
report "Project KMS aliases" aws kms list-aliases --region "$REGION" \
  --query "Aliases[?AliasName=='alias/attendance-dev' || AliasName=='alias/attendance-prod']" --output json
report "Project Rekognition collections" aws rekognition list-collections --region "$REGION" \
  --query "CollectionIds[?starts_with(@, 'attendance-dev-') || starts_with(@, 'attendance-prod-')]" --output json
report "Project Cognito user pools" aws cognito-idp list-user-pools --max-results 60 --region "$REGION" \
  --query "UserPools[?starts_with(Name, 'attendance-dev-') || starts_with(Name, 'attendance-prod-')]" --output json
report "Project API Gateway v2 APIs" aws apigatewayv2 get-apis --region "$REGION" \
  --query "Items[?starts_with(Name, 'attendance-dev-') || starts_with(Name, 'attendance-prod-')]" --output json
report "Project Lambda functions" aws lambda list-functions --region "$REGION" \
  --query "Functions[?starts_with(FunctionName, 'attendance-dev-') || starts_with(FunctionName, 'attendance-prod-')]" --output json
report "Project SQS queues" aws sqs list-queues --queue-name-prefix attendance- --region "$REGION" --output json
report "Project SNS topics" aws sns list-topics --region "$REGION" \
  --query "Topics[?contains(TopicArn, ':attendance-dev-alerts') || contains(TopicArn, ':attendance-prod-alerts')]" --output json
report "Project EventBridge Scheduler groups" aws scheduler list-schedule-groups --region "$REGION" \
  --query "ScheduleGroups[?starts_with(Name, 'attendance-')]" --output json
for group in attendance-dev attendance-prod; do
  report "Schedules in group $group" aws scheduler list-schedules --group-name "$group" --region "$REGION" --output json
done
report "Project Lambda log groups" aws logs describe-log-groups --log-group-name-prefix /aws/lambda/attendance- --region "$REGION" \
  --query "logGroups[].logGroupName" --output json
report "Project CloudWatch alarms" aws cloudwatch describe-alarms --region "$REGION" \
  --query "MetricAlarms[?starts_with(AlarmName, 'attendance-')]" --output json
report "Project IAM runtime roles" aws iam list-roles \
  --query "Roles[?starts_with(RoleName, 'attendance-dev-') || starts_with(RoleName, 'attendance-prod-')]" --output json
report "Project IAM managed policies" aws iam list-policies --scope Local \
  --query "Policies[?starts_with(PolicyName, 'attendance-dev-') || starts_with(PolicyName, 'attendance-prod-')]" --output json
report "Project AWS Budgets" aws budgets describe-budgets --account-id "$ACCOUNT_ID" \
  --query "Budgets[?starts_with(BudgetName, 'attendance-')]" --output json
report "Project CloudFront distributions" aws cloudfront list-distributions \
  --query "DistributionList.Items[?starts_with(Comment, 'attendance-')].{Id:Id,Comment:Comment,DomainName:DomainName,Enabled:Enabled}" --output json

echo
echo "=== Check globally unique application bucket names (read-only) ==="
for env in dev prod; do
  for kind in raw reports web; do
    candidate="attendance-$env-$kind-$ACCOUNT_ID"
    error_file="$(mktemp)"
    if aws s3api head-bucket --bucket "$candidate" 2>"$error_file"; then
      echo "EXISTS in this account: $candidate"
      report "Bucket location: $candidate" aws s3api get-bucket-location --bucket "$candidate" --output json
      report "Bucket public access block: $candidate" aws s3api get-public-access-block --bucket "$candidate" --output json
      report "Bucket ownership controls: $candidate" aws s3api get-bucket-ownership-controls --bucket "$candidate" --output json
      report "Bucket versioning: $candidate" aws s3api get-bucket-versioning --bucket "$candidate" --output json
      report "Bucket encryption: $candidate" aws s3api get-bucket-encryption --bucket "$candidate" --output json
      report "Bucket policy: $candidate" aws s3api get-bucket-policy --bucket "$candidate" --output json
    elif grep -Eq '\(404\)|Not Found|NoSuchBucket' "$error_file"; then
      echo "NOT FOUND (candidate appears available): $candidate"
    else
      echo "NOT CONFIRMED (possible name collision or missing permission): $candidate"
      cat "$error_file" >&2
    fi
    rm -f "$error_file"
  done
done

BUCKET="${TF_STATE_BUCKET:-}"
if [[ -z "$BUCKET" ]]; then
  echo
  echo "=== Discover existing project state bucket names (read-only) ==="
  if bucket_names="$(aws s3api list-buckets --query 'Buckets[].Name' --output text)"; then
    matches=()
    for candidate in $bucket_names; do
      if [[ "$candidate" == "attendance-tf-state-$ACCOUNT_ID-"* ]]; then
        matches+=("$candidate")
      fi
    done
    if [[ "${#matches[@]}" -eq 1 ]]; then
      BUCKET="${matches[0]}"
      echo "Found one account-prefixed candidate: $BUCKET"
    elif [[ "${#matches[@]}" -gt 1 ]]; then
      echo "Multiple account-prefixed candidates found; set TF_STATE_BUCKET explicitly:"
      printf ' - %s\n' "${matches[@]}"
    else
      echo "No existing bucket matched attendance-tf-state-$ACCOUNT_ID-*."
    fi
  else
    echo "NOT CONFIRMED: unable to list bucket names; caller may lack s3:ListAllMyBuckets."
  fi
fi

if [[ -n "$BUCKET" ]]; then
  report "State bucket HEAD: $BUCKET" aws s3api head-bucket --bucket "$BUCKET"
  report "State bucket region: $BUCKET" aws s3api get-bucket-location --bucket "$BUCKET" --output json
  report "State bucket ownership: $BUCKET" aws s3api get-bucket-ownership-controls --bucket "$BUCKET" --output json
  report "State bucket public access block: $BUCKET" aws s3api get-public-access-block --bucket "$BUCKET" --output json
  report "State bucket versioning: $BUCKET" aws s3api get-bucket-versioning --bucket "$BUCKET" --output json
  report "State bucket encryption: $BUCKET" aws s3api get-bucket-encryption --bucket "$BUCKET" --output json
  report "State bucket policy: $BUCKET" aws s3api get-bucket-policy --bucket "$BUCKET" --output json
else
  echo
  echo "State bucket settings not inspected: no unique existing candidate was identified."
fi

echo
echo "Read-only inventory finished. No AWS resources or policies were changed."
echo "Treat any access-denied result as unknown, not as proof that a resource is absent."
