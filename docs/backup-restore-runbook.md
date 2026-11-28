# SumaiBoard Backup & Restore Runbook (G1-01)

## Backup (scripts/backup.sh)

Consistency scheme A: the app container is stopped (30 s drain), so no writer
exists; MySQL stays up for the dump. The script refuses to run while any
MySQL Event Scheduler event is ENABLED. It records per-table counts in the
same quiesced state, dumps with
`mysqldump --single-transaction --routines --events --triggers --hex-blob`,
archives storage, and writes `manifest.json` containing: deployment/profile/
tenant identity, app version + build revision, maintenance (stop) duration,
per-table counts, db/storage SHA-256, key-record summaries (company_settings,
admin users — volatile fields excluded), a schema summary hash (columns +
indexes from information_schema) and the audit chain head (max audit_events
id + chain hash). A generation is published atomically and marked `.complete`.
Only an app that this run stopped (and that was running) is restarted;
upgrade-internal backups (`BACKUP_INTERNAL_MODE=1`) never restart the app and
never release the outer maintenance flag.

Status files: `last-attempt.json` is rewritten after every run (success or
failure); `last-success.json` only on success. A failure is "the latest
attempt failed after the last success" — a later success clears it naturally.

Rotation: newest 14 daily + newest 8 ISO-weekly valid generations; pinned
(upgrade) backups are never rotated; rotation is skipped entirely when the
newest backup or its offsite copy failed; deletions are realpath-checked to
stay inside this deployment's BACKUP_DIR.

## Offsite copy

The local generation tar is encrypted with `scripts/backup_crypto.py`
(PBKDF2-HMAC-SHA256, 480k iterations, per-4 MiB-chunk Fernet with the
manifest inside the authenticated payload and every chunk bound to
backup_id/archive/index/total) and rsynced to `OFFSITE_RSYNC_TARGET`
(deployment target: Muse VM `~/workspace/backups/sumaiboard-offsite/<deployment_id>/`,
staging write-only for the push account; a privileged publisher verifies
every chunk and moves generations into the read-only archive). The
passphrase file is root 600 and never enters the backup directory. MFA key
and passphrase escrow copies live in `~/workspace/tools/secrets-sumaiboard/`
(700) on the VM, separate from the data.

## Restore drill (scripts/restore.sh, verify-restore.sh)

Restores go ONLY into the restore stack (`docker-compose.verify.yml`,
suffix `-restore`, port 18190, project name must end in `-restore`). The
script inventories all docker containers/volumes/networks (including
stopped), verifies db/storage hashes and tar safety before loading, loads
the dump into a MySQL-only stack, then:

1. Stage 1 (pristine): per-table counts vs manifest before the app starts.
2. Stage 2 (safe start): sessions, MFA challenges, enrollments and recovery
   grants are revoked (the delta is recorded, not treated as corruption);
   webhook is emptied, no cron, loopback only, profile preserved from the
   backup. Then admin login, MFA secret decryption and business regression
   are verified (F03 numbers only from sample backups or fixtures).

## Production DB disaster recovery (separate from restore.sh)

1. Stop the app; keep the maintenance flag set.
2. Confirm target deployment twice (deployment dir + DEPLOYMENT_ID).
3. Pick the newest `.complete` generation; verify hashes.
4. Load the dump into the production MySQL (this is the ONLY flow allowed
   to write the production DB; restore.sh never does).
5. Run the section-7.3 verification matrix (counts, key summaries, schema
   summary, audit head), revoke all sessions/grants as in stage 2.
6. Start the app, verify health/ready, admin login + MFA, then clear the
   maintenance flag and record the incident.

## Whole-host loss

1. Provision a new host; install Docker.
2. Fetch the newest offsite generation from the Muse VM archive.
3. Restore escrow secrets (MFA key, backup passphrase) from
   `~/workspace/tools/secrets-sumaiboard/`.
4. Decrypt: `backup_crypto.py decrypt` (integrity is verified before any
   unpacking; a mismatch refuses the restore).
5. Deploy the recorded SHA from GitHub, point it at the restored DB using
   the disaster-recovery flow above.

## MFA emergency recovery

If the sole executive loses every authenticator and recovery code:
`scripts/mfa-emergency-reset.sh <deployment dir> <employee_code>` (host root
only). It verifies the typed deployment_id, records operator + reason,
applies the admin-reset set, writes a `security_alert` audit event with
actor `deployment-operator`, and prints one recovery grant (48 h) for
out-of-band delivery. The user then logs in with password + grant and is
forced through password change + MFA enrollment. There is no master
password and no HTTP entry point. Rotate the deployment's MFA key escrow
afterwards per the key-handling note in the spec (section 2.4 SC-03').
