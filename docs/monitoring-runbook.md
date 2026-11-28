# SumaiBoard Monitoring Runbook (G1-01)

## Endpoints

| Endpoint | Access | Contract |
|---|---|---|
| `GET /api/health` | public | DB unreachable → 503 `{status:"error",db:"error",version}`; degraded items (stale backup, self-check warnings) → 200 `{status:"degraded",...}`; healthy → 200 `{status:"ok",...}` |
| `GET /api/health/ready` | public | 503 until startup stage 5 completes and while the DB is lost; stale backups do not affect readiness |
| `GET /api/ops/status-detail` | `X-Ops-Token` header | profile, build revision, self-check items, backup status (from the read-only `BACKUP_STATUS_FILE` mount), disk, clock offset. Empty `OPS_STATUS_TOKEN` disables the endpoint (404); an empty token never matches |

## monitor.sh (host cron, every 5 minutes)

Checks: health/ready; ops detail (product only — sample monitors never call
it; they use health + host checks + the DB security channel); backup
staleness (>26 h), latest-attempt failure, offsite failure; disk <15 % free;
clock drift / NTP unsynchronized; container existence, exit, restart-count
growth, unhealthy.

Notifications: event id is `{deployment_id}:{check}:{subject}` (stable).
The same event is suppressed for 1 hour; on recovery a recovery notification
is sent and suppression is cleared, so a later recurrence alerts immediately.
Webhook timeouts are 5 s connect / 15 s total; only a receiver 2xx counts as
sent — failures are kept in the local pending queue and retried next run
(retry counting is separate from suppression). Payloads never contain
credentials, secrets or full account numbers.

Security channel: monitor reads `audit_events` rows with
`event_type='security_alert'` (admin MFA resets, emergency resets) by an
`id` cursor stored in its state file. Security events are notified
immediately (no 1-hour suppression, deduplicated by event id). The cursor
advances only after a successful send or after the event is persisted to
the local pending queue. If the maximum audit id falls below the cursor
(a restore rolled the id space back), the cursor is rebuilt to the current
maximum and a baseline-reset notification is sent, so new events are never
swallowed by a stale cursor.

## Delivery gate

Before a product deployment is handed over, `MONITOR_WEBHOOK_URL` must be a
real target and at least one real test notification must have been sent and
recorded (deployment target: the Muse VM tailnet receiver).

## Stale maintenance flag

If a maintenance flag survives a crashed operation or a host reboot,
monitor alerts on its age. Controlled clearing procedure: confirm no
deploy/backup/restore/reset process is running for the deployment, remove
the flag file, and record the clearing (operator + reason) in the
deployment's releases.log.
