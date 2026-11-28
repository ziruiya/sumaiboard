#!/bin/bash
# MFA emergency reset (spec 4.7): host root only, no HTTP API, no master
# password. Applies the same reset set as the admin reset and issues one
# recovery grant, shown once for out-of-band delivery.
# Usage: mfa-emergency-reset.sh <deployment dir> <employee_code>
set -euo pipefail
[ "$(id -u)" = "0" ] || { echo "root only" >&2; exit 1; }
DEPLOY_DIR="${1:?usage: mfa-emergency-reset.sh <deployment dir> <employee_code>}"
EMPLOYEE_CODE="${2:?employee_code required}"
cd "$DEPLOY_DIR"
set -a; . ./.env; set +a
exec 9>"/run/lock/sumaiboard-${DEPLOYMENT_ID}.lock"
flock -w 600 9 || { echo "could not acquire deployment lock" >&2; exit 1; }
read -rp "deployment_id を入力してください: " INPUT_ID
[ "$INPUT_ID" = "$DEPLOYMENT_ID" ] || { echo "deployment_id が一致しません。中止します" >&2; exit 1; }
read -rp "操作者氏名: " OPERATOR
read -rp "理由 (10-500文字): " REASON
[ ${#REASON} -ge 10 ] && [ ${#REASON} -le 500 ] || { echo "理由の長さが不正です" >&2; exit 1; }
docker compose exec -T -e SB_EMERG_EMPLOYEE="$EMPLOYEE_CODE" -e SB_EMERG_OPERATOR="$OPERATOR" -e SB_EMERG_REASON="$REASON" app python - <<'PYEOF'
import json, os
from backend.main import connect, _reset_user_mfa, audit, now_jst

code = os.environ["SB_EMERG_EMPLOYEE"]
with connect() as db:
    user = db.execute("SELECT id FROM users WHERE employee_code=?", (code,)).fetchone()
    if not user:
        raise SystemExit(f"user not found: {code}")
    grant = _reset_user_mfa(db, user["id"])
    event_id = audit(db, None, "security.alert", "user", user["id"], json.dumps(
        {"kind": "mfa_emergency_reset", "operator": os.environ["SB_EMERG_OPERATOR"],
         "reason": os.environ["SB_EMERG_REASON"]}, ensure_ascii=False),
        actor_role_override="deployment-operator")
    db.commit()
print("RECOVERY_GRANT (show once, deliver out-of-band):", grant)
PYEOF
echo "emergency reset complete for $EMPLOYEE_CODE (grant expires in 48h)"
