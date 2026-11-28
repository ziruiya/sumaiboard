#!/bin/bash
# SumaiBoard public sample: daily reset to the fictional seed baseline.
# Normative version (spec 8.4): shares the deployment flock with
# backup/deploy/rollback, refuses to run while a maintenance flag is held,
# and sends the CSRF header on every state-changing call (spec 4.8 item 5).
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
BASE="${SAMPLE_BASE_URL:-http://127.0.0.1:18080}"
LOCK_FILE="/run/lock/sumaiboard-${DEPLOYMENT_ID:-sample}.lock"
exec 9>"$LOCK_FILE"
flock -w 600 9 || { echo "could not acquire deployment lock" >&2; exit 1; }
if [ -f run/maintenance.flag ] || [ -f .maintenance.flag ]; then
  echo "maintenance in progress; refusing to reset" >&2
  exit 1
fi
JAR=$(mktemp)
trap "rm -f $JAR" EXIT
HDR="X-Requested-With: XMLHttpRequest"
FID=$(curl -s "$BASE/api/auth/demo-accounts" | python3 -c "import sys,json; print([a['id'] for a in json.load(sys.stdin)['accounts'] if a['employee_code']=='FN-01'][0])")
curl -s -c "$JAR" -X POST "$BASE/api/auth/demo-login" -H "Content-Type: application/json" -H "$HDR" -d "{\"account_id\": $FID}" > /dev/null
RESP=$(curl -s -b "$JAR" -X POST "$BASE/api/reset" -H "$HDR" -H "X-Sample-Reset-Token: $SAMPLE_RESET_TOKEN")
echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('ok') is True, d"
echo "$(date -Is) sample reset OK"
