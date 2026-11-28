#!/bin/bash
# SumaiBoard monitor (spec 9). Host-side, cron every 5 minutes.
# Usage: monitor.sh <deployment dir>
# Sample deployments: /api/health + host checks + security_alert DB cursor
# only (never the ops detail endpoint, spec 9 R51-R1).
set -uo pipefail
DEPLOY_DIR="${1:?usage: monitor.sh <deployment dir>}"
cd "$DEPLOY_DIR"
set -a; [ -f .env ] && . ./.env; set +a
: "${DEPLOYMENT_ID:?}"
STATE_DIR="${MONITOR_STATE_DIR:-$DEPLOY_DIR/.monitor}"
mkdir -p "$STATE_DIR"
STATE_FILE="$STATE_DIR/state.json"
QUEUE_FILE="$STATE_DIR/pending-notifications.jsonl"
PORT=$(grep -oE '127.0.0.1:[0-9]+' docker-compose.yml | head -1 | cut -d: -f2); PORT=${PORT:-18080}
BASE="http://127.0.0.1:$PORT"
NOW=$(date +%s)

python3 - "$STATE_FILE" "$QUEUE_FILE" "$BASE" "$NOW" <<'PYEOF'
import json, os, subprocess, sys, time, urllib.request, urllib.error

state_path, queue_path, base, now = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
state = {}
if os.path.exists(state_path):
    try: state = json.load(open(state_path))
    except Exception: state = {}
state.setdefault("events", {})
state.setdefault("security_cursor", 0)
webhook = os.environ.get("MONITOR_WEBHOOK_URL", "").strip()
profile = os.environ.get("DEPLOYMENT_PROFILE", "")
deployment_id = os.environ.get("DEPLOYMENT_ID", "")

def http(path, headers=None, timeout=10):
    req = urllib.request.Request(base + path, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode() or "{}")
        except Exception: return e.code, {}
    except Exception:
        return None, {}

def send(payload):
    """Returns True only on a receiver 2xx (spec 9). Failures stay queued."""
    if not webhook:
        # No webhook configured: persist to the local queue so nothing is lost.
        with open(queue_path, "a") as fh: fh.write(json.dumps(payload) + "\n")
        return True
    req = urllib.request.Request(webhook, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return 200 <= r.status < 300
    except Exception:
        with open(queue_path, "a") as fh: fh.write(json.dumps(payload) + "\n")
        return False

def notify(check, subject, severity, detail, immediate=False):
    event_id = f"{deployment_id}:{check}:{subject}"
    ev = state["events"].get(event_id)
    if not immediate and ev and now - ev.get("last_sent", 0) < 3600 and ev.get("active"):
        return
    payload = {"event_id": event_id, "check": check, "subject": subject,
               "severity": severity, "detail": detail, "profile": profile,
               "at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    if send(payload):
        state["events"][event_id] = {"last_sent": now, "active": True}

def recovered(check, subject):
    event_id = f"{deployment_id}:{check}:{subject}"
    ev = state["events"].get(event_id)
    if ev and ev.get("active"):
        payload = {"event_id": event_id, "check": check, "subject": subject,
                   "severity": "recovered", "detail": "recovered",
                   "at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
        if send(payload):
            state["events"][event_id] = {"last_sent": 0, "active": False}

problems = []
status, health = http("/api/health")
if status is None or status >= 500 or health.get("db") == "error":
    problems.append(("health", "app", "critical", f"health status={status} body={health}"))
else:
    recovered("health", "app")
    if health.get("status") == "degraded":
        problems.append(("health-degraded", "app", "warning", json.dumps(health)))
    else:
        recovered("health-degraded", "app")
status_r, ready = http("/api/health/ready")
if status_r != 200:
    problems.append(("ready", "app", "critical", f"ready status={status_r}"))
else:
    recovered("ready", "app")

if profile == "product" and os.environ.get("OPS_STATUS_TOKEN"):
    st, detail = http("/api/ops/status-detail", {"X-Ops-Token": os.environ["OPS_STATUS_TOKEN"]})
    if st != 200:
        problems.append(("ops-detail", "app", "warning", f"ops detail status={st}"))
    else:
        recovered("ops-detail", "app")

# Backup status files.
status_dir = os.path.dirname(os.environ.get("BACKUP_STATUS_FILE", "")) or "."
def load_json(p):
    try: return json.load(open(p))
    except Exception: return None
success = load_json(os.path.join(status_dir, "last-success.json"))
attempt = load_json(os.path.join(status_dir, "last-attempt.json"))
if attempt and success:
    if attempt.get("result") == "failure" and attempt.get("at", "") > (success.get("completed_at") or ""):
        problems.append(("backup-failed", "backup", "critical", json.dumps(attempt)))
    else:
        recovered("backup-failed", "backup")
if success:
    try:
        done = time.mktime(time.strptime(success["completed_at"][:19], "%Y-%m-%dT%H:%M:%S"))
        if now - done > 26 * 3600:
            problems.append(("backup-stale", "backup", "warning", f"last success {success['completed_at']}"))
        else:
            recovered("backup-stale", "backup")
    except Exception:
        pass
    # M-03-R2: distinguish pending / published / failed. The authoritative
    # publication state comes from status/offsite-published.json, written
    # by the VM pull+publish confirmation; last-success only records the
    # state known at backup time.
    pub = load_json(os.path.join(status_dir, "offsite-published.json")) or {}
    bid = success.get("backup_id", "")
    offsite_state = pub.get(bid) or success.get("offsite")
    if offsite_state == "failed":
        problems.append(("backup-offsite", "backup", "warning", "offsite publish failed"))
    elif offsite_state == "pending":
        try:
            done = time.mktime(time.strptime(success["completed_at"][:19], "%Y-%m-%dT%H:%M:%S"))
            if now - done > 2 * 3600:
                problems.append(("backup-offsite-pending", "backup", "warning", "offsite publication unconfirmed >2h"))
            else:
                recovered("backup-offsite-pending", "backup")
        except Exception:
            pass
        recovered("backup-offsite", "backup")
    elif offsite_state == "published":
        recovered("backup-offsite", "backup")
        recovered("backup-offsite-pending", "backup")
    else:
        recovered("backup-offsite", "backup")
if attempt and attempt.get("offsite") == "failed":
    problems.append(("backup-offsite", "backup", "warning", "offsite copy failed (attempt)"))

# Disk + clock.
df = subprocess.run(["df", "--output=pcent", "."], capture_output=True, text=True).stdout
try:
    used_pct = int(df.strip().splitlines()[-1].strip().rstrip("%"))
    if used_pct > 85:
        problems.append(("disk", "host", "warning", f"disk used {used_pct}%"))
    else:
        recovered("disk", "host")
except Exception:
    pass
try:
    out = subprocess.run(["timedatectl", "show", "-p", "NTPSynchronized", "--value"],
                         capture_output=True, text=True).stdout.strip()
    if out != "yes":
        problems.append(("clock", "host", "warning", "NTP not synchronized"))
    else:
        recovered("clock", "host")
except Exception:
    pass

# Containers: existence / exited / restart growth / unhealthy.
ps = subprocess.run(["docker", "compose", "ps", "-a", "--format", "json"],
                    capture_output=True, text=True, cwd=os.getcwd()).stdout
containers = {}
for line in ps.splitlines():
    try:
        c = json.loads(line); containers[c["Name"]] = c
    except Exception:
        pass
prev_restarts = state.get("restarts", {})
restarts = {}
for name, c in containers.items():
    restarts[name] = c.get("RestartCount", 0)
    if c.get("State") != "running":
        problems.append(("container-down", name, "critical", f"state={c.get('State')}"))
    else:
        recovered("container-down", name)
    if "unhealthy" in (c.get("Health") or ""):
        problems.append(("container-unhealthy", name, "warning", "health=unhealthy"))
    else:
        recovered("container-unhealthy", name)
    if prev_restarts.get(name) is not None and restarts[name] > prev_restarts[name]:
        problems.append(("container-restarts", name, "warning",
                         f"restart count {prev_restarts[name]} -> {restarts[name]}"))
    else:
        recovered("container-restarts", name)
state["restarts"] = restarts
if not containers:
    problems.append(("container-down", "compose", "critical", "no containers found"))

for check, subject, severity, detail in problems:
    notify(check, subject, severity, detail)

# Security events channel (spec 9): audit_events security_alert by cursor.
try:
    q = ("SELECT id FROM audit_events WHERE event_type='security_alert' AND id>%d ORDER BY id"
         % int(state.get("security_cursor", 0)))
    out = subprocess.run(
        ["docker", "compose", "exec", "-T", "mysql", "mysql",
         "-u" + os.environ.get("DB_USER", ""), "-p" + os.environ.get("DB_PASSWORD", ""),
         "-N", "-e", q, os.environ.get("DB_NAME", "")],
        capture_output=True, text=True, cwd=os.getcwd(), timeout=30).stdout
    ids = [int(x) for x in out.split() if x.isdigit()]
    max_id_out = subprocess.run(
        ["docker", "compose", "exec", "-T", "mysql", "mysql",
         "-u" + os.environ.get("DB_USER", ""), "-p" + os.environ.get("DB_PASSWORD", ""),
         "-N", "-e", "SELECT COALESCE(MAX(id),0) FROM audit_events", os.environ.get("DB_NAME", "")],
        capture_output=True, text=True, cwd=os.getcwd(), timeout=30).stdout.strip()
    max_id = int(max_id_out) if max_id_out.isdigit() else state.get("security_cursor", 0)
    cursor = int(state.get("security_cursor", 0))
    if max_id < cursor:
        # Restore rolled the id space back: rebuild the baseline (spec 9).
        payload = {"event_id": f"{deployment_id}:security-cursor:reset",
                   "check": "security-cursor", "subject": "audit",
                   "severity": "warning",
                   "detail": f"audit id regressed {cursor} -> {max_id}; cursor rebuilt",
                   "at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
        if send(payload):
            state["security_cursor"] = max_id
    else:
        for event_pk in ids:
            payload = {"event_id": f"{deployment_id}:security_alert:{event_pk}",
                       "check": "security_alert", "subject": str(event_pk),
                       "severity": "critical",
                       "detail": f"security_alert audit event {event_pk}",
                       "at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
            if send(payload):
                state["security_cursor"] = event_pk
            else:
                break  # cursor advances only after successful send/queue
except Exception as exc:
    print(f"security channel check failed: {exc}", file=sys.stderr)

tmp = state_path + ".tmp"
open(tmp, "w").write(json.dumps(state, indent=1))
os.replace(tmp, state_path)
print(f"monitor done: {len(problems)} active problem(s)")
PYEOF
