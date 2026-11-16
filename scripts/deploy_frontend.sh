#!/usr/bin/env bash
# Usage: scripts/deploy_frontend.sh <web_bucket> <cloudfront_distribution_id>
# Both values are outputs of the access Terraform module. config.json is written by Terraform, so it is skipped.
set -euo pipefail
BUCKET="${1:?web bucket}"; DIST="${2:?cloudfront distribution id}"
aws s3 sync frontend/ "s3://${BUCKET}/" --delete --exclude "config.json" --region ap-south-1
aws cloudfront create-invalidation --distribution-id "${DIST}" --paths "/*" >/dev/null
echo "Deployed frontend to ${BUCKET}"
