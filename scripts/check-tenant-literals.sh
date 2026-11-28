#!/bin/bash
# Tenant literal guard (spec 5.3): any tenant literal/reference outside the
# registered baseline fails. Baseline: scripts/tenant-literal-baseline.txt
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BASELINE="$SCRIPT_DIR/tenant-literal-baseline.txt"
CURRENT="$(mktemp)"
trap 'rm -f "$CURRENT"' EXIT
cd "$REPO_DIR"
{
  grep -rn "TENANT_ID" backend/ --include="*.py" || true
  grep -rn "tenant_id * = *1\|tenant_id=1\|tenant_id = 1" backend/ --include="*.py" || true
} | sed 's/[[:space:]]*$//' | sort > "$CURRENT"
if [ ! -f "$BASELINE" ]; then
  echo "baseline missing: $BASELINE" >&2
  exit 1
fi
sort "$BASELINE" > "$CURRENT.base"
NEW_LINES=$(comm -13 "$CURRENT.base" "$CURRENT" || true)
if [ -n "$NEW_LINES" ]; then
  echo "NEW tenant literals outside baseline:" >&2
  echo "$NEW_LINES" >&2
  exit 1
fi
echo "tenant literals: OK ($(wc -l < "$CURRENT") references, all within baseline)"
