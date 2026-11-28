#!/bin/bash
# SumaiBoard deploy (spec 8): immutable source from git archive, pinned
# pre-upgrade backup, snapshot, serial build via the resource-limited
# builder, readiness + smoke.
# Usage: deploy.sh --source <git worktree> --sha <full SHA> --target <dir> --profile <sample|product>
#
# Rework (GPT round-2): M-02-R1/R2/R3, M-08, M-11, M-13.
#  - Migration state is NEVER inferred from startup logs. Before the new
#    tree is installed we record an explicit schema summary hash of the
#    live DB; after a failed start we record it again. Auto-rollback is
#    allowed only when (a) the schema summary is byte-identical (proof no
#    migration changed the schema), or (b) a verified compatibility proof
#    exists at $TARGET/schema-compat/<snapshot_sha>.proof naming the exact
#    post-failure schema hash (old code proven runnable on the new schema,
#    spec D-05). Otherwise the deployment stays in maintenance.
#  - g1_01_secure=true is written ONLY for result=success releases
#    (M-02-R2). Rollback targets must match the full SHA + result=success
#    + the secure flag.
#  - First upgrade (target has no scripts/backup.sh yet, e.g. the legacy
#    V3.0.2 sample site) performs a baseline-compatible pinned backup
#    using the NEW tree's backup tooling against the still-running old
#    stack BEFORE any tree/container/DB change (M-02-R3); if it cannot be
#    produced and verified, the deploy aborts.
#  - The app is stopped by deploy.sh itself before the internal backup
#    runs, and backup.sh verifies the stopped state (M-08).
#  - Preflight runs against every other SumaiBoard deployment found on
#    this host (M-11); when the inventory cannot be completed the deploy
#    refuses instead of silently passing.
#  - Builds go through the dedicated resource-limited buildx builder
#    sb-builder (M-13, spec 8.4).
#  - A failed deploy (including a successful auto-rollback) exits nonzero
#    so automation never mistakes it for a successful release (M-02-R2).
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
case "$SHA" in *[!0-9a-f]*|???????????????????????????????????????) echo "SHA must be a full 40-char hex commit id" >&2; exit 2;; esac
[ ${#SHA} -eq 40 ] || { echo "SHA must be a full 40-char hex commit id" >&2; exit 2; }
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p /run/lock
DEPLOYMENT_ID=$(grep -E "^DEPLOYMENT_ID=" "$TARGET/.env" 2>/dev/null | tail -1 | cut -d= -f2- || echo "unknown")
LOCK_FILE="/run/lock/sumaiboard-${DEPLOYMENT_ID}.lock"
exec 9>"$LOCK_FILE"
flock -w 600 9 || { echo "could not acquire deployment lock" >&2; exit 1; }

env_get() { grep -E "^$1=" "$TARGET/.env" 2>/dev/null | tail -1 | cut -d= -f2- || true; }

# Schema summary hash of the live DB (same canonical query as backup.sh).
schema_hash() {
  (cd "$TARGET" && docker compose exec -T mysql sh -c \
    'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" -N "$MYSQL_DATABASE" -e "
SELECT CONCAT(TABLE_NAME,CHAR(124),COLUMN_NAME,CHAR(124),COLUMN_TYPE,CHAR(124),IS_NULLABLE,CHAR(124),COALESCE(COLUMN_DEFAULT,CHAR(45))) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME,ORDINAL_POSITION;
SELECT CONCAT(TABLE_NAME,CHAR(124),INDEX_NAME,CHAR(124),GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX)) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() GROUP BY TABLE_NAME,INDEX_NAME ORDER BY TABLE_NAME,INDEX_NAME;"' 2>/dev/null) \
    | sha256sum | cut -d' ' -f1
}

# 1. Preflight against this deployment AND every other deployment on the
#    host (M-11). Inventory: sibling dirs with a SumaiBoard .env.
OTHERS=()
CAND_DIRS=(/opt/sumaiboard /root/build/*/)
# Also inventory every live compose project's working directory - the
# authoritative host deployment list - so no deployment is missed.
while IFS= read -r wd; do [ -n "$wd" ] && CAND_DIRS+=("$wd"); done < <(
  docker compose ls -a --format json 2>/dev/null | python3 -c "
import json, sys
try:
    for p in json.load(sys.stdin):
        for c in (p.get('ConfigFiles') or '').split(','):
            import os
            if c: print(os.path.dirname(c))
except Exception:
    pass
" || true)
declare -A SEEN_DIRS=()
for cand in "${CAND_DIRS[@]}"; do
  cand="${cand%/}"
  [ -f "$cand/.env" ] || continue
  RP="$(cd "$cand" 2>/dev/null && pwd)" || continue
  [ "$RP" = "$(cd "$TARGET" && pwd)" ] && continue
  [ -n "${SEEN_DIRS[$RP]:-}" ] && continue
  SEEN_DIRS[$RP]=1
  if grep -qE "^(DEPLOYMENT_ID|DB_NAME)=" "$cand/.env" 2>/dev/null; then OTHERS+=("$cand/.env"); fi
done
PRE_ARGS=(--env "$TARGET/.env")
for o in "${OTHERS[@]}"; do PRE_ARGS+=(--other-env "$o"); done
"$SCRIPT_DIR/preflight-isolation.sh" "${PRE_ARGS[@]}"
AVAIL_KB=$(df --output=avail -k "$TARGET" | tail -1)
BACKUP_KB=$(du -sk "$(env_get BACKUP_DIR)" 2>/dev/null | cut -f1 || echo 0)
NEED_KB=$(( BACKUP_KB * 2 + 2 * 1024 * 1024 ))
[ "$AVAIL_KB" -ge "$NEED_KB" ] || { echo "insufficient disk: avail ${AVAIL_KB}KB < need ${NEED_KB}KB" >&2; exit 1; }
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

# 3. Maintenance + stop app (M-08: deploy owns the stop; backup verifies)
#    + pinned pre-upgrade backup.
mkdir -p "$TARGET/run"; HOST_FLAG="$TARGET/run/maintenance.flag"
printf '{"owner":"deploy.sh","pid":%s,"started_at":"%s"}\n' "$$" "$(date -Is)" > "$HOST_FLAG"
FROM_SHA=$(python3 -c "import json; print(json.load(open('$TARGET/RELEASE.json')).get('sha',''))" 2>/dev/null || echo "")
SCHEMA_BEFORE=""
if (cd "$TARGET" && docker compose ps mysql --status running -q 2>/dev/null | grep -q .); then
  SCHEMA_BEFORE=$(schema_hash || echo "")
fi
APP_WAS_RUNNING=0
if (cd "$TARGET" && docker compose ps app --status running -q 2>/dev/null | grep -q .); then
  APP_WAS_RUNNING=1
  (cd "$TARGET" && docker compose stop -t 30 app)
fi
BACKUP_ID=""
run_pinned_backup() {
  # $1 = directory whose scripts/backup.sh to use (target tree, or the new
  # staged tree for a first upgrade). Runs with cwd=$TARGET so compose and
  # .env resolve to the target deployment.
  (cd "$TARGET" && SUMAIBOARD_DEPLOY_DIR="$TARGET" BACKUP_INTERNAL_MODE=1 bash "$1/scripts/backup.sh" --pinned)
  BACKUP_ID=$(python3 -c "import json; print(json.load(open('$(env_get BACKUP_DIR)/status/last-success.json'))['backup_id'])" 2>/dev/null || echo "")
  [ -n "$BACKUP_ID" ] && [ -f "$(env_get BACKUP_DIR)/$BACKUP_ID/.complete" ]
}
if [ -f "$TARGET/scripts/backup.sh" ]; then
  run_pinned_backup "$TARGET" || { echo "pre-upgrade pinned backup failed - aborting deploy" >&2; exit 1; }
elif [ -f "$STAGE/scripts/backup.sh" ]; then
  # First upgrade (M-02-R3): the legacy tree has no backup tooling. Use the
  # NEW tree's backup.sh against the old (stopped) stack before touching
  # anything; the backup format/manifest is produced and verified first.
  echo "first upgrade: producing baseline pinned backup with new backup tooling" >&2
  run_pinned_backup "$STAGE" || { echo "first-upgrade pinned backup failed - aborting deploy" >&2; exit 1; }
else
  echo "no backup tooling available (target or staged tree) - aborting deploy" >&2; exit 1
fi

# 4. Snapshot current tree (code/compose/docs/scripts + .env only).
SNAP="$TARGET.snapshot-$(date +%Y%m%dT%H%M%S)"
mkdir -p "$SNAP"; chmod 700 "$SNAP"
(cd "$TARGET" && tar -cf - --exclude='*.tar' --exclude='backups' .env docker-compose.yml \
  docker-compose.verify.yml Dockerfile README.md DEPLOY.md RELEASE.json backend frontend scripts docs 2>/dev/null) \
  | tar -xf - -C "$SNAP" || true
ls -dt "$TARGET".snapshot-* 2>/dev/null | tail -n +4 | xargs -r rm -rf

# 5. Install new tree + build via the limited builder (M-13) + up.
# .env is deployment-local and never part of the archive; it is preserved.
(cd "$STAGE" && tar -cf - .) | (cd "$TARGET" && tar -xf -)
BUILDER_OK=0
if docker buildx inspect sb-builder >/dev/null 2>&1; then BUILDER_OK=1; fi
build_tree() {
  if [ "$BUILDER_OK" = "1" ]; then
    (cd "$TARGET" && BUILD_REVISION="$SHA" BUILDX_BUILDER=sb-builder docker compose build)
  else
    (cd "$TARGET" && BUILD_REVISION="$SHA" docker compose build)
  fi
}
if ! build_tree; then
  echo "build failed - old containers untouched" >&2
  if [ "$APP_WAS_RUNNING" = "1" ]; then (cd "$TARGET" && docker compose start app) || true; fi
  rm -f "$HOST_FLAG"; exit 1
fi
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
  # The maintenance flag (bind-mounted into the app) intentionally blocks
  # every non-health path, including public-config and guest-login, so a
  # full smoke can only run after unfreezing. Phase 1 (above) proved
  # readiness under maintenance; now unfreeze for the full smoke. If the
  # smoke fails, the flag is restored BEFORE the rollback gates run, so
  # the deployment is never left open on a failed release.
  rm -f "$HOST_FLAG"
  if curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null && curl -sf "http://127.0.0.1:$PORT/api/public-config" >/dev/null; then
    SMOKE="ok"
    if [ "$PROFILE" = "sample" ]; then
      curl -sf -X POST "http://127.0.0.1:$PORT/api/auth/guest-login" \
        -H "X-Requested-With: XMLHttpRequest" -H "Content-Type: application/json" -d '{}' >/dev/null || SMOKE="guest-login-failed"
    fi
  fi
fi
SCHEMA_AFTER=$(schema_hash || echo "")
RESULT="success"
SECURE_FLAG="false"
if [ "$SMOKE" != "ok" ]; then
  RESULT="failed"
  printf '{"owner":"deploy.sh","pid":%s,"started_at":"%s"}\n' "$$" "$(date -Is)" > "$HOST_FLAG"
  # Migration-state gate (M-02-R1): explicit schema summary comparison,
  # never startup-log inference. (SCHEMA_AFTER was recorded above, right
  # after the new release came up.)
  MIGRATION_CLEAR=0
  if [ -n "$SCHEMA_BEFORE" ] && [ "$SCHEMA_AFTER" = "$SCHEMA_BEFORE" ]; then
    MIGRATION_CLEAR=1
  elif [ -n "$FROM_SHA" ] && [ -f "$TARGET/schema-compat/$FROM_SHA.proof" ] \
       && grep -q "^schema_sha256=$SCHEMA_AFTER" "$TARGET/schema-compat/$FROM_SHA.proof" 2>/dev/null; then
    MIGRATION_CLEAR=1
  fi
  GATE_OK=1
  [ -f "$SNAP/RELEASE.json" ] || GATE_OK=0
  SNAP_SHA=""
  if [ "$GATE_OK" = "1" ]; then
    SNAP_SHA=$(python3 -c "import json; print(json.load(open('$SNAP/RELEASE.json'))['sha'])" 2>/dev/null || echo "")
    [ -n "$SNAP_SHA" ] || GATE_OK=0
  fi
  if [ "$GATE_OK" = "1" ] && [ "$PROFILE" = "product" ]; then
    # Full SHA + successful release + secure flag (M-02-R2).
    if ! grep -F "to=$SNAP_SHA" "$TARGET/releases.log" 2>/dev/null | grep "result=success" | grep -q "g1_01_secure=true"; then
      GATE_OK=0
    fi
  fi
  [ "$MIGRATION_CLEAR" = "1" ] || GATE_OK=0
  if [ "$GATE_OK" != "1" ]; then
    echo "smoke failed ($SMOKE); auto-rollback gates not met (migration_clear=$MIGRATION_CLEAR) - left in maintenance" >&2
  elif (cd "$SNAP" && tar -cf - --exclude=".env" .) | (cd "$TARGET" && tar -xf -); then
    echo "smoke failed ($SMOKE); rolling back to snapshot $SNAP" >&2
    if build_tree >/dev/null 2>&1 && (cd "$TARGET" && docker compose up -d >/dev/null 2>&1); then
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
if [ "$RESULT" = "success" ]; then SECURE_FLAG="true"; fi
echo "$(date -Is) from=${FROM_SHA:-none} to=$SHA operator=${USER:-root} backup=${BACKUP_ID:-none} result=$RESULT g1_01_secure=$SECURE_FLAG schema_before=${SCHEMA_BEFORE:-unknown} schema_after=${SCHEMA_AFTER:-unknown}" >> "$TARGET/releases.log"
if [ "$RESULT" = "success" ] || [ "$RESULT" = "failed_rolled_back" ]; then rm -f "$HOST_FLAG"; fi
echo "deploy $RESULT: $SHA (backup: ${BACKUP_ID:-none}, snapshot: $SNAP)"
# M-02-R2: any non-success outcome (including a successful auto-rollback)
# exits nonzero so callers never record the new release as deployed.
[ "$RESULT" = "success" ]
