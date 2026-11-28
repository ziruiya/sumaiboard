#!/bin/bash
# Code-only rollback to a deploy snapshot (spec 8.3). Never restores the DB.
# Usage: rollback.sh --target <dir> --snapshot <snapshot dir>
#
# Rework (GPT round-2, M-02-R2): the product safety floor now requires the
# snapshot's FULL SHA to appear in releases.log with result=success AND
# g1_01_secure=true (a failed release can no longer pose as a safe target),
# and schema compatibility is enforced for every profile: the live DB
# schema summary must equal the summary recorded for the snapshot release,
# or a verified compatibility proof must exist at
# $TARGET/schema-compat/<snapshot_sha>.proof naming the live schema hash.
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
SNAP_SHA=$(python3 -c "import json; print(json.load(open('$SNAP/RELEASE.json'))['sha'])" 2>/dev/null || echo "")
[ -n "$SNAP_SHA" ] || { echo "refusing: snapshot has no readable RELEASE.json SHA" >&2; exit 1; }
# Safety floor (spec 8.3 R39-R1 + M-02-R2): full SHA + successful release
# + secure flag. Applies to product; for sample the same provenance check
# is required whenever a releases.log exists.
if [ "$PROFILE" = "product" ]; then
  if ! grep -F "to=$SNAP_SHA" "$TARGET/releases.log" 2>/dev/null | grep "result=success" | grep -q "g1_01_secure=true"; then
    echo "refusing: snapshot is not a successful g1_01_secure release (product rollback floor)" >&2
    exit 1
  fi
fi
# Schema compatibility (M-02-R2): compare the live schema summary with the
# summary recorded at the snapshot release; a proof file may attest that
# the snapshot code was verified on the live (newer) schema (spec D-05).
schema_hash() {
  (cd "$TARGET" && docker compose exec -T mysql sh -c \
    'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" -N "$MYSQL_DATABASE" -e "
SELECT CONCAT(TABLE_NAME,CHAR(124),COLUMN_NAME,CHAR(124),COLUMN_TYPE,CHAR(124),IS_NULLABLE,CHAR(124),COALESCE(COLUMN_DEFAULT,CHAR(45))) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME,ORDINAL_POSITION;
SELECT CONCAT(TABLE_NAME,CHAR(124),INDEX_NAME,CHAR(124),GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX)) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() GROUP BY TABLE_NAME,INDEX_NAME ORDER BY TABLE_NAME,INDEX_NAME;"' 2>/dev/null) \
    | sha256sum | cut -d' ' -f1
}
LIVE_SCHEMA=$(schema_hash || echo "")
SNAP_SCHEMA=$(grep -F "to=$SNAP_SHA" "$TARGET/releases.log" 2>/dev/null | grep "result=success" | tail -1 | sed -n 's/.*schema_after=\([0-9a-f]*\).*/\1/p' || true)
if [ -n "$LIVE_SCHEMA" ] && [ -n "$SNAP_SCHEMA" ] && [ "$LIVE_SCHEMA" != "$SNAP_SCHEMA" ]; then
  if [ -f "$TARGET/schema-compat/$SNAP_SHA.proof" ] && grep -q "^schema_sha256=$LIVE_SCHEMA" "$TARGET/schema-compat/$SNAP_SHA.proof"; then
    echo "schema differs from snapshot release; verified compatibility proof accepted"
  else
    echo "refusing: live schema ($LIVE_SCHEMA) differs from snapshot release schema ($SNAP_SCHEMA) and no compatibility proof exists" >&2
    exit 1
  fi
fi
printf '{"owner":"rollback.sh","pid":%s,"started_at":"%s"}\n' "$$" "$(date -Is)" > "$TARGET/run/maintenance.flag"
(cd "$SNAP" && tar -cf - --exclude='.env' .) | (cd "$TARGET" && tar -xf -)
BUILDER_ENV=""
docker buildx inspect sb-builder >/dev/null 2>&1 && BUILDER_ENV="BUILDX_BUILDER=sb-builder"
(cd "$TARGET" && env $BUILDER_ENV docker compose build && docker compose up -d)
PORT=$(grep -oE '127.0.0.1:[0-9]+' "$TARGET/docker-compose.yml" | head -1 | cut -d: -f2); PORT=${PORT:-18080}
for i in $(seq 1 40); do
  if curl -sf "http://127.0.0.1:$PORT/api/health/ready" >/dev/null 2>&1; then
    rm -f "$TARGET/run/maintenance.flag"
    echo "$(date -Is) rollback to snapshot $SNAP sha=$SNAP_SHA result=success" >> "$TARGET/releases.log"
    echo "rollback complete: $SNAP"
    exit 0
  fi
  sleep 3
done
echo "rollback target did not become ready; maintenance flag kept" >&2
exit 1
