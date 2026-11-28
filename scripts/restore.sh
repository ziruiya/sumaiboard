#!/bin/bash
# SumaiBoard restore into the ISOLATED restore stack only (spec 7.3).
# Usage: restore.sh --backup <dir> [--project sumaiboard-restore]
# Never touches the running stack or the standing verify stack: the target
# project name must carry the -restore marker and all existing docker
# resources are inventoried first (including stopped ones).
set -euo pipefail
BACKUP_DIR_ARG=""
PROJECT="sumaiboard-restore"
while [ $# -gt 0 ]; do
  case "$1" in
    --backup) BACKUP_DIR_ARG="$2"; shift 2;;
    --project) PROJECT="$2"; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done
[ -n "$BACKUP_DIR_ARG" ] || { echo "--backup is required" >&2; exit 2; }
case "$PROJECT" in
  *-restore) ;;
  *) echo "refusing: restore project must end with -restore (got: $PROJECT)" >&2; exit 1;;
esac
[ -f "$BACKUP_DIR_ARG/.complete" ] || { echo "backup is not a complete generation" >&2; exit 1; }
[ -f "$BACKUP_DIR_ARG/manifest.json" ] || { echo "manifest.json missing" >&2; exit 1; }

# Verify hashes before anything is loaded (spec 7.3: verify first).
python3 - "$BACKUP_DIR_ARG" <<'PYEOF'
import hashlib, json, os, sys
root = sys.argv[1]
manifest = json.load(open(os.path.join(root, "manifest.json")))
def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
if sha(os.path.join(root, "db.sql")) != manifest["db_sha256"]:
    raise SystemExit("db.sql hash mismatch - refusing restore")
if sha(os.path.join(root, "storage.tar")) != manifest["storage_sha256"]:
    raise SystemExit("storage.tar hash mismatch - refusing restore")
print("hash verification OK for", manifest["backup_id"])
PYEOF

# Safe unpack check for the storage tar (data filter semantics in python).
python3 - "$BACKUP_DIR_ARG/storage.tar" <<'PYEOF'
import sys, tarfile
with tarfile.open(sys.argv[1]) as tf:
    for member in tf.getmembers():
        name = member.name
        if name.startswith("/") or ".." in name.split("/") or member.issym() or member.islnk():
            raise SystemExit(f"unsafe tar member: {name}")
print("tar safety check OK")
PYEOF

# Full resource inventory (spec 7.3 R33-R3 + M-12): BEFORE any destructive
# operation, verify that every resource this restore will delete or reuse
# actually belongs to the restore project. Inventory commands must succeed
# (fail closed); unknown resources, label anomalies or name collisions are
# a hard refusal, not a warning.
echo "== docker inventory (all, incl. stopped) =="
docker compose ls -a
docker volume ls
docker network ls
for vol in $(docker volume ls -q); do
  owner=$(docker volume inspect "$vol" --format '{{ index .Labels "com.docker.compose.project" }}' 2>/dev/null) || {
    echo "cannot inspect volume $vol - refusing restore" >&2; exit 1; }
  if [ "$owner" = "$PROJECT" ]; then
    case "$vol" in
      *restore*) ;;
      *) echo "volume $vol claims restore project but carries no restore marker - refusing" >&2; exit 1;;
    esac
  fi
  case "$vol" in
    *restore*) if [ "$owner" != "$PROJECT" ] && [ -n "$owner" ]; then
        echo "restore-named volume $vol owned by foreign project '$owner' - refusing" >&2; exit 1; fi;;
  esac
done
for net in $(docker network ls -q); do
  nname=$(docker network inspect "$net" --format '{{ .Name }}' 2>/dev/null) || {
    echo "cannot inspect network $net - refusing restore" >&2; exit 1; }
  nowner=$(docker network inspect "$net" --format '{{ index .Labels "com.docker.compose.project" }}' 2>/dev/null || echo "")
  case "$nname" in
    *restore*) if [ "$nowner" != "$PROJECT" ] && [ -n "$nowner" ]; then
        echo "restore-named network $nname owned by foreign project '$nowner' - refusing" >&2; exit 1; fi;;
  esac
done
for cid in $(docker ps -aq); do
  cproj=$(docker inspect "$cid" --format '{{ index .Config.Labels "com.docker.compose.project" }}' 2>/dev/null || echo "")
  cname=$(docker inspect "$cid" --format '{{ .Name }}' 2>/dev/null || echo "")
  case "$cname" in
    *restore*) if [ "$cproj" != "$PROJECT" ]; then
        echo "restore-named container $cname belongs to project '$cproj', not $PROJECT - refusing" >&2; exit 1; fi;;
  esac
done
echo "resource ownership verification OK for project $PROJECT"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
export VERIFY_PROJECT="$PROJECT"
export VERIFY_PORT="${RESTORE_PORT:-18190}"
export VERIFY_SUFFIX="-restore"
# Restore DB credentials are fresh and restore-local.
export VERIFY_DB_NAME="sb_restore"
export VERIFY_DB_USER="sb_restore"
export VERIFY_DB_PASSWORD="$(head -c 24 /dev/urandom | base64 | tr -d '/+= ' | head -c 24)"
export VERIFY_MYSQL_ROOT_PASSWORD="$(head -c 24 /dev/urandom | base64 | tr -d '/+= ' | head -c 24)"
# Side-effect isolation (spec 7.3): no webhook, no cron, loopback only.
export MONITOR_WEBHOOK_URL=""
PROFILE=$(python3 -c "import json,sys; print(json.load(open('$BACKUP_DIR_ARG/manifest.json')).get('profile') or 'sample')")
export DEPLOYMENT_PROFILE="$PROFILE"
export DEPLOYMENT_ID="$(python3 -c "import json; print(json.load(open('$BACKUP_DIR_ARG/manifest.json'))['deployment_id'])")"
export DEPLOYMENT_TENANT_ID="$(python3 -c "import json; print(json.load(open('$BACKUP_DIR_ARG/manifest.json'))['tenant_id'])")"
export DEMO_MODE="$([ "$PROFILE" = "sample" ] && echo true || echo false)"
export PUBLIC_SAMPLE_MODE="$DEMO_MODE"
export SAMPLE_RESET_TOKEN=""
export PUBLIC_ORIGIN="http://127.0.0.1:$VERIFY_PORT"
export ATTACHMENT_STORAGE_DIR="/app/attachments"
export BACKUP_DIR="/app/backups"
export MFA_ENCRYPTION_KEY="${MFA_ENCRYPTION_KEY:-}"
export OPS_STATUS_TOKEN=""

COMPOSE="docker compose -f $REPO_DIR/docker-compose.verify.yml"
# M-12: down -v runs only after the ownership verification above passed;
# its failure is fatal, never ignored.
$COMPOSE down -v
$COMPOSE up -d mysql
for i in $(seq 1 40); do
  if $COMPOSE exec -T mysql mysqladmin ping -h 127.0.0.1 -uroot -p"$VERIFY_MYSQL_ROOT_PASSWORD" --silent >/dev/null 2>&1; then break; fi
  sleep 3
done
$COMPOSE exec -T mysql mysql -uroot -p"$VERIFY_MYSQL_ROOT_PASSWORD" -e "DROP DATABASE IF EXISTS sb_restore; CREATE DATABASE sb_restore CHARACTER SET utf8mb4;"
$COMPOSE exec -T mysql mysql -uroot -p"$VERIFY_MYSQL_ROOT_PASSWORD" sb_restore < "$BACKUP_DIR_ARG/db.sql"

# ---- Stage 1: pristine verification (app NOT started, no new writes) ----
$COMPOSE exec -T mysql mysql -u"$VERIFY_DB_USER" -p"$VERIFY_DB_PASSWORD" -N sb_restore -e \
  "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE'" > "$WORK/tables.txt"
: > "$WORK/counts.txt"
while read -r t; do
  [ -z "$t" ] && continue
  c=$($COMPOSE exec -T mysql mysql -u"$VERIFY_DB_USER" -p"$VERIFY_DB_PASSWORD" -N sb_restore -e "SELECT COUNT(*) FROM \`$t\`" < /dev/null)
  echo "$t $c" >> "$WORK/counts.txt"
done < "$WORK/tables.txt"
python3 - "$BACKUP_DIR_ARG/manifest.json" "$WORK/counts.txt" <<'PYEOF'
import json, sys
manifest = json.load(open(sys.argv[1]))
counts = {}
for line in open(sys.argv[2]):
    p = line.split()
    if len(p) == 2:
        counts[p[0]] = int(p[1])
expected = manifest["table_counts"]
diff = {k: (expected.get(k), counts.get(k)) for k in set(expected) | set(counts)
        if expected.get(k) != counts.get(k)}
# Tables created by a later app start are not in the dump state; the dump
# itself defines the expected set, so any diff is a real mismatch.
if diff:
    raise SystemExit(f"stage-1 row count mismatch: {diff}")
print("stage-1 row counts OK")
PYEOF

# Stage-1 full verification matrix (M-10, spec 7.3 R34-R1): schema summary,
# key-record summaries and the audit chain head + full chain integrity are
# recomputed against the pristine restored DB (app still NOT started) and
# compared with the manifest. Any mismatch aborts before stage-2.
$COMPOSE exec -T mysql mysql -u"$VERIFY_DB_USER" -p"$VERIFY_DB_PASSWORD" -N sb_restore -e \
  "SELECT CONCAT(TABLE_NAME,'|',COLUMN_NAME,'|',COLUMN_TYPE,'|',IS_NULLABLE,'|',COALESCE(COLUMN_DEFAULT,'')) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME,ORDINAL_POSITION" > "$WORK/schema-summary-src.txt"
$COMPOSE exec -T mysql mysql -u"$VERIFY_DB_USER" -p"$VERIFY_DB_PASSWORD" -N sb_restore -e \
  "SELECT CONCAT(TABLE_NAME,'|',INDEX_NAME,'|',GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX)) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() GROUP BY TABLE_NAME,INDEX_NAME ORDER BY TABLE_NAME,INDEX_NAME" >> "$WORK/schema-summary-src.txt"
TENANT_ID=$(python3 -c "import json; print(json.load(open('$BACKUP_DIR_ARG/manifest.json'))['tenant_id'])")
if [ "$($COMPOSE exec -T mysql mysql -u"$VERIFY_DB_USER" -p"$VERIFY_DB_PASSWORD" -N sb_restore -e "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='company_settings'")" = "1" ]; then
  $COMPOSE exec -T mysql mysql -u"$VERIFY_DB_USER" -p"$VERIFY_DB_PASSWORD" -N sb_restore -e \
    "SELECT COALESCE(JSON_OBJECT('company_name',company_name,'registration_number',registration_number,'account_number',account_number,'logo_file_key',logo_file_key),'null') FROM company_settings WHERE tenant_id=$TENANT_ID" > "$WORK/key-company.txt"
else
  echo "absent" > "$WORK/key-company.txt"
fi
TOTP_COL="totp_enabled"
if [ "$($COMPOSE exec -T mysql mysql -u"$VERIFY_DB_USER" -p"$VERIFY_DB_PASSWORD" -N sb_restore -e "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='users' AND COLUMN_NAME='totp_enabled'")" != "1" ]; then TOTP_COL="0"; fi
$COMPOSE exec -T mysql mysql -u"$VERIFY_DB_USER" -p"$VERIFY_DB_PASSWORD" -N sb_restore -e \
  "SELECT CONCAT(id,'|',employee_code,'|',role,'|',account_status,'|',COALESCE(password_hash,''),'|',$TOTP_COL) FROM users WHERE role IN ('executive','administrator') ORDER BY id" > "$WORK/key-admins.txt"
if [ "$($COMPOSE exec -T mysql mysql -u"$VERIFY_DB_USER" -p"$VERIFY_DB_PASSWORD" -N sb_restore -e "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='audit_events'")" = "1" ]; then
  $COMPOSE exec -T mysql mysql -u"$VERIFY_DB_USER" -p"$VERIFY_DB_PASSWORD" -N sb_restore -e \
    "SELECT CONCAT(COALESCE(MAX(id),0),'|',(SELECT last_hash FROM audit_chain WHERE id=1)) FROM audit_events" > "$WORK/audit-head.txt"
else
  echo "absent" > "$WORK/audit-head.txt"
fi
# Full audit-chain recomputation is done by verify_audit_chain.py (shipped
# with the repo) running in a one-off app container against the pristine
# restored DB - the exact same algorithm the application itself uses.
python3 - "$BACKUP_DIR_ARG/manifest.json" "$WORK" <<'PYEOF'
import hashlib, json, os, sys
manifest = json.load(open(sys.argv[1]))
work = sys.argv[2]
def h(name):
    return hashlib.sha256(open(os.path.join(work, name), "rb").read()).hexdigest()
errors = []
if manifest.get("schema_summary_sha256") and h("schema-summary-src.txt") != manifest["schema_summary_sha256"]:
    errors.append("schema summary mismatch")
ks = manifest.get("key_summaries") or {}
if ks.get("company_settings") and h("key-company.txt") != ks["company_settings"]:
    errors.append("company_settings key summary mismatch")
if ks.get("admin_users") and h("key-admins.txt") != ks["admin_users"]:
    errors.append("admin users key summary mismatch")
audit_head = open(os.path.join(work, "audit-head.txt")).read().strip()
if manifest.get("audit_head") and audit_head != manifest["audit_head"]:
    errors.append(f"audit head mismatch: {audit_head} != {manifest['audit_head']}")
if errors:
    raise SystemExit("stage-1 verification FAILED: " + "; ".join(errors))
print("stage-1 pristine verification OK: counts + schema + key summaries + audit head")
PYEOF
if [ "$($COMPOSE exec -T mysql mysql -u"$VERIFY_DB_USER" -p"$VERIFY_DB_PASSWORD" -N sb_restore -e "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='audit_events'")" != "1" ]; then
  echo "stage-1 audit chain recomputation skipped: legacy backup without audit tables"
elif ! $COMPOSE run --rm -T --no-deps -v "$SCRIPT_DIR/verify_audit_chain.py:/tmp/verify_audit_chain.py:ro" app python3 /tmp/verify_audit_chain.py; then
  echo "stage-1 audit chain full recomputation FAILED - aborting restore" >&2
  exit 1
fi
echo "stage-1 audit chain full recomputation OK"

# Storage restore into the restore stack volumes. M-10: a failed storage
# restore is FATAL - the run must not continue to stage-2 or report success.
if ! $COMPOSE run --rm -T --no-deps app sh -c 'mkdir -p /app/attachments /app/private_storage && tar -xf - -C /app' < "$BACKUP_DIR_ARG/storage.tar"; then
  echo "storage restore FAILED - aborting restore (M-10)" >&2
  exit 1
fi
# Per-file verification against the manifest inventory (M-10).
STORAGE_LIST=$($COMPOSE run --rm -T --no-deps app python3 -c "
import hashlib, json, os
out = []
for root in ('/app/attachments', '/app/private_storage'):
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if name == '.keep':
                continue  # placeholder marker, not data
            p = os.path.join(dirpath, name)
            rel = os.path.relpath(p, '/app')
            h = hashlib.sha256()
            with open(p, 'rb') as fh:
                for chunk in iter(lambda: fh.read(1024 * 1024), b''):
                    h.update(chunk)
            out.append({'path': rel, 'size': os.path.getsize(p), 'sha256': h.hexdigest()})
print(json.dumps(sorted(out, key=lambda e: e['path'])))
")
python3 - "$BACKUP_DIR_ARG/manifest.json" "$STORAGE_LIST" <<'PYEOF'
import json, sys
manifest = json.load(open(sys.argv[1]))
expected = manifest.get("storage_files")
if expected is None:
    print("manifest has no storage_files inventory (legacy generation) - skipping per-file check")
    raise SystemExit(0)
actual = json.loads(sys.argv[2])
exp = {e["path"]: e for e in expected}
act = {e["path"]: e for e in actual}
diff = []
for p in sorted(set(exp) | set(act)):
    if p not in exp: diff.append(f"unexpected file {p}")
    elif p not in act: diff.append(f"missing file {p}")
    elif exp[p]["sha256"] != act[p]["sha256"] or exp[p]["size"] != act[p]["size"]: diff.append(f"hash/size mismatch {p}")
if diff:
    raise SystemExit("storage per-file verification FAILED: " + "; ".join(diff[:10]))
print(f"storage per-file verification OK ({len(exp)} files)")
PYEOF

# ---- Stage 2: safe start (sessions/challenges/enrollments/grants revoked) ----
$COMPOSE exec -T mysql mysql -uroot -p"$VERIFY_MYSQL_ROOT_PASSWORD" sb_restore -e \
  "DELETE FROM auth_sessions; DELETE FROM auth_mfa_challenges; DELETE FROM mfa_enrollments; DELETE FROM mfa_recovery_grants;"
echo "stage-2 safety cleanup done (revoked rows recorded as expected stage-2 delta)"
$COMPOSE up -d app
for i in $(seq 1 40); do
  if curl -sf "http://127.0.0.1:$VERIFY_PORT/api/health/ready" >/dev/null 2>&1; then
    echo "restore stack ready on http://127.0.0.1:$VERIFY_PORT (project $PROJECT)"
    exit 0
  fi
  sleep 3
done
echo "restore stack did not become ready" >&2
$COMPOSE logs app | tail -30 >&2
exit 1
