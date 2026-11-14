#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python "$ROOT/scripts/check_region_consistency.py"
REGION="$(python "$ROOT/scripts/check_region_consistency.py" --print-region)"

for variable in AWS_REGION AWS_DEFAULT_REGION; do
  current="${!variable:-}"
  if [[ -n "$current" && "$current" != "$REGION" ]]; then
    echo "Refusing Terraform execution: $variable=$current conflicts with canonical region $REGION." >&2
    exit 2
  fi
done

export AWS_REGION="$REGION"
export AWS_DEFAULT_REGION="$REGION"
exec terraform "$@"
