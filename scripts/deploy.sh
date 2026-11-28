#!/bin/bash
# SumaiBoard deploy (spec 8): immutable source from git archive, pinned
# pre-upgrade backup, snapshot, serial build, readiness + smoke.
# Usage: deploy.sh --source <git worktree> --sha <full SHA> --target <dir> --profile <sample|product>
set -euo pipefail
SOURCE=""; SHA=""; TARGET=""; PROFILE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --source) SOURCE="$2"; shift 2;;
    --sha) SHA="$2"; shift 2;;
    --target) TARGET="$2"; shift 2;;
    --profile) PROFILE="$2"; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done
[ -n "$SOURCE" ] && [ -n "$SHA" ] && [ -n "$TARGET" ] && [ -n "$PROFILE" ] || {
  echo "--source --sha --target --profile are all required" >&2; exit 2; }
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p /run/lock
# Deployment id from target env (for the shared lock).
DEPLOYMENT_ID=$(grep -E "^DEPLOYMENT_ID=" "$TARGET/.env" 2>/dev/null | tail -1 | cut -d= -f2- || echo "unknown")
LOCK_FILE="/run/lock/sumaiboard-${DEPLOYMENT_ID}.lock"
exec 9>"$LOCK_FILE"
flock -w 600 9 || { echo "could not acquire deployment lock" >&2; exit 1; }

# 1. Preflight + resources.
"$SCRIPT_DIR/preflight-isolation.sh" --env "$TARGET/.env"
AVAIL_KB=$(df --output=avail -k "$TARGET" | tail -1)
BACKUP_KB=$(du -sk "$(grep -E '^BACKUP_DIR=' "$TARGET/.env" | tail -1 | cut -d= -f2-)" 2>/dev/null | cut -f1 || echo 0)
NEED_KB=$(( BACKUP_KB * 2 + 2 * 1024 * 1024 ))
[ "$AVAIL_KB" -ge "$NEED_KB" ] || { echo "insufficient disk: avail ${AVAIL_KB}KB < need ${NEED_KB}KB" >&2; exit 1; }
# product targets must not carry a sample reset cron (spec 2.5).
if [ "$PROFILE" = "product" ]; then
  if crontab -l 2>/dev/null | grep -F "$TARGET" | grep -qi reset; then
    echo "refusing: a reset cron points at the product target" >&2; exit 1
  fi
fi

# 2. Immutable release tree from git archive.
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
git -C "$SOURCE" archive "$SHA" | tar -x -C "$STAGE"
TREE_HASH=$(git -C "$SOURCE" rev-parse "$SHA^{tree}")
python3 - "$STAGE/RELEASE.json" "$SHA" "$TREE_HASH" <<'PYEOF'
import json, sys, datetime
path, sha, tree = sys.argv[1:4]
json.dump({"sha": sha, "tree_hash": tree,
           "exported_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds")},
          open(path, "w"), indent=2)
PYEOF

# 3. Maintenance + pinned pre-upgrade backup (internal mode inherits lock/flag).
HOST_FLAG="$TARGET/.maintenance.flag"
printf '{"owner":"deploy.sh","pid":%s,"started_at":"%s"}\n' "$$" "$(date -Is)" > "$HOST_FLAG"
FROM_SHA=$(cat "$TARGET/RELEASE.json" 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || echo "")
BACKUP_ID=""
if [ -f "$TARGET/scripts/backup.sh" ]; then
  (cd "$TARGET" && BACKUP_INTERNAL_MODE=1 bash scripts/backup.sh --pinned) || {
    echo "pre-upgrade pinned backup failed - aborting deploy" >&2; exit 1; }
  BACKUP_ID=$(python3 -c "import json; print(json.load(open('$(grep -E '^BACKUP_DIR=' "$TARGET/.env" | tail -1 | cut -d= -f2-)/status/last-success.json'))['backup_id'])" 2>/dev/null || echo "")
fi

# 4. Snapshot current tree (code/compose/docs/scripts + .env only).
SNAP="$TARGET.snapshot-$(date +%Y%m%dT%H%M%S)"
mkdir -p "$SNAP"; chmod 700 "$SNAP"
(cd "$TARGET" && tar -cf - --exclude='*.tar' --exclude='backups' .env docker-compose.yml \
  docker-compose.verify.yml Dockerfile README.md DEPLOY.md RELEASE.json backend frontend scripts docs 2>/dev/null) \
  | tar -xf - -C "$SNAP" || true
ls -dt "$TARGET".snapshot-* 2>/dev/null | tail -n +4 | xargs -r rm -rf

# 5. Install new tree + serial build + up.
(cd "$STAGE" && tar -cf - .) | (cd "$TARGET" && tar -xf -)
cp "$TARGET/.env" "$TARGET/.env" 2>/dev/null || true
(cd "$TARGET" && BUILD_REVISION="$SHA" docker compose build) || {
  echo "build failed - old containers untouched" >&2; rm -f "$HOST_FLAG"; exit 1; }
(cd "$TARGET" && BUILD_REVISION="$SHA" docker compose up -d)

# 6. Readiness (<=120s) + smoke.
PORT=$(grep -oE '127.0.0.1:[0-9]+' "$TARGET/docker-compose.yml" | head -1 | cut -d: -f2)
PORT=${PORT:-18080}
READY=0
for i in $(seq 1 40); do
  if curl -sf "http://127.0.0.1:$PORT/api/health/ready" >/dev/null 2>&1; then READY=1; break; fi
  sleep 3
done
SMOKE="failed"
if [ "$READY" = "1" ]; then
  if curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null && curl -sf "http://127.0.0.1:$PORT/api/public-config" >/dev/null; then
    SMOKE="ok"
    if [ "$PROFILE" = "sample" ]; then
      curl -sf -X POST "http://127.0.0.1:$PORT/api/auth/guest-login" \
        -H "X-Requested-With: XMLHttpRequest" -H "Content-Type: application/json" -d '{}' >/dev/null || SMOKE="guest-login-failed"
    fi
  fi
fi
RESULT="success"
if [ "$SMOKE" != "ok" ]; then
  # Spec 8 failure table: the new release never served, so return to the
  # snapshot release (code only; the DB is never auto-restored). Additive
  # migrations keep the old code runnable on the current schema (D-05).
  RESULT="failed"
  # Gates (spec 8 failure table + R39-R1 floor):
  #  - a real prior release must exist (snapshot carries RELEASE.json);
  #    a first-deploy failure stays in maintenance instead.
  #  - product: the snapshot release must be g1_01_secure per releases.log.
  #  - the failed release must never have completed startup (otherwise a
  #    migration may have run and compatibility is unproven -> maintenance).
  GATE_OK=1
  [ -f "$SNAP/RELEASE.json" ] || GATE_OK=0
  if [ "$GATE_OK" = "1" ] && [ "$PROFILE" = "product" ]; then
    SNAP_SHA=$(python3 -c "import json; print(json.load(open('$SNAP/RELEASE.json'))['sha'])" 2>/dev/null || echo "")
    if [ -z "$SNAP_SHA" ] || ! grep -F "to=$SNAP_SHA" "$TARGET/releases.log" 2>/dev/null | grep -q "g1_01_secure=true"; then
      GATE_OK=0
    fi
  fi
  if [ "$GATE_OK" = "1" ]; then
    if (cd "$TARGET" && docker compose logs --no-color app 2>/dev/null | grep -q "Application startup complete"); then
      GATE_OK=0
    fi
  fi
  if [ "$GATE_OK" != "1" ]; then
    echo "smoke failed ($SMOKE); auto-rollback gates not met - left in maintenance" >&2
  elif (cd "$SNAP" && tar -cf - --exclude=".env" .) | (cd "$TARGET" && tar -xf -); then
    echo "smoke failed ($SMOKE); rolling back to snapshot $SNAP" >&2
    if (cd "$TARGET" && docker compose build >/dev/null 2>&1 && docker compose up -d >/dev/null 2>&1); then
      for i in $(seq 1 40); do
        if curl -sf "http://127.0.0.1:$PORT/api/health/ready" >/dev/null 2>&1; then
          RESULT="failed_rolled_back"; break
        fi
        sleep 3
      done
    fi
  fi
  if [ "$RESULT" != "failed_rolled_back" ]; then
    echo "auto-rollback did not restore readiness; left in maintenance" >&2
  fi
fi
echo "$(date -Is) from=${FROM_SHA:-none} to=$SHA operator=${USER:-root} backup=${BACKUP_ID:-none} result=$RESULT g1_01_secure=true" >> "$TARGET/releases.log"
if [ "$RESULT" = "success" ] || [ "$RESULT" = "failed_rolled_back" ]; then rm -f "$HOST_FLAG"; fi
echo "deploy $RESULT: $SHA (backup: ${BACKUP_ID:-none}, snapshot: $SNAP)"
[ "$RESULT" = "success" ] || [ "$RESULT" = "failed_rolled_back" ]
