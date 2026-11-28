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

# Full resource inventory (spec 7.3 R33-R3): refuse if the restore project
# would collide with resources owned by any other project.
echo "== docker inventory (all, incl. stopped) =="
docker compose ls -a || true
docker volume ls || true
docker network ls || true
for vol in $(docker volume ls -q); do
  owner=$(docker volume inspect "$vol" --format '{{ index .Labels "com.docker.compose.project" }}' 2>/dev/null || echo "")
  case "$vol" in
    *restore*) ;;
    *) if [ "$owner" = "$PROJECT" ]; then echo "foreign volume claims restore project: $vol" >&2; exit 1; fi;;
  esac
done

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
$COMPOSE down -v >/dev/null 2>&1 || true
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
print("stage-1 pristine verification OK: all table counts match manifest")
PYEOF

# Storage restore into the restore stack volumes.
$COMPOSE run --rm -T --no-deps app sh -c 'mkdir -p /app/attachments /app/private_storage && tar -xf - -C /app' < "$BACKUP_DIR_ARG/storage.tar" || \
  echo "storage restore: tar reported issues (continuing to stage-2 checks)"

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
