#!/bin/bash
# Restore drill wrapper (spec 7.3): restore.sh + post-restore verification.
# Usage: verify-restore.sh --backup <dir> [--project sumaiboard-restore]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
"$SCRIPT_DIR/restore.sh" "$@"
PORT="${RESTORE_PORT:-18190}"
echo "== post-restore checks on port $PORT =="
curl -sf "http://127.0.0.1:$PORT/api/health" | head -c 300; echo
curl -sf "http://127.0.0.1:$PORT/api/public-config" | head -c 300; echo
echo "verify-restore: restore stack is up; run the business regression (F03 for"
echo "sample backups, admin login + MFA decrypt for product backups) against"
echo "http://127.0.0.1:$PORT and record the results in the acceptance record."
