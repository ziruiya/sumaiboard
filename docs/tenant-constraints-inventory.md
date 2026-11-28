# SumaiBoard Tenant Constraints Inventory (G1-01, spec 5.4)

Generated 2026-11-28 from the live product verification DB
(information_schema) and the code at the G1-01 baseline. "Code vs actual"
was compared for every row; differences are registered, not silently fixed.

## Single-tenant invariants

- `tenants` holds exactly one row: id = `DEPLOYMENT_TENANT_ID`, name = the
  internal deployment label (`DEPLOYMENT_NAME` or `tenant-<id>`). It is NOT
  the company-name source (that is `company_settings.company_name`). There
  is no status column (deactivation is a G3 topic).
- `deployment_identity` holds exactly one row (id=1) with profile /
  tenant_id / deployment_id, cross-checked against env at startup before
  any migration or write.
- Startup refuses to boot when: any tenant_id-bearing table contains a
  value other than `DEPLOYMENT_TENANT_ID` (or NULL), the tenants registry
  has != 1 rows, or an initialized DB is missing its registry row (no
  auto-repair outside the NEW / LEGACY_SAMPLE paths).

## Tables carrying tenant_id (actual schema, 24)

applications, buildings, charge_types, company_settings, complaints,
deposits, deployment_identity, fee_plans, fund_accounts,
fund_ledger_entries, inspections, leases, management_contract_units,
management_contracts, owner_accounts, owner_remittances, owner_settlements,
parties, payment_allocations, payments, rent_charges, settlement_lines,
units, work_orders.

All are `INT NOT NULL` in the rental schema (code definition and actual
schema agree). `company_settings.tenant_id` is additionally UNIQUE
(single row per tenant). `deployment_identity.tenant_id` records the
deployment's tenant at bootstrap.

Unique indexes follow the pattern `(tenant_id, id)` and
`(tenant_id, <business code>)` on rental tables (e.g. buildings:
`tenant_id,building_code`; fee_plans: `tenant_id,plan_code,plan_version`;
deposits: `tenant_id,lease_id,management_contract_id`) — verified in
information_schema.STATISTICS; code DDL and actual schema agree.

## Tables without tenant_id (platform / single-instance premise)

users, auth_sessions, auth_mfa_challenges, mfa_enrollments,
user_recovery_codes, mfa_recovery_grants, password_history,
password_reset_tokens, system_configs, audit_events, audit_logs,
audit_chain, audit_outbox, households and the legacy mall/CRM tables,
stores, notifications, preferences and job tables. Authentication is
single-instance by design: `users` has no tenant_id and employee_code is
globally UNIQUE. This is a registered premise of the single-tenant
product, not an oversight.

Foreign keys: rental tables reference buildings/units/leases within the
same tenant by application-level tenant scoping plus FKs on row ids
(verified FK list in information_schema.TABLE_CONSTRAINTS); no cross-tenant
FK exists because there is exactly one tenant per deployment.

## Queries and exceptions

- All rental queries scope by the module constant
  `rental.TENANT_ID = deployment_tenant_id()` (91 references in rental.py,
  guarded by scripts/check-tenant-literals.sh against
  scripts/tenant-literal-baseline.txt).
- Legacy mall/CRM queries predate the tenant model and carry no tenant
  condition; they operate on the same single deployment DB. Registered as
  a known exception for G1-01 (single-tenant deployment makes the blast
  radius the deployment itself).

## Initialization fixed IDs

- `deployment_identity.id = 1` (single row, write-once).
- `audit_chain.id = 1` (single row chain head).
- `tenants.id = DEPLOYMENT_TENANT_ID` (17 verified end-to-end).

## Processes, locks, files

- Single app container / single worker premise: in-process counters and
  the audit chain `FOR UPDATE` head assume one app instance per
  deployment. Scheduled work is host cron only (sample reset 04:00,
  monitor every 5 min); all mutating scripts share the deployment flock
  `/run/lock/sumaiboard-<deployment_id>.lock`.
- Files: attachments under `ATTACHMENT_STORAGE_DIR/{tenant_id}/...`,
  referral documents under the legacy `REFERRAL_STORAGE_DIR` (unchanged),
  backups under `BACKUP_DIR` — the three roots must be pairwise disjoint
  (preflight-isolation.sh, realpath-based).
- Volumes: live stack keeps the historical names (`mallboard-app`,
  `mallboard-mysql`, DB `mallboard`); verify/restore stacks use suffixed
  names via docker-compose.verify.yml.
