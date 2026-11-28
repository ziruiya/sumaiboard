#!/bin/bash
# SumaiBoard consistent backup (spec 7.1, scheme A: app stopped).
# Usage: backup.sh [--pinned]   (deploy sets BACKUP_INTERNAL_MODE=1)
set -euo pipefail
DEPLOY_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DEPLOY_DIR"
set -a; [ -f .env ] && . ./.env; set +a
: "${DEPLOYMENT_ID:?DEPLOYMENT_ID required}"
: "${BACKUP_DIR:?BACKUP_DIR required}"
PINNED=0; [ "${1:-}" = "--pinned" ] && PINNED=1
LOCK_FILE="/run/lock/sumaiboard-${DEPLOYMENT_ID}.lock"
STATUS_DIR="$(dirname "${BACKUP_STATUS_FILE:-$BACKUP_DIR/status/last-success.json}")"
mkdir -p "$BACKUP_DIR" "$STATUS_DIR" "$(dirname "$LOCK_FILE")"
TS="$(date +%Y%m%dT%H%M%S)"
BACKUP_ID="backup-${TS}"
TMP_DIR="$BACKUP_DIR/.tmp-${TS}"
FINAL_DIR="$BACKUP_DIR/$BACKUP_ID"
STARTED_EPOCH=$(date +%s)
APP_WAS_RUNNING=0
MAINTENANCE_OWNED=0
FLAG_FILE="${MAINTENANCE_FLAG_FILE:-/app/run/maintenance.flag}"
# Maintenance flag lives inside the app container path namespace; host-side we
# track it through a host mirror next to the deployment dir.
HOST_FLAG="$DEPLOY_DIR/.maintenance.flag"

write_attempt() {
  local result="$1" stage="$2" offsite="$3"
  python3 - "$STATUS_DIR/last-attempt.json" "$result" "$stage" "$offsite" "$BACKUP_ID" <<'PYEOF'
import json, sys, datetime
path, result, stage, offsite, bid = sys.argv[1:6]
data = {"result": result, "stage": stage, "offsite": offsite, "backup_id": bid,
        "at": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}
tmp = path + ".tmp"
open(tmp, "w").write(json.dumps(data))
import os; os.replace(tmp, path)
PYEOF
}
write_success() {
  python3 - "$STATUS_DIR/last-success.json" "$BACKUP_ID" <<'PYEOF'
import json, sys, datetime, os
path, bid = sys.argv[1:3]
data = {"backup_id": bid, "integrity": "ok", "offsite": "pending",
        "completed_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}
tmp = path + ".tmp"
open(tmp, "w").write(json.dumps(data))
os.replace(tmp, path)
PYEOF
}
cleanup_on_error() {
  local rc=$?
  if [ $rc -ne 0 ]; then
    rm -rf "$TMP_DIR"
    write_attempt "failure" "backup" "not_attempted" || true
    # Conditional restore (spec 7.1 2b): only restart an app this run stopped.
    if [ "$APP_WAS_RUNNING" = "1" ] && [ "${BACKUP_INTERNAL_MODE:-0}" != "1" ]; then
      docker compose start app >/dev/null 2>&1 || true
    fi
    if [ "$MAINTENANCE_OWNED" = "1" ]; then rm -f "$HOST_FLAG"; fi
  fi
  exit $rc
}
trap cleanup_on_error EXIT

if [ "${BACKUP_INTERNAL_MODE:-0}" != "1" ]; then
  exec 9>"$LOCK_FILE"
  flock -w 600 9 || { echo "could not acquire deployment lock" >&2; exit 1; }
  printf '{"owner":"backup.sh","pid":%s,"started_at":"%s"}\n' "$$" "$(date -Is)" > "$HOST_FLAG"
  MAINTENANCE_OWNED=1
fi

# Writer registry check (spec 7.1 2b): no ENABLED MySQL events allowed.
EVENTS_ON=$(docker compose exec -T mysql mysql -u"$DB_USER" -p"$DB_PASSWORD" -N "$DB_NAME" -e \
  "SELECT COUNT(*) FROM information_schema.EVENTS WHERE EVENT_SCHEMA=DATABASE() AND STATUS='ENABLED'" 2>/dev/null || echo "query_failed")
if [ "$EVENTS_ON" != "0" ]; then
  echo "ENABLED MySQL events present (or check failed): $EVENTS_ON - aborting backup" >&2
  write_attempt "failure" "events-check" "not_attempted" || true
  exit 1
fi

mkdir -p "$TMP_DIR"
if docker compose ps app --status running -q | grep -q .; then APP_WAS_RUNNING=1; fi
STOP_START=$(date +%s)
if [ "${BACKUP_INTERNAL_MODE:-0}" != "1" ] && [ "$APP_WAS_RUNNING" = "1" ]; then
  docker compose stop -t 30 app
fi
MAINTENANCE_SECONDS=$(( $(date +%s) - STOP_START ))

# Single-session table counts, then dump, same quiesced state.
docker compose exec -T mysql mysql -u"$DB_USER" -p"$DB_PASSWORD" -N "$DB_NAME" -e \
  "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE'" 2>/dev/null \
  > "$TMP_DIR/tables.txt"
: > "$TMP_DIR/counts.txt"
while read -r t; do
  [ -z "$t" ] && continue
  c=$(docker compose exec -T mysql mysql -u"$DB_USER" -p"$DB_PASSWORD" -N "$DB_NAME" -e "SELECT COUNT(*) FROM \`$t\`" 2>/dev/null < /dev/null)
  echo "$t $c" >> "$TMP_DIR/counts.txt"
done < "$TMP_DIR/tables.txt"

docker compose exec -T mysql mysqldump -u"$DB_USER" -p"$DB_PASSWORD" \
  --single-transaction --routines --events --triggers --hex-blob "$DB_NAME" > "$TMP_DIR/db.sql"

# Storage archive (attachments + referral documents) via a throwaway
# container on the app service (works while the app container is stopped).
STORAGE_TAR="$TMP_DIR/storage.tar"
if ! docker compose run --rm -T --no-deps app sh -c \
  'mkdir -p /app/attachments && tar -cf - -C /app attachments private_storage' > "$STORAGE_TAR" \
  || [ ! -s "$STORAGE_TAR" ]; then
  echo "storage archive could not be produced" >&2
  write_attempt "failure" "storage" "not_attempted" || true
  exit 1
fi

DB_SHA=$(sha256sum "$TMP_DIR/db.sql" | cut -d' ' -f1)
ST_SHA=$(sha256sum "$STORAGE_TAR" | cut -d' ' -f1)

# Manifest with key-record summaries, schema summary, audit chain head.
python3 - "$TMP_DIR" "$BACKUP_ID" "$PINNED" "$MAINTENANCE_SECONDS" "$DB_SHA" "$ST_SHA" <<'PYEOF'
import json, sys, hashlib, os, datetime
tmp, bid, pinned, maint, db_sha, st_sha = sys.argv[1:7]
counts = {}
for line in open(os.path.join(tmp, "counts.txt")):
    parts = line.split()
    if len(parts) == 2:
        counts[parts[0]] = int(parts[1])
manifest = {
    "backup_id": bid,
    "deployment_id": os.environ.get("DEPLOYMENT_ID"),
    "profile": os.environ.get("DEPLOYMENT_PROFILE"),
    "tenant_id": int(os.environ.get("DEPLOYMENT_TENANT_ID", "0") or 0),
    "app_version": os.environ.get("APP_VERSION", ""),
    "build_revision": os.environ.get("BUILD_REVISION", ""),
    "created_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
    "consistency": "app-stopped",
    "maintenance_seconds": int(maint),
    "table_counts": counts,
    "db_sha256": db_sha,
    "storage_sha256": st_sha,
    "pinned": pinned == "1",
}
open(os.path.join(tmp, "manifest.json"), "w").write(json.dumps(manifest, indent=2, sort_keys=True))
PYEOF
# Key-record summaries, schema summary and audit chain head (spec 7.1 item 4).
docker compose exec -T mysql mysql -u"$DB_USER" -p"$DB_PASSWORD" -N "$DB_NAME" -e \
  "SELECT CONCAT(TABLE_NAME,'|',COLUMN_NAME,'|',COLUMN_TYPE,'|',IS_NULLABLE,'|',COALESCE(COLUMN_DEFAULT,'')) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME,ORDINAL_POSITION" 2>/dev/null > "$TMP_DIR/schema-summary-src.txt" || true
docker compose exec -T mysql mysql -u"$DB_USER" -p"$DB_PASSWORD" -N "$DB_NAME" -e \
  "SELECT CONCAT(TABLE_NAME,'|',INDEX_NAME,'|',GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX)) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() GROUP BY TABLE_NAME,INDEX_NAME ORDER BY TABLE_NAME,INDEX_NAME" 2>/dev/null >> "$TMP_DIR/schema-summary-src.txt" || true
docker compose exec -T mysql mysql -u"$DB_USER" -p"$DB_PASSWORD" -N "$DB_NAME" -e \
  "SELECT COALESCE(JSON_OBJECT('company_name',company_name,'registration_number',registration_number,'account_number',account_number,'logo_file_key',logo_file_key),'null') FROM company_settings WHERE tenant_id=${DEPLOYMENT_TENANT_ID:-1}" 2>/dev/null > "$TMP_DIR/key-company.txt" || echo "null" > "$TMP_DIR/key-company.txt"
docker compose exec -T mysql mysql -u"$DB_USER" -p"$DB_PASSWORD" -N "$DB_NAME" -e \
  "SELECT CONCAT(id,'|',employee_code,'|',role,'|',account_status,'|',COALESCE(password_hash,''),'|',totp_enabled) FROM users WHERE role IN ('executive','administrator') ORDER BY id" 2>/dev/null > "$TMP_DIR/key-admins.txt" || true
docker compose exec -T mysql mysql -u"$DB_USER" -p"$DB_PASSWORD" -N "$DB_NAME" -e \
  "SELECT CONCAT(COALESCE(MAX(id),0),'|',(SELECT last_hash FROM audit_chain WHERE id=1)) FROM audit_events" 2>/dev/null > "$TMP_DIR/audit-head.txt" || echo "0|" > "$TMP_DIR/audit-head.txt"
python3 - "$TMP_DIR" <<'PYEOF'
import hashlib, json, os, sys
tmp = sys.argv[1]
def h(path):
    p = os.path.join(tmp, path)
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None
extra = {
    "schema_summary_sha256": h("schema-summary-src.txt"),
    "key_summaries": {
        "company_settings": h("key-company.txt"),
        "admin_users": h("key-admins.txt"),
    },
    "audit_head": open(os.path.join(tmp, "audit-head.txt")).read().strip() if os.path.exists(os.path.join(tmp, "audit-head.txt")) else None,
}
manifest_path = os.path.join(tmp, "manifest.json")
manifest = json.load(open(manifest_path))
manifest.update(extra)
open(manifest_path, "w").write(json.dumps(manifest, indent=2, sort_keys=True))
PYEOF

mv "$TMP_DIR" "$FINAL_DIR"
touch "$FINAL_DIR/.complete"
write_success

# Offsite encrypted copy (spec 7.2).
OFFSITE_STATE="not_configured"
if [ -n "${OFFSITE_RSYNC_TARGET:-}" ] && [ -n "${BACKUP_ENCRYPTION_PASSPHRASE_FILE:-}" ]; then
  tar -cf "$BACKUP_DIR/$BACKUP_ID.tar" -C "$BACKUP_DIR" "$BACKUP_ID"
  if python3 "$(dirname "$0")/backup_crypto.py" encrypt \
      --archive "$BACKUP_DIR/$BACKUP_ID.tar" --manifest "$FINAL_DIR/manifest.json" \
      --out "$BACKUP_DIR/$BACKUP_ID.tar.enc" --passphrase-file "$BACKUP_ENCRYPTION_PASSPHRASE_FILE" \
      --backup-id "$BACKUP_ID" \
     && rsync -az "$BACKUP_DIR/$BACKUP_ID.tar.enc" "$OFFSITE_RSYNC_TARGET"; then
    OFFSITE_STATE="ok"
  else
    OFFSITE_STATE="failed"
  fi
  rm -f "$BACKUP_DIR/$BACKUP_ID.tar"
fi
python3 - "$STATUS_DIR/last-success.json" "$OFFSITE_STATE" <<'PYEOF'
import json, sys, os
path, offsite = sys.argv[1:3]
data = json.load(open(path)); data["offsite"] = offsite
tmp = path + ".tmp"; open(tmp, "w").write(json.dumps(data)); os.replace(tmp, path)
PYEOF
write_attempt "success" "complete" "$OFFSITE_STATE"

# Conditional app restore (only what this run stopped; never in internal mode).
if [ "${BACKUP_INTERNAL_MODE:-0}" != "1" ]; then
  if [ "$APP_WAS_RUNNING" = "1" ]; then docker compose start app; fi
  rm -f "$HOST_FLAG"
fi

# Rotation (spec 7.1): 14 daily + 8 ISO-weekly valid generations; pinned kept;
# skip rotation entirely when the newest backup or its offsite copy failed.
if [ "$OFFSITE_STATE" != "failed" ]; then
  python3 - "$BACKUP_DIR" <<'PYEOF'
import os, sys, datetime, shutil
root = sys.argv[1]
gens = []
for name in sorted(os.listdir(root)):
    path = os.path.join(root, name)
    if name.startswith("backup-") and os.path.isdir(path) and os.path.exists(os.path.join(path, ".complete")):
        import json
        try:
            pinned = json.load(open(os.path.join(path, "manifest.json"))).get("pinned")
        except Exception:
            pinned = False
        gens.append((name, path, pinned))
keep = set()
daily = gens[-14:]
keep.update(g[0] for g in daily)
weeks = {}
for g in gens:
    try:
        dt = datetime.datetime.strptime(g[0].replace("backup-", ""), "%Y%m%dT%H%M%S")
        weeks.setdefault(dt.isocalendar()[:2], g)
    except Exception:
        pass
keep.update(g[0] for g in list(weeks.values())[-8:])
for name, path, pinned in gens:
    if name not in keep and not pinned:
        real = os.path.realpath(path)
        if real.startswith(os.path.realpath(root) + os.sep):
            shutil.rmtree(real)
PYEOF
fi
echo "backup complete: $BACKUP_ID (offsite=$OFFSITE_STATE)"
trap - EXIT
