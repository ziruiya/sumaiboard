#!/bin/bash
# SumaiBoard consistent backup (spec 7.1, scheme A: app stopped).
# Usage: backup.sh [--pinned]   (deploy sets BACKUP_INTERNAL_MODE=1)
set -euo pipefail
DEPLOY_DIR="${SUMAIBOARD_DEPLOY_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
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
HOST_FLAG="$DEPLOY_DIR/run/maintenance.flag"

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
  mkdir -p "$(dirname "$HOST_FLAG")"
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
# M-08: the consistency claim "app-stopped" must be TRUE for every backup,
# including deploy-internal ones. In internal mode the outer deploy.sh has
# already stopped the app; either way this script VERIFIES the stopped
# state immediately before dumping and refuses to run against a live app.
if [ "$APP_WAS_RUNNING" = "1" ] && [ "${BACKUP_INTERNAL_MODE:-0}" != "1" ]; then
  docker compose stop -t 30 app
fi
if docker compose ps app --status running -q | grep -q .; then
  echo "app container is still running - refusing to take an 'app-stopped' backup (M-08)" >&2
  write_attempt "failure" "app-not-stopped" "not_attempted" || true
  exit 1
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
  --single-transaction --no-tablespaces --routines --events --triggers --hex-blob "$DB_NAME" > "$TMP_DIR/db.sql"

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
# M-10: these summaries are MANDATORY verification evidence. Any failure to
# generate them aborts the backup - a generation must never be published as
# valid with silently-defaulted evidence (no "|| true", no fallback values).
set -o pipefail
docker compose exec -T mysql mysql -u"$DB_USER" -p"$DB_PASSWORD" -N "$DB_NAME" -e \
  "SELECT CONCAT(TABLE_NAME,'|',COLUMN_NAME,'|',COLUMN_TYPE,'|',IS_NULLABLE,'|',COALESCE(COLUMN_DEFAULT,'')) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME,ORDINAL_POSITION" 2>/dev/null > "$TMP_DIR/schema-summary-src.txt"
docker compose exec -T mysql mysql -u"$DB_USER" -p"$DB_PASSWORD" -N "$DB_NAME" -e \
  "SELECT CONCAT(TABLE_NAME,'|',INDEX_NAME,'|',GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX)) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() GROUP BY TABLE_NAME,INDEX_NAME ORDER BY TABLE_NAME,INDEX_NAME" 2>/dev/null >> "$TMP_DIR/schema-summary-src.txt"
[ -s "$TMP_DIR/schema-summary-src.txt" ] || { echo "schema summary generation failed" >&2; exit 1; }
# Legacy (pre-G1-01) schemas have no company_settings table: record the
# canonical "absent" marker then; when the table exists the query MUST
# succeed (M-10 strictness applies to evidence that should exist).
if [ "$(docker compose exec -T mysql mysql -u"$DB_USER" -p"$DB_PASSWORD" -N "$DB_NAME" -e "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='company_settings'" 2>/dev/null)" = "1" ]; then
  docker compose exec -T mysql mysql -u"$DB_USER" -p"$DB_PASSWORD" -N "$DB_NAME" -e \
    "SELECT COALESCE(JSON_OBJECT('company_name',company_name,'registration_number',registration_number,'account_number',account_number,'logo_file_key',logo_file_key),'null') FROM company_settings WHERE tenant_id=${DEPLOYMENT_TENANT_ID:-1}" 2>/dev/null > "$TMP_DIR/key-company.txt"
else
  echo "absent" > "$TMP_DIR/key-company.txt"
fi
TOTP_COL="totp_enabled"
if [ "$(docker compose exec -T mysql mysql -u"$DB_USER" -p"$DB_PASSWORD" -N "$DB_NAME" -e "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='users' AND COLUMN_NAME='totp_enabled'" 2>/dev/null)" != "1" ]; then TOTP_COL="0"; fi
docker compose exec -T mysql mysql -u"$DB_USER" -p"$DB_PASSWORD" -N "$DB_NAME" -e \
  "SELECT CONCAT(id,'|',employee_code,'|',role,'|',account_status,'|',COALESCE(password_hash,''),'|',$TOTP_COL) FROM users WHERE role IN ('executive','administrator') ORDER BY id" 2>/dev/null > "$TMP_DIR/key-admins.txt"
if [ "$(docker compose exec -T mysql mysql -u"$DB_USER" -p"$DB_PASSWORD" -N "$DB_NAME" -e "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='audit_events'" 2>/dev/null)" = "1" ]; then
  docker compose exec -T mysql mysql -u"$DB_USER" -p"$DB_PASSWORD" -N "$DB_NAME" -e \
    "SELECT CONCAT(COALESCE(MAX(id),0),'|',(SELECT last_hash FROM audit_chain WHERE id=1)) FROM audit_events" 2>/dev/null > "$TMP_DIR/audit-head.txt"
  grep -qE '^[0-9]+\|[0-9a-f]{64}$' "$TMP_DIR/audit-head.txt" || { echo "audit chain head generation failed" >&2; exit 1; }
else
  echo "absent" > "$TMP_DIR/audit-head.txt"
fi
# Per-file storage inventory (M-10): relative path + sha256 for every file
# inside the storage archive, verified file-by-file at restore stage-1.
python3 - "$STORAGE_TAR" "$TMP_DIR/storage-files.json" <<'PYEOF'
import hashlib, json, sys, tarfile
tar_path, out_path = sys.argv[1:3]
entries = []
with tarfile.open(tar_path) as tf:
    for m in tf.getmembers():
        if not m.isfile():
            continue
        if m.name.rsplit("/", 1)[-1] == ".keep":
            continue  # placeholder marker, not data
        h = hashlib.sha256()
        fh = tf.extractfile(m)
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
        entries.append({"path": m.name, "size": m.size, "sha256": h.hexdigest()})
entries.sort(key=lambda e: e["path"])
json.dump(entries, open(out_path, "w"), indent=1, sort_keys=True)
PYEOF
[ -s "$TMP_DIR/storage-files.json" ] || { echo "storage file inventory generation failed" >&2; exit 1; }
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
    "storage_files": json.load(open(os.path.join(tmp, "storage-files.json"))),
}
for k, v in extra.items():
    if v is None:
        raise SystemExit(f"mandatory manifest evidence missing: {k}")
manifest_path = os.path.join(tmp, "manifest.json")
manifest = json.load(open(manifest_path))
manifest.update(extra)
open(manifest_path, "w").write(json.dumps(manifest, indent=2, sort_keys=True))
PYEOF

mv "$TMP_DIR" "$FINAL_DIR"
touch "$FINAL_DIR/.complete"
write_success

# Offsite encrypted copy (spec 7.2 + M-03-R2). The approved transport is:
# UMIDORI writes the encrypted generation into a local staging directory;
# the Muse VM pulls it and a privileged publisher fully verifies and
# publishes it into the read-only archive. backup.sh therefore records
# offsite=pending at staging time and NEVER claims success from transport
# alone. Publication is confirmed out-of-band by the VM puller, which
# writes $BACKUP_DIR/status/offsite-published.json ({backup_id: "published"
# |"failed", ...}); monitor.sh and the rotation gate read that file.
# Legacy OFFSITE_RSYNC_TARGET push is still honoured when explicitly
# configured, but it likewise only reaches "pending" until a publish
# confirmation for this backup_id exists.
OFFSITE_STATE="not_configured"
OFFSITE_STAGING_DIR="${OFFSITE_STAGING_DIR:-}"
if [ -n "${BACKUP_ENCRYPTION_PASSPHRASE_FILE:-}" ] && { [ -n "$OFFSITE_STAGING_DIR" ] || [ -n "${OFFSITE_RSYNC_TARGET:-}" ]; }; then
  tar -cf "$BACKUP_DIR/$BACKUP_ID.tar" -C "$BACKUP_DIR" "$BACKUP_ID"
  if python3 "$(dirname "$0")/backup_crypto.py" encrypt \
      --archive "$BACKUP_DIR/$BACKUP_ID.tar" --manifest "$FINAL_DIR/manifest.json" \
      --out "$BACKUP_DIR/$BACKUP_ID.tar.enc" --passphrase-file "$BACKUP_ENCRYPTION_PASSPHRASE_FILE" \
      --backup-id "$BACKUP_ID"; then
    OFFSITE_STATE="pending"
    if [ -n "$OFFSITE_STAGING_DIR" ]; then
      mkdir -p "$OFFSITE_STAGING_DIR/$DEPLOYMENT_ID"
      cp "$BACKUP_DIR/$BACKUP_ID.tar.enc" "$OFFSITE_STAGING_DIR/$DEPLOYMENT_ID/$BACKUP_ID.tar.enc"
    fi
    if [ -n "${OFFSITE_RSYNC_TARGET:-}" ]; then
      rsync -az "$BACKUP_DIR/$BACKUP_ID.tar.enc" "$OFFSITE_RSYNC_TARGET" || OFFSITE_STATE="failed"
    fi
  else
    OFFSITE_STATE="failed"
  fi
  rm -f "$BACKUP_DIR/$BACKUP_ID.tar"
fi
# A publish confirmation that already exists for this generation (fast
# local publisher setups) upgrades pending -> published.
PUB_FILE="$STATUS_DIR/offsite-published.json"
if [ "$OFFSITE_STATE" = "pending" ] && [ -f "$PUB_FILE" ]; then
  PUB_STATE=$(python3 -c "import json,sys; print(json.load(open('$PUB_FILE')).get('$BACKUP_ID',''))" 2>/dev/null || echo "")
  [ "$PUB_STATE" = "published" ] && OFFSITE_STATE="published"
  [ "$PUB_STATE" = "failed" ] && OFFSITE_STATE="failed"
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

# Rotation (spec 7.1 + M-03-R2): 14 daily + 8 ISO-weekly valid generations;
# pinned kept. Rotation is skipped unless the newest generation's offsite
# state is confirmed "published" (or offsite is not configured at all):
# an unconfirmed (pending) or failed offsite copy must never let older
# generations be deleted on the assumption the newest one is safe offsite.
if [ "$OFFSITE_STATE" = "published" ] || [ "$OFFSITE_STATE" = "not_configured" ]; then
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
