#!/bin/bash
# Code-only rollback to a deploy snapshot (spec 8.3). Never restores the DB.
# Usage: rollback.sh --target <dir> --snapshot <snapshot dir>
set -euo pipefail
TARGET=""; SNAP=""
while [ $# -gt 0 ]; do
  case "$1" in
    --target) TARGET="$2"; shift 2;;
    --snapshot) SNAP="$2"; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done
[ -n "$TARGET" ] && [ -n "$SNAP" ] && [ -d "$SNAP" ] || { echo "--target and --snapshot required" >&2; exit 2; }
PROFILE=$(grep -E "^DEPLOYMENT_PROFILE=" "$TARGET/.env" | tail -1 | cut -d= -f2- || echo "")
DEPLOYMENT_ID=$(grep -E "^DEPLOYMENT_ID=" "$TARGET/.env" | tail -1 | cut -d= -f2- || echo "unknown")
exec 9>"/run/lock/sumaiboard-${DEPLOYMENT_ID}.lock"
flock -w 600 9 || { echo "could not acquire deployment lock" >&2; exit 1; }
# Safety floor (spec 8.3 R39-R1): product may only roll back to a
# g1_01_secure release.
if [ "$PROFILE" = "product" ]; then
  SNAP_SHA=$(python3 -c "import json; print(json.load(open('$SNAP/RELEASE.json'))['sha'])" 2>/dev/null || echo "")
  if [ -z "$SNAP_SHA" ] || ! grep -F "to=$SNAP_SHA" "$TARGET/releases.log" 2>/dev/null | grep -q "g1_01_secure=true"; then
    echo "refusing: snapshot is not a g1_01_secure release (product rollback floor)" >&2
    exit 1
  fi
fi
printf '{"owner":"rollback.sh","pid":%s,"started_at":"%s"}\n' "$$" "$(date -Is)" > "$TARGET/.maintenance.flag"
(cd "$SNAP" && tar -cf - --exclude='.env' .) | (cd "$TARGET" && tar -xf -)
(cd "$TARGET" && docker compose build && docker compose up -d)
PORT=$(grep -oE '127.0.0.1:[0-9]+' "$TARGET/docker-compose.yml" | head -1 | cut -d: -f2); PORT=${PORT:-18080}
for i in $(seq 1 40); do
  if curl -sf "http://127.0.0.1:$PORT/api/health/ready" >/dev/null 2>&1; then
    rm -f "$TARGET/.maintenance.flag"
    echo "$(date -Is) rollback to snapshot $SNAP result=success" >> "$TARGET/releases.log"
    echo "rollback complete: $SNAP"
    exit 0
  fi
  sleep 3
done
echo "rollback target did not become ready; maintenance flag kept" >&2
exit 1
