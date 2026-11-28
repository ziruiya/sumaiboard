# SumaiBoard Product Deployment Guide (G1-01, V3.1.0)

Two deployment profiles exist. `DEPLOYMENT_PROFILE` is mandatory and has no
default; the app refuses to start without it.

| | sample | product |
|---|---|---|
| Purpose | public fictional demo | single-tenant production for one customer |
| DEMO_MODE / PUBLIC_SAMPLE_MODE | true | must be false (startup is fatal otherwise) |
| SAMPLE_RESET_TOKEN | set | must be empty (startup is fatal otherwise) |
| DEPLOYMENT_TENANT_ID | must be 1 | any positive integer (verified with 17) |
| Seed data | fictional sample seed | none; only the bootstrap admin |
| MFA | optional, never forced | forced for executive / hq_finance / manager |
| Reset cron | installed (04:00) | **must not be installed** |

## Required environment (see spec section 1 for the full table)

`DEPLOYMENT_PROFILE`, `DEPLOYMENT_ID` (UUID generated per deployment),
`DEPLOYMENT_TENANT_ID`, `PUBLIC_ORIGIN` (trusted origin for CSRF, e.g.
`https://sumaiboard.example.jp`), `ATTACHMENT_STORAGE_DIR`, `BACKUP_DIR`,
`MFA_ENCRYPTION_KEY` (Fernet key, product mandatory), `OPS_STATUS_TOKEN`,
`MONITOR_WEBHOOK_URL` (product delivery gate: must be a real target and
test-fired once), `OFFSITE_RSYNC_TARGET` (product mandatory),
`BACKUP_ENCRYPTION_PASSPHRASE_FILE` (root 600, outside the backup dir).

First boot on a fresh DB additionally needs `INITIAL_ADMIN_EMPLOYEE_CODE`,
`INITIAL_ADMIN_NAME`, `INITIAL_ADMIN_PASSWORD_FILE` (password via file only).
The initial admin is created exactly once, in the same transaction that marks
bootstrap complete; the credentials are ignored on every later start.

## Deploy

```
scripts/preflight-isolation.sh --env /path/to/deployment/.env [--other-env <other .env>]
scripts/deploy.sh --source <git worktree> --sha <full commit SHA> --target <deployment dir> --profile <sample|product>
```

deploy.sh exports an immutable tree via `git archive`, writes `RELEASE.json`
(SHA + tree hash), takes a pinned pre-upgrade backup, snapshots the old tree,
builds serially, waits for readiness (<=120 s) and smokes health /
public-config / (sample) guest login. Releases are appended to
`<target>/releases.log` with a `g1_01_secure=true` marker.

## Rollback

`scripts/rollback.sh --target <dir> --snapshot <snapshot dir>` restores code
only (never the DB). Product targets may only roll back to releases marked
`g1_01_secure=true`; anything older is hard-refused. Database disaster
recovery is a separate runbook procedure (see backup-restore-runbook.md).

## Isolation rules

- One deployment = one DB instance/volume set, one attachment root, one
  backup root, one MFA key. preflight-isolation.sh hard-refuses overlaps
  (realpath/parent-child), shared DB passwords and shared MFA key
  fingerprints with the other deployment.
- Verification and restore stacks use `docker-compose.verify.yml`
  (suffixes `-verify` / `-restore`); they never reuse live names.
