#!/bin/bash
# Isolation preflight (spec 6): HARD refuse on overlap. Judged on realpaths
# and rendered compose mounts, not on name strings.
# Usage: preflight-isolation.sh --env <deployment .env> [--other-env <other .env>]
set -euo pipefail
ENV_FILE=""; OTHER_ENV=""
while [ $# -gt 0 ]; do
  case "$1" in
    --env) ENV_FILE="$2"; shift 2;;
    --other-env) OTHER_ENV="$2"; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done
[ -n "$ENV_FILE" ] && [ -f "$ENV_FILE" ] || { echo "--env <file> required" >&2; exit 2; }
get() { grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- || true; }
geto() { grep -E "^$1=" "$OTHER_ENV" | tail -1 | cut -d= -f2- || true; }
fail() { echo "PREFLIGHT REFUSED: $1" >&2; exit 1; }

ATTACH=$(get ATTACHMENT_STORAGE_DIR); REFERRAL=$(get REFERRAL_STORAGE_DIR); BACKUP=$(get BACKUP_DIR)
[ -n "$ATTACH" ] || fail "ATTACHMENT_STORAGE_DIR is empty"
[ -n "$BACKUP" ] || fail "BACKUP_DIR is empty"
python3 - "$ATTACH" "$REFERRAL" "$BACKUP" <<'PYEOF' || fail "storage roots overlap (realpath/parent-child)"
import os, sys
roots = [os.path.realpath(p) for p in sys.argv[1:] if p]
for i, a in enumerate(roots):
    for b in roots[i + 1:]:
        if a == b or a.startswith(b + os.sep) or b.startswith(a + os.sep):
            raise SystemExit(f"overlap: {a} vs {b}")
# backup root must not sit inside any storage root
PYEOF

DEPLOY_DIR="$(cd "$(dirname "$ENV_FILE")" && pwd)"
if [ -f "$DEPLOY_DIR/docker-compose.yml" ]; then
  (cd "$DEPLOY_DIR" && docker compose config >/dev/null) || fail "docker compose config does not render"
  echo "compose renders OK"
fi

if [ -n "$OTHER_ENV" ] && [ -f "$OTHER_ENV" ]; then
  # Credentials must be independent (spec 6): DB password differs.
  [ "$(get DB_PASSWORD)" != "$(geto DB_PASSWORD)" ] || fail "DB password shared with the other deployment"
  # MFA key fingerprint must differ.
  FP1=$(printf '%s' "$(get MFA_ENCRYPTION_KEY)" | sha256sum | cut -c1-16)
  FP2=$(printf '%s' "$(geto MFA_ENCRYPTION_KEY)" | sha256sum | cut -c1-16)
  if [ -n "$(get MFA_ENCRYPTION_KEY)" ] && [ "$FP1" = "$FP2" ]; then
    fail "MFA key fingerprint shared with the other deployment"
  fi
  # Backup roots must differ.
  [ "$(python3 -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "$BACKUP")" != \
     "$(python3 -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "$(geto BACKUP_DIR)")" ] \
    || fail "BACKUP_DIR shared with the other deployment"
fi
echo "preflight-isolation: OK"
