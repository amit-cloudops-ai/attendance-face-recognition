#!/usr/bin/env bash
set -euo pipefail

required=(API_BASE ADMIN_TOKEN KIOSK_TOKEN AWS_ACCOUNT_ID RAW_BUCKET EMPLOYEE_ID EMPLOYEE_NAME EMPLOYEE_EMAIL ENROLL_PHOTO_1 ENROLL_PHOTO_2 ENROLL_PHOTO_3 SCAN_PHOTO)
for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required environment variable: $name" >&2
    exit 2
  fi
done

if [[ "${CONSENT_CONFIRMED:-}" != "YES" ]]; then
  echo "Set CONSENT_CONFIRMED=YES only after the test participant has explicitly consented to biometric processing." >&2
  exit 2
fi

for command in curl jq python3 file aws; do
  command -v "$command" >/dev/null || { echo "Required command not found: $command" >&2; exit 2; }
done

if [[ ! "$EMPLOYEE_ID" =~ ^[A-Z0-9_-]{3,20}$ ]]; then
  echo "EMPLOYEE_ID must match ^[A-Z0-9_-]{3,20}$." >&2
  exit 2
fi

API_BASE="${API_BASE%/}"
DEPLOY_REGION="${AWS_REGION:-us-east-1}"
if [[ "$DEPLOY_REGION" != "us-east-1" ]]; then
  echo "Refusing smoke test outside canonical region us-east-1 (got $DEPLOY_REGION)." >&2
  exit 2
fi
if [[ ! "$AWS_ACCOUNT_ID" =~ ^[0-9]{12}$ ]]; then
  echo "AWS_ACCOUNT_ID must be the verified 12-digit dev account ID." >&2
  exit 2
fi
actual_account="$(aws sts get-caller-identity --query Account --output text --region "$DEPLOY_REGION")"
if [[ "$actual_account" != "$AWS_ACCOUNT_ID" ]]; then
  echo "Refusing smoke test: AWS CLI identity $actual_account does not match AWS_ACCOUNT_ID $AWS_ACCOUNT_ID." >&2
  exit 2
fi
RUNS="${RUNS:-20}"
if [[ ! "$RUNS" =~ ^[0-9]+$ ]] || (( RUNS < 20 )); then
  echo "RUNS must be an integer of at least 20." >&2
  exit 2
fi
SHIFT_START="${SHIFT_START:-09:00}"
SHIFT_END="${SHIFT_END:-18:00}"
DEPARTMENT="${DEPARTMENT:-SmokeTest}"
TMP_DIR="$(mktemp -d)"
CREATED=0
LATENCIES=()
RAW_KEYS=()

cleanup() {
  if [[ "$CREATED" == "1" ]]; then
    echo "Cleaning up test employee $EMPLOYEE_ID (attendance history is retained)…"
    curl -sS --max-time 20 -o /dev/null -X DELETE \
      -H "Authorization: Bearer $ADMIN_TOKEN" \
      "$API_BASE/admin/employees/$EMPLOYEE_ID" || true
    curl -sS --max-time 20 -o /dev/null -X DELETE \
      -H "Authorization: Bearer $ADMIN_TOKEN" \
      "$API_BASE/admin/employees/$EMPLOYEE_ID/faces" || true
  fi
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

check_jpeg() {
  local path="$1"
  [[ -f "$path" ]] || { echo "Photo not found: $path" >&2; exit 2; }
  [[ "$(file --brief --mime-type "$path")" == "image/jpeg" ]] || {
    echo "Photo must be JPEG: $path" >&2
    exit 2
  }
  local bytes
  bytes="$(stat -c '%s' "$path")"
  if (( bytes < 1024 || bytes > 1048576 )); then
    echo "Photo must be between 1 KB and 1 MB: $path" >&2
    exit 2
  fi
}

for photo in "$ENROLL_PHOTO_1" "$ENROLL_PHOTO_2" "$ENROLL_PHOTO_3" "$SCAN_PHOTO"; do
  check_jpeg "$photo"
done

api_get() {
  local token="$1" path="$2"
  curl -fsS --max-time 30 -H "Authorization: Bearer $token" "$API_BASE$path"
}

api_post() {
  local token="$1" path="$2" body="$3"
  curl -fsS --max-time 30 -X POST -H "Authorization: Bearer $token" \
    -H "Content-Type: application/json" --data "$body" "$API_BASE$path"
}

upload_presigned() {
  local token="$1" request_path="$2" photo="$3"
  local request upload_url request_id fields_file raw_key
  request="$(api_post "$token" "$request_path" '{}')"
  upload_url="$(jq -er '.upload.url' <<<"$request")"
  request_id="$(jq -er '.request_id' <<<"$request")"
  raw_key="$(jq -er '.upload.fields.key' <<<"$request")"
  RAW_KEYS+=("$raw_key")
  fields_file="$TMP_DIR/fields-$request_id.tsv"
  jq -r '.upload.fields | to_entries[] | [.key, .value] | @tsv' <<<"$request" > "$fields_file"

  local form_args=()
  while IFS=$'\t' read -r key value; do
    form_args+=(--form-string "$key=$value")
  done < "$fields_file"
  # The file part is intentionally last, as required by S3 presigned POST.
  form_args+=(--form "file=@$photo;type=image/jpeg")
  curl -fsS --max-time 30 -o /dev/null -X POST "$upload_url" "${form_args[@]}"
  printf '%s\n' "$request_id"
}

verify_raw_deleted() {
  local key="$1" attempt
  for attempt in $(seq 1 60); do
    if aws s3api head-object --bucket "$RAW_BUCKET" --key "$key" --region "$DEPLOY_REGION" \
      >/dev/null 2>"$TMP_DIR/head-object.err"; then
      sleep 10
      continue
    fi
    if grep -Eq '\((404|NoSuchKey)\)|Not Found' "$TMP_DIR/head-object.err"; then
      return 0
    fi
    echo "Could not verify raw-image deletion for s3://$RAW_BUCKET/$key; AWS returned an unconfirmed error:" >&2
    cat "$TMP_DIR/head-object.err" >&2
    return 1
  done
  echo "Raw image still exists after 10 minutes: s3://$RAW_BUCKET/$key" >&2
  return 1
}

verify_raw_prefixes_empty() {
  local prefix keys
  for prefix in captures/ enroll/; do
    keys="$(aws s3api list-objects-v2 --bucket "$RAW_BUCKET" --prefix "$prefix" \
      --query 'Contents[].Key' --output json --region "$DEPLOY_REGION")"
    if ! jq -e 'length == 0' >/dev/null <<<"$keys"; then
      echo "Raw bucket prefix $prefix is not empty after the smoke test:" >&2
      jq . <<<"$keys" >&2
      return 1
    fi
  done
}

poll_result() {
  local token="$1" request_id="$2"
  local response code
  for _ in $(seq 1 60); do
    response="$(api_get "$token" "/kiosk/result/$request_id")"
    code="$(jq -r '.code // empty' <<<"$response")"
    if [[ -n "$code" && "$code" != "pending" ]]; then
      printf '%s\n' "$response"
      return 0
    fi
    sleep 0.25
  done
  echo "Timed out waiting for result $request_id." >&2
  return 1
}

echo "Creating a consented test employee…"
employee_body="$(jq -n \
  --arg id "$EMPLOYEE_ID" \
  --arg name "$EMPLOYEE_NAME" \
  --arg email "$EMPLOYEE_EMAIL" \
  --arg department "$DEPARTMENT" \
  --arg start "$SHIFT_START" \
  --arg end "$SHIFT_END" \
  '{employee_id:$id,name:$name,email:$email,department:$department,shift_start:$start,shift_end:$end,consent:true}')"
api_post "$ADMIN_TOKEN" "/admin/employees" "$employee_body" > "$TMP_DIR/employee.json"
CREATED=1

for photo in "$ENROLL_PHOTO_1" "$ENROLL_PHOTO_2" "$ENROLL_PHOTO_3"; do
  request_id="$(upload_presigned "$ADMIN_TOKEN" "/admin/employees/$EMPLOYEE_ID/enroll-url" "$photo")"
  outcome="$(poll_result "$ADMIN_TOKEN" "$request_id")"
  code="$(jq -r '.code' <<<"$outcome")"
  verify_raw_deleted "enroll/$EMPLOYEE_ID/$request_id.jpg"
  if [[ "$code" != "enrolled" ]]; then
    echo "Enrollment failed for request $request_id: $(jq -r '.message' <<<"$outcome")" >&2
    exit 1
  fi
done

employee="$(api_get "$ADMIN_TOKEN" "/admin/employees/$EMPLOYEE_ID")"
photo_count="$(jq -r '.photo_count' <<<"$employee")"
if (( photo_count != 3 )); then
  echo "Expected 3 indexed photos; API reports $photo_count." >&2
  exit 1
fi

TODAY_IST="$(python3 -c 'from datetime import datetime; from zoneinfo import ZoneInfo; print(datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat())')"
debounce="$(api_get "$ADMIN_TOKEN" "/admin/settings" | jq -r ".debounce_minutes")"
if [[ ! "$debounce" =~ ^[0-9]+$ ]] || (( debounce < 10 )); then
  echo "Set debounce_minutes to at least 10 for this repeated-scan smoke test." >&2
  exit 2
fi

echo "Running $RUNS kiosk scan cycles for $EMPLOYEE_ID on $TODAY_IST…"

for ((index = 1; index <= RUNS; index += 1)); do
  start_ns="$(python3 -c 'import time; print(time.monotonic_ns())')"
  request_id="$(upload_presigned "$KIOSK_TOKEN" "/kiosk/upload-url" "$SCAN_PHOTO")"
  outcome="$(poll_result "$KIOSK_TOKEN" "$request_id")"
  end_ns="$(python3 -c 'import time; print(time.monotonic_ns())')"
  verify_raw_deleted "captures/$request_id.jpg"
  elapsed_ms="$(( (end_ns - start_ns) / 1000000 ))"
  LATENCIES+=("$elapsed_ms")

  code="$(jq -r '.code' <<<"$outcome")"
  action="$(jq -r '.action // empty' <<<"$outcome")"
  if [[ "$code" != "matched" ]]; then
    echo "Scan $index failed with code=$code: $(jq -r '.message' <<<"$outcome")" >&2
    exit 1
  fi
  if (( index == 1 )) && [[ "$action" != "clock_in" ]]; then
    echo "First scan should clock in; received action=$action." >&2
    exit 1
  fi
  if (( index > 1 )) && [[ "$action" != "duplicate_ignored" ]]; then
    echo "Repeated scan $index should be debounced; received action=$action." >&2
    exit 1
  fi
  printf '  scan %02d: %s ms (%s)\n' "$index" "$elapsed_ms" "$action"
done

attendance="$(api_get "$ADMIN_TOKEN" "/admin/attendance?employee_id=$EMPLOYEE_ID&from=$TODAY_IST&to=$TODAY_IST")"
count="$(jq --arg id "$EMPLOYEE_ID" '[.items[] | select(.employee_id == $id)] | length' <<<"$attendance")"
if (( count < 1 )); then
  echo "Attendance query did not return the test employee's record." >&2
  exit 1
fi

verify_raw_prefixes_empty

p95="$(printf '%s\n' "${LATENCIES[@]}" | sort -n | python3 -c 'import math,sys; values=[int(line) for line in sys.stdin if line.strip()]; print(sorted(values)[math.ceil(.95*len(values))-1])')"
printf '\nAPI-path latency p95: %s ms across %s scans\n' "$p95" "$RUNS"
if (( p95 > 3000 )); then
  echo "API-path p95 exceeded 3 seconds. Browser camera/rendering latency is not included." >&2
  exit 1
fi
echo "Attendance query returned the test employee's record."
echo "All test capture and enrollment objects were verified deleted; captures/ and enroll/ are empty."
echo "Smoke flow passed. The cleanup trap will deactivate the test employee and remove indexed face templates."
echo "Note: this script measures API/upload/recognition round-trip, not browser camera capture or result rendering; it is not standalone evidence for SPEC N01."
