#!/bin/bash
# Isolation preflight (spec 6): HARD refuse on overlap. Judged on realpaths,
# credentials, key fingerprints and the RENDERED compose mounts, not on
# name strings.
# Usage: preflight-isolation.sh --env <deployment .env> [--other-env <other .env>]...
#
# Rework (GPT round-2, M-11): deploy.sh now passes --other-env for every
# other SumaiBoard deployment inventoried on the host, and this script
# actually executes the cross-deployment checks for each of them:
# DB credentials, MFA key fingerprint, backup/attachment/referral roots,
# and the rendered compose volume sources of both deployments. When an
# other deployment's rendered mounts cannot be obtained, the check fails
# closed instead of silently passing.
set -euo pipefail
ENV_FILE=""; OTHER_ENVS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --env) ENV_FILE="$2"; shift 2;;
    --other-env) OTHER_ENVS+=("$2"); shift 2;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done
[ -n "$ENV_FILE" ] && [ -f "$ENV_FILE" ] || { echo "--env <file> required" >&2; exit 2; }
fail() { echo "PREFLIGHT REFUSED: $1" >&2; exit 1; }
getv() { grep -E "^$2=" "$1" | tail -1 | cut -d= -f2- || true; }

ATTACH=$(getv "$ENV_FILE" ATTACHMENT_STORAGE_DIR); REFERRAL=$(getv "$ENV_FILE" REFERRAL_STORAGE_DIR); BACKUP=$(getv "$ENV_FILE" BACKUP_DIR)
[ -n "$ATTACH" ] || fail "ATTACHMENT_STORAGE_DIR is empty"
[ -n "$BACKUP" ] || fail "BACKUP_DIR is empty"
python3 - "$ATTACH" "$REFERRAL" "$BACKUP" <<'PYEOF' || fail "storage roots overlap (realpath/parent-child)"
import os, sys
roots = [os.path.realpath(p) for p in sys.argv[1:] if p]
for i, a in enumerate(roots):
    for b in roots[i + 1:]:
        if a == b or a.startswith(b + os.sep) or b.startswith(a + os.sep):
            raise SystemExit(f"overlap: {a} vs {b}")
PYEOF

# Rendered mounts of a deployment dir (host sources, one per line).
rendered_sources() {
  local dir="$1"
  (cd "$dir" && docker compose config --format json 2>/dev/null) | python3 -c "
import json, sys
cfg = json.load(sys.stdin)
srcs = set()
for svc in (cfg.get('services') or {}).values():
    for vol in svc.get('volumes') or []:
        if vol.get('source'):
            srcs.add(vol['source'])
print('\n'.join(sorted(srcs)))
" 2>/dev/null
}

DEPLOY_DIR="$(cd "$(dirname "$ENV_FILE")" && pwd)"
MY_SOURCES=""
if [ -f "$DEPLOY_DIR/docker-compose.yml" ]; then
  MY_SOURCES=$(rendered_sources "$DEPLOY_DIR") || fail "docker compose config does not render for $DEPLOY_DIR"
  [ -n "$MY_SOURCES" ] || fail "could not extract rendered mounts for $DEPLOY_DIR"
  echo "compose renders OK; mounts: $(echo "$MY_SOURCES" | tr '\n' ' ')"
fi

for OTHER_ENV in "${OTHER_ENVS[@]}"; do
  [ -f "$OTHER_ENV" ] || fail "other deployment env not readable: $OTHER_ENV"
  # DB credentials must be independent (spec 6): password differs.
  [ "$(getv "$ENV_FILE" DB_PASSWORD)" != "$(getv "$OTHER_ENV" DB_PASSWORD)" ] || fail "DB password shared with $OTHER_ENV"
  [ "$(getv "$ENV_FILE" MYSQL_ROOT_PASSWORD)" != "$(getv "$OTHER_ENV" MYSQL_ROOT_PASSWORD)" ] || fail "MySQL root password shared with $OTHER_ENV"
  # MFA key fingerprint must differ.
  K1=$(getv "$ENV_FILE" MFA_ENCRYPTION_KEY); K2=$(getv "$OTHER_ENV" MFA_ENCRYPTION_KEY)
  if [ -n "$K1" ] && [ -n "$K2" ]; then
    FP1=$(printf '%s' "$K1" | sha256sum | cut -c1-16); FP2=$(printf '%s' "$K2" | sha256sum | cut -c1-16)
    [ "$FP1" != "$FP2" ] || fail "MFA key fingerprint shared with $OTHER_ENV"
  fi
  # Path roots must not overlap across deployments.
  python3 - "$BACKUP" "$(getv "$OTHER_ENV" BACKUP_DIR)" "$ATTACH" "$(getv "$OTHER_ENV" ATTACHMENT_STORAGE_DIR)" "$REFERRAL" "$(getv "$OTHER_ENV" REFERRAL_STORAGE_DIR)" <<'PYEOF' || fail "cross-deployment path overlap with $OTHER_ENV"
import os, sys
vals = [os.path.realpath(p) if p else "" for p in sys.argv[1:]]
pairs = [(vals[0], vals[1]), (vals[2], vals[3]), (vals[4], vals[5])]
for a, b in pairs:
    if a and b and (a == b or a.startswith(b + os.sep) or b.startswith(a + os.sep)):
        raise SystemExit(f"overlap: {a} vs {b}")
PYEOF
  # Rendered mounts must not share a host source across deployments.
  OTHER_DIR="$(cd "$(dirname "$OTHER_ENV")" && pwd)"
  if [ -f "$OTHER_DIR/docker-compose.yml" ] && [ -n "$MY_SOURCES" ]; then
    OTHER_SOURCES=$(rendered_sources "$OTHER_DIR") || fail "docker compose config does not render for other deployment $OTHER_DIR"
    [ -n "$OTHER_SOURCES" ] || fail "could not extract rendered mounts for other deployment $OTHER_DIR"
    SHARED=$(comm -12 <(echo "$MY_SOURCES" | sort) <(echo "$OTHER_SOURCES" | sort) | grep -v '^$' || true)
    # Named docker volumes are project-scoped; only bind-mount host paths
    # (starting with /) can actually collide across deployments.
    SHARED_BIND=$(echo "$SHARED" | grep '^/' || true)
    [ -z "$SHARED_BIND" ] || fail "rendered bind-mount source shared with $OTHER_DIR: $SHARED_BIND"
  fi
  echo "cross-deployment checks OK vs $OTHER_ENV"
done
echo "preflight-isolation: OK"
