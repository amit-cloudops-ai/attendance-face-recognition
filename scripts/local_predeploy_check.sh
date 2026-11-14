#!/usr/bin/env bash
# Local static pre-deployment checks. No AWS API calls and no remote backend access.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

for command in python3 node bash terraform; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Required command not found: $command" >&2
    exit 2
  fi
done

python3 -m ruff --version >/dev/null 2>&1 || {
  echo "Ruff is missing. Install repository dev dependencies first: python3 -m pip install -r requirements-dev.txt" >&2
  exit 2
}
python3 -m pytest --version >/dev/null 2>&1 || {
  echo "Pytest is missing. Install repository dev dependencies first: python3 -m pip install -r requirements-dev.txt" >&2
  exit 2
}

echo "=== Ruff ==="
python3 -m ruff check .

echo "=== Python unit and contract tests ==="
python3 -m pytest -q

echo "=== Canonical AWS region guard ==="
python3 scripts/check_region_consistency.py

echo "=== Browser JavaScript syntax ==="
while IFS= read -r -d '' file; do
  node --input-type=module --check < "$file"
done < <(find web -type f -name '*.js' -print0)

echo "=== Shell syntax ==="
while IFS= read -r -d '' file; do
  bash -n "$file"
done < <(find scripts -type f -name '*.sh' -print0)

echo "=== Terraform formatting ==="
terraform fmt -check -recursive infra

echo "=== Terraform offline initialization and validation ==="
for root in \
  infra/modules/foundation \
  infra/modules/data \
  infra/modules/recognition \
  infra/modules/access \
  infra/envs/dev \
  infra/envs/prod \
  infra/billing; do
  echo "--- $root ---"
  terraform -chdir="$root" init -backend=false -input=false -lockfile=readonly
  terraform -chdir="$root" validate -no-color
done

echo
echo "LOCAL STATIC CHECKS PASSED."
echo "No AWS APIs were called. No remote backend was initialized. No plan or apply was run."
