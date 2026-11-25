import asyncio
import csv
import io
import json
import hashlib
import hmac
import logging
import os
import re
import secrets
import time
import unicodedata
import uuid
from collections import OrderedDict, deque
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo
from urllib.parse import quote

import pymysql
from pymysql.cursors import DictCursor
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from backend.pdf_export import PDF_TEMPLATE_VERSION, build_pdf_isolated
from backend import rental


ROOT = Path(__file__).resolve().parent.parent
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "mysql"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.environ["DB_USER"],
    "password": os.environ["DB_PASSWORD"],
    "database": os.environ["DB_NAME"],
    "charset": "utf8mb4",
    "cursorclass": DictCursor,
    "connect_timeout": 10,
    "init_command": "SET time_zone = '+09:00'",
}
REFERRAL_STORAGE_DIR = Path(os.getenv(
    "REFERRAL_STORAGE_DIR", "/app/private_storage/referral-documents"
))

app = FastAPI(title="SumaiBoard", version="0.1.0")
LOGGER = logging.getLogger("sumaiboard")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS stores (
  id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(120) NOT NULL, area VARCHAR(120) NOT NULL,
  opened_at DATE NULL
);
CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(120) NOT NULL, role VARCHAR(40) NOT NULL,
  store_id INT NULL, employee_code VARCHAR(30) NULL UNIQUE, public_id CHAR(36) NULL UNIQUE,
  display_name VARCHAR(120) NULL, password_hash VARCHAR(255) NULL,
  account_status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE', failed_login_attempts INT NOT NULL DEFAULT 0,
  locked_until DATETIME NULL, must_change_password TINYINT NOT NULL DEFAULT 1,
  last_login_at DATETIME NULL, password_changed_at DATETIME NULL, last_password_reset_at DATETIME NULL,
  version INT NOT NULL DEFAULT 1,
  FOREIGN KEY (store_id) REFERENCES stores(id)
);
CREATE TABLE IF NOT EXISTS households (
  id INT AUTO_INCREMENT PRIMARY KEY, representative_name VARCHAR(120) NOT NULL, store_id INT,
  advisor_id INT, budget_band VARCHAR(120), area_pref VARCHAR(255), land_status VARCHAR(40),
  status VARCHAR(40) NOT NULL DEFAULT 'active', lost_reason TEXT, created_at DATETIME NOT NULL,
  household_code VARCHAR(24) UNIQUE, kana VARCHAR(120) NULL,
  FOREIGN KEY (store_id) REFERENCES stores(id), FOREIGN KEY (advisor_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS persons (
  id INT AUTO_INCREMENT PRIMARY KEY, household_id INT NOT NULL, name VARCHAR(120) NOT NULL,
  relation VARCHAR(80), phone VARCHAR(50), email VARCHAR(255), kana VARCHAR(120) NULL,
  FOREIGN KEY (household_id) REFERENCES households(id)
);
CREATE TABLE IF NOT EXISTS touches (
  id INT AUTO_INCREMENT PRIMARY KEY, household_id INT NOT NULL, touch_at DATETIME NOT NULL,
  channel VARCHAR(80) NOT NULL, campaign_id VARCHAR(255), creative_id VARCHAR(255), tracking_code VARCHAR(255),
  landing_referrer VARCHAR(500), store_id INT, capture_method VARCHAR(80),
  FOREIGN KEY (household_id) REFERENCES households(id), FOREIGN KEY (store_id) REFERENCES stores(id)
);
CREATE TABLE IF NOT EXISTS activities (
  id INT AUTO_INCREMENT PRIMARY KEY, household_id INT NOT NULL, user_id INT NOT NULL,
  type VARCHAR(80) NOT NULL, body TEXT NOT NULL, acted_at DATETIME NOT NULL,
  next_action TEXT, next_action_due DATE, FOREIGN KEY (household_id) REFERENCES households(id),
  FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS stage_events (
  id INT AUTO_INCREMENT PRIMARY KEY, household_id INT NOT NULL, from_stage VARCHAR(80), to_stage VARCHAR(80) NOT NULL,
  changed_by INT, changed_at DATETIME NOT NULL, FOREIGN KEY (household_id) REFERENCES households(id),
  FOREIGN KEY (changed_by) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS partners (
  id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(160) NOT NULL, area VARCHAR(120),
  tags JSON NOT NULL, active TINYINT NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS partner_staff (
  id INT AUTO_INCREMENT PRIMARY KEY, partner_id INT NOT NULL, name VARCHAR(120) NOT NULL,
  branch_name VARCHAR(120),
  FOREIGN KEY (partner_id) REFERENCES partners(id)
);
CREATE TABLE IF NOT EXISTS fee_rules (
  id INT AUTO_INCREMENT PRIMARY KEY, version VARCHAR(80) NOT NULL, type VARCHAR(40) NOT NULL, params JSON NOT NULL,
  base VARCHAR(120) NOT NULL, effective_from DATE NOT NULL, effective_to DATE NULL, approved_by INT,
  FOREIGN KEY (approved_by) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS partner_agreements (
  id INT AUTO_INCREMENT PRIMARY KEY, partner_id INT NOT NULL, effective_from DATE NOT NULL,
  effective_to DATE, fee_rule_id INT NOT NULL, status VARCHAR(40) NOT NULL,
  FOREIGN KEY (partner_id) REFERENCES partners(id), FOREIGN KEY (fee_rule_id) REFERENCES fee_rules(id)
);
CREATE TABLE IF NOT EXISTS introductions (
  id INT AUTO_INCREMENT PRIMARY KEY, household_id INT NOT NULL, partner_id INT NOT NULL,
  partner_staff_id INT, advisor_id INT, introduced_at DATETIME NOT NULL, reception_confirmed_at DATETIME,
  status VARCHAR(80) NOT NULL, existing_customer_flag TINYINT NOT NULL DEFAULT 0, evidence_note TEXT,
  valid_until DATE NULL, referral_letter_id CHAR(36) NULL,
  FOREIGN KEY (household_id) REFERENCES households(id), FOREIGN KEY (partner_id) REFERENCES partners(id),
  FOREIGN KEY (partner_staff_id) REFERENCES partner_staff(id)
);
CREATE TABLE IF NOT EXISTS negotiations (
  id INT AUTO_INCREMENT PRIMARY KEY, introduction_id INT NOT NULL, status VARCHAR(80) NOT NULL,
  last_activity_at DATETIME NOT NULL, next_action VARCHAR(255) NULL, next_action_due DATE NULL,
  next_action_owner_id INT NULL, risk_level VARCHAR(20) NOT NULL DEFAULT 'none',
  version INT NOT NULL DEFAULT 1,
  FOREIGN KEY (introduction_id) REFERENCES introductions(id),
  FOREIGN KEY (next_action_owner_id) REFERENCES users(id),
  INDEX idx_negotiations_next_action(next_action_due,next_action_owner_id)
);
CREATE TABLE IF NOT EXISTS contracts (
  id INT AUTO_INCREMENT PRIMARY KEY, negotiation_id INT NOT NULL, contract_date DATE NOT NULL,
  contract_amount BIGINT NOT NULL, builder_contact VARCHAR(120) NOT NULL,
  FOREIGN KEY (negotiation_id) REFERENCES negotiations(id)
);
CREATE TABLE IF NOT EXISTS construction_projects (
  id INT AUTO_INCREMENT PRIMARY KEY, contract_id INT NOT NULL, planned_start_date DATE,
  actual_start_date DATE, confirmed_start_date DATE, confirmation_evidence TEXT,
  confirmation_due_date DATE, confirmation_status VARCHAR(40) NOT NULL DEFAULT 'pending_review',
  delayed_note TEXT,
  FOREIGN KEY (contract_id) REFERENCES contracts(id)
);
CREATE TABLE IF NOT EXISTS fee_entitlements (
  id INT AUTO_INCREMENT PRIMARY KEY, contract_id INT NOT NULL, introduction_id INT NOT NULL,
  fee_rule_id INT NOT NULL, base_amount BIGINT NOT NULL, calculated_amount BIGINT NOT NULL,
  state VARCHAR(40) NOT NULL, dispute_reason TEXT, calculated_at DATETIME NOT NULL, confirmed_by INT,
  invoice_data_generated TINYINT NOT NULL DEFAULT 0, reference_amount BIGINT NOT NULL DEFAULT 0,
  FOREIGN KEY (contract_id) REFERENCES contracts(id), FOREIGN KEY (introduction_id) REFERENCES introductions(id),
  FOREIGN KEY (fee_rule_id) REFERENCES fee_rules(id), FOREIGN KEY (confirmed_by) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS referral_disputes (
  id INT AUTO_INCREMENT PRIMARY KEY, fee_entitlement_id INT NOT NULL, raised_by INT NOT NULL,
  reason TEXT NOT NULL, evidence_level VARCHAR(8) NOT NULL, status VARCHAR(40) NOT NULL, decided_by INT,
  decided_at DATETIME, decision_note TEXT, due_date DATE NULL,
  dispute_type VARCHAR(40) NOT NULL DEFAULT 'referral', reference_amount BIGINT NOT NULL DEFAULT 0,
  FOREIGN KEY (fee_entitlement_id) REFERENCES fee_entitlements(id),
  FOREIGN KEY (raised_by) REFERENCES users(id), FOREIGN KEY (decided_by) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS consents (
  id INT AUTO_INCREMENT PRIMARY KEY, household_id INT NOT NULL, purpose VARCHAR(255) NOT NULL,
  scope VARCHAR(40) NOT NULL, granted_at DATETIME NOT NULL, revoked_at DATETIME,
  consent_method VARCHAR(80) NULL, content_version VARCHAR(40) NULL,
  allowed_fields_json JSON NULL, partner_id INT NULL, expires_at DATETIME NULL,
  evidence_reference VARCHAR(255) NULL,
  FOREIGN KEY (household_id) REFERENCES households(id)
);
CREATE TABLE IF NOT EXISTS data_disclosures (
  id INT AUTO_INCREMENT PRIMARY KEY, household_id INT NOT NULL, disclosed_to VARCHAR(255) NOT NULL,
  scope VARCHAR(40) NOT NULL, disclosed_by INT NOT NULL, disclosed_at DATETIME NOT NULL,
  consent_id INT, FOREIGN KEY (household_id) REFERENCES households(id),
  FOREIGN KEY (disclosed_by) REFERENCES users(id), FOREIGN KEY (consent_id) REFERENCES consents(id)
);
CREATE TABLE IF NOT EXISTS referral_document_files (
  id CHAR(36) PRIMARY KEY, storage_key VARCHAR(255) NOT NULL, size_bytes BIGINT NOT NULL,
  sha256 CHAR(64) NOT NULL, status VARCHAR(20) NOT NULL DEFAULT 'AVAILABLE',
  created_at DATETIME NOT NULL, deleted_at DATETIME NULL, deletion_reason VARCHAR(255) NULL
);
CREATE TABLE IF NOT EXISTS referral_documents (
  id CHAR(36) PRIMARY KEY, document_number VARCHAR(80) NOT NULL UNIQUE,
  introduction_id INT NOT NULL, household_id INT NOT NULL, partner_id INT NOT NULL,
  partner_staff_id INT NULL, recipient_name VARCHAR(120) NOT NULL,
  issuing_store_id INT NOT NULL, advisor_id INT NULL, issued_on DATE NOT NULL,
  consent_id INT NOT NULL,
  status VARCHAR(20) NOT NULL, template_version VARCHAR(40) NOT NULL,
  generated_at DATETIME NOT NULL, expires_at DATETIME NOT NULL,
  sha256 CHAR(64) NOT NULL, file_id CHAR(36) NOT NULL,
  storage_reference VARCHAR(255) NOT NULL, generated_by INT NOT NULL,
  generation_result VARCHAR(20) NOT NULL, failure_reason TEXT NULL,
  audit_event_id BIGINT NULL, created_at DATETIME NOT NULL,
  INDEX idx_referral_documents_intro(introduction_id,created_at)
);
CREATE TABLE IF NOT EXISTS referral_document_generations (
  id CHAR(36) PRIMARY KEY, document_id CHAR(36) NULL, introduction_id INT NOT NULL,
  generated_by INT NOT NULL, requested_at DATETIME NOT NULL,
  result VARCHAR(20) NOT NULL, failure_reason TEXT NULL, audit_event_id BIGINT NULL,
  INDEX idx_referral_generations_intro(introduction_id,requested_at)
);
CREATE TABLE IF NOT EXISTS data_correction_requests (
  id CHAR(36) PRIMARY KEY, household_id INT NOT NULL, field_name VARCHAR(80) NOT NULL,
  before_value TEXT NULL, requested_value TEXT NOT NULL, reason TEXT NOT NULL,
  requested_by INT NOT NULL, requested_at DATETIME NOT NULL,
  status ENUM('PENDING','APPROVED','REJECTED') NOT NULL DEFAULT 'PENDING',
  decided_by INT NULL, decided_at DATETIME NULL, decision_note TEXT NULL, version INT NOT NULL DEFAULT 1,
  INDEX idx_data_corrections_status(status,requested_at),
  FOREIGN KEY (household_id) REFERENCES households(id), FOREIGN KEY (requested_by) REFERENCES users(id),
  FOREIGN KEY (decided_by) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS tasks (
  id INT AUTO_INCREMENT PRIMARY KEY, assignee_id INT NOT NULL, title VARCHAR(255) NOT NULL, due_at DATE NOT NULL,
  source VARCHAR(40) NOT NULL, related_household_id INT, done TINYINT NOT NULL DEFAULT 0,
  task_type VARCHAR(40) NOT NULL DEFAULT 'followup', priority VARCHAR(20) NOT NULL DEFAULT 'normal',
  related_type VARCHAR(40) NOT NULL DEFAULT 'household', related_id INT, cancelled TINYINT NOT NULL DEFAULT 0,
  status VARCHAR(20) NOT NULL DEFAULT 'open',
  FOREIGN KEY (assignee_id) REFERENCES users(id), FOREIGN KEY (related_household_id) REFERENCES households(id)
);
CREATE TABLE IF NOT EXISTS expenses (
  id CHAR(36) PRIMARY KEY, applicant_id INT NOT NULL, store_id INT NULL,
  category VARCHAR(80) NOT NULL, amount BIGINT NOT NULL, description TEXT NOT NULL,
  expense_date DATE NOT NULL, receipt_filename VARCHAR(255) NULL, receipt_mime VARCHAR(80) NULL,
  receipt_size BIGINT NULL, receipt_sha256 CHAR(64) NULL, receipt_blob LONGBLOB NULL,
  status ENUM('DRAFT','SUBMITTED','APPROVED','REJECTED','RECORDED') NOT NULL DEFAULT 'DRAFT',
  rejection_reason TEXT NULL, version INT NOT NULL DEFAULT 1,
  applied_at DATETIME NULL, tax_amount BIGINT NOT NULL DEFAULT 0,
  tax_category VARCHAR(40) NOT NULL DEFAULT '課税10%%（税込）',
  reviewed_by INT NULL, reviewed_at DATETIME NULL, finance_recorded_by INT NULL,
  finance_recorded_at DATETIME NULL, accounting_integration_id VARCHAR(160) NULL,
  recorded_reference VARCHAR(500) NULL, recorded_confirmed_at DATETIME NULL,
  created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL,
  INDEX idx_expenses_applicant(applicant_id,status,expense_date),
  INDEX idx_expenses_store(store_id,status,expense_date)
);
CREATE TABLE IF NOT EXISTS external_record_mappings (
  id BIGINT AUTO_INCREMENT PRIMARY KEY, source_system VARCHAR(40) NOT NULL,
  external_id VARCHAR(160) NOT NULL, object_type VARCHAR(40) NOT NULL,
  local_id VARCHAR(160) NOT NULL, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL,
  UNIQUE KEY uq_external_record(source_system,external_id)
);
CREATE TABLE IF NOT EXISTS import_jobs (
  id CHAR(36) PRIMARY KEY, source_system VARCHAR(40) NOT NULL, requested_by INT NOT NULL,
  filename VARCHAR(255) NOT NULL, total_rows INT NOT NULL DEFAULT 0,
  success_rows INT NOT NULL DEFAULT 0, skipped_rows INT NOT NULL DEFAULT 0,
  error_rows INT NOT NULL DEFAULT 0, status VARCHAR(24) NOT NULL,
  created_at DATETIME NOT NULL, finished_at DATETIME NULL,
  content_sha256 CHAR(64) NULL, mapping_json JSON NULL, preview_expires_at DATETIME NULL,
  INDEX idx_import_jobs_requester(requested_by,created_at)
);
CREATE TABLE IF NOT EXISTS import_row_results (
  id BIGINT AUTO_INCREMENT PRIMARY KEY, job_id CHAR(36) NOT NULL, source_row_number INT NOT NULL,
  external_id VARCHAR(160) NULL, status VARCHAR(24) NOT NULL, reason VARCHAR(500) NULL,
  local_id VARCHAR(160) NULL, created_at DATETIME NOT NULL,
  INDEX idx_import_rows_job(job_id,source_row_number)
);
CREATE TABLE IF NOT EXISTS export_jobs (
  id CHAR(36) PRIMARY KEY, user_id INT NOT NULL, resource VARCHAR(40) NOT NULL,
  format VARCHAR(12) NOT NULL DEFAULT 'csv', template_version VARCHAR(40) NOT NULL DEFAULT 'csv-v1',
  created_role VARCHAR(40) NOT NULL DEFAULT '', scope_store_id INT NULL,
  include_personal_data TINYINT NOT NULL DEFAULT 0, record_ids_json LONGTEXT NULL,
  filename VARCHAR(255) NOT NULL, row_count INT NOT NULL, content_sha256 CHAR(64) NOT NULL,
  content LONGBLOB NOT NULL, status VARCHAR(24) NOT NULL DEFAULT 'READY',
  created_at DATETIME NOT NULL, expires_at DATETIME NOT NULL, downloaded_at DATETIME NULL,
  INDEX idx_export_jobs_user(user_id,created_at)
);
CREATE TABLE IF NOT EXISTS month_closes (
  id CHAR(36) PRIMARY KEY, period CHAR(7) NOT NULL, snapshot_version INT NOT NULL,
  status VARCHAR(32) NOT NULL, snapshot_json JSON NOT NULL, snapshot_sha256 CHAR(64) NOT NULL,
  prepared_by INT NOT NULL, prepared_at DATETIME NOT NULL, closed_by INT NULL,
  closed_at DATETIME NULL, reopen_requested_by INT NULL, reopen_reason TEXT NULL,
  reopen_requested_at DATETIME NULL, reopen_approved_by INT NULL, reopened_at DATETIME NULL,
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uq_month_close_version(period,snapshot_version),
  INDEX idx_month_closes_period(period,status)
);
CREATE TABLE IF NOT EXISTS month_close_period_locks (
  period CHAR(7) PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS daily_report_drafts (
  id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL, report_date DATE NOT NULL,
  auto_summary TEXT NOT NULL, manual_note TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS audit_logs (
  id INT AUTO_INCREMENT PRIMARY KEY, user_id INT, action VARCHAR(120) NOT NULL, target_type VARCHAR(120) NOT NULL,
  target_id INT, target_id_text VARCHAR(160) NULL, `at` DATETIME NOT NULL, detail TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS system_configs (
  config_key VARCHAR(120) PRIMARY KEY, value_json JSON NOT NULL, updated_at DATETIME NOT NULL,
  updated_by INT NULL
);
CREATE TABLE IF NOT EXISTS audit_chain (
  id TINYINT PRIMARY KEY, last_hash CHAR(64) NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_events (
  id BIGINT AUTO_INCREMENT PRIMARY KEY, actor_id INT NULL, actor_role VARCHAR(40) NOT NULL,
  action VARCHAR(120) NOT NULL, object_type VARCHAR(120) NOT NULL, object_id INT NULL,
  object_id_text VARCHAR(160) NULL,
  reason TEXT NOT NULL, event_at DATETIME NOT NULL, previous_hash CHAR(64) NOT NULL,
  event_hash CHAR(64) NOT NULL UNIQUE, event_type VARCHAR(80) NULL, before_hash CHAR(64) NULL,
  after_hash CHAR(64) NULL, request_id CHAR(36) NULL, result VARCHAR(40) NULL, error_code VARCHAR(80) NULL,
  INDEX idx_audit_events_at(event_at), INDEX idx_audit_events_object(object_type, object_id)
);
CREATE TABLE IF NOT EXISTS auth_sessions (
  id CHAR(36) PRIMARY KEY, user_id INT NOT NULL, token_hash CHAR(64) NOT NULL UNIQUE,
  created_at DATETIME NOT NULL, last_seen_at DATETIME NOT NULL, expires_at DATETIME NOT NULL,
  revoked_at DATETIME NULL, source_ip VARCHAR(64) NULL, user_agent_hash CHAR(64) NULL,
  INDEX idx_auth_sessions_user(user_id,revoked_at)
);
CREATE TABLE IF NOT EXISTS auth_login_attempts (
  id BIGINT AUTO_INCREMENT PRIMARY KEY, identity_hash CHAR(64) NOT NULL,
  source_ip VARCHAR(64) NULL, attempted_at DATETIME NOT NULL, succeeded TINYINT NOT NULL DEFAULT 0,
  INDEX idx_login_attempts_identity(identity_hash,attempted_at),
  INDEX idx_login_attempts_ip(source_ip,attempted_at)
);
CREATE TABLE IF NOT EXISTS password_history (
  id BIGINT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL,
  password_hash VARCHAR(255) NOT NULL, created_at DATETIME NOT NULL,
  INDEX idx_password_history_user(user_id,created_at)
);
CREATE TABLE IF NOT EXISTS password_reset_tokens (
  id CHAR(36) PRIMARY KEY, user_id INT NOT NULL, token_hash CHAR(64) NOT NULL UNIQUE,
  expires_at DATETIME NOT NULL, used_at DATETIME NULL, created_by INT NOT NULL,
  verification_method VARCHAR(40) NOT NULL, created_at DATETIME NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications (
  id CHAR(36) PRIMARY KEY, user_id INT NOT NULL,
  notification_type ENUM('TASK','APPROVAL','EXPENSE','DAILY_REPORT','IMPORT','MONTHLY_CLOSE',
    'DOCUMENT','EXPORT','DATA_CORRECTION','SECURITY','SYSTEM') NOT NULL,
  system_event_code VARCHAR(80) NULL, title VARCHAR(255) NOT NULL, title_zh VARCHAR(255) NULL,
  message TEXT NOT NULL, message_zh TEXT NULL,
  related_record_type VARCHAR(80) NULL, related_record_id VARCHAR(160) NULL,
  status ENUM('UNREAD','READ','ARCHIVED') NOT NULL DEFAULT 'UNREAD',
  created_at DATETIME NOT NULL, read_at DATETIME NULL,
  INDEX idx_notifications_user(user_id,status,created_at)
);
CREATE TABLE IF NOT EXISTS notification_deliveries (
  id CHAR(36) PRIMARY KEY, notification_id CHAR(36) NOT NULL, channel VARCHAR(20) NOT NULL,
  delivery_status VARCHAR(24) NOT NULL, attempt_count INT NOT NULL DEFAULT 0,
  last_error VARCHAR(255) NULL, sent_at DATETIME NULL
);
CREATE TABLE IF NOT EXISTS migration_mappings (
  id INT AUTO_INCREMENT PRIMARY KEY, old_demo_role VARCHAR(40) NOT NULL, old_user_id INT NOT NULL,
  new_user_id INT NULL,
  store_id INT NULL, mapped_by INT NULL, mapped_at DATETIME NULL, status VARCHAR(32) NOT NULL,
  old_display_name VARCHAR(120) NULL, UNIQUE KEY uq_migration_user(old_user_id)
);
CREATE TABLE IF NOT EXISTS audit_outbox (
  id CHAR(36) PRIMARY KEY, event_type VARCHAR(80) NOT NULL, aggregate_id VARCHAR(160) NOT NULL,
  sequence_no BIGINT NOT NULL, payload_hash CHAR(64) NOT NULL,
  status ENUM('PENDING','PROCESSING','COMPLETED','DEAD_LETTER') NOT NULL DEFAULT 'PENDING',
  attempt_count INT NOT NULL DEFAULT 0, next_retry_at DATETIME NULL, error_code VARCHAR(80) NULL,
  created_at DATETIME NOT NULL, UNIQUE KEY uq_outbox_aggregate_sequence(aggregate_id,sequence_no)
);
CREATE TABLE IF NOT EXISTS seed_metadata (
  id TINYINT PRIMARY KEY, batch_key VARCHAR(80) NOT NULL, seeded_at DATETIME NOT NULL
);
CREATE TABLE IF NOT EXISTS user_preferences (
  user_id INT PRIMARY KEY, dashboard_widgets JSON NOT NULL, notification_preferences JSON NOT NULL,
  updated_at DATETIME NOT NULL, FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS calendar_events (
  id CHAR(36) PRIMARY KEY, owner_id INT NOT NULL, title VARCHAR(255) NOT NULL,
  event_type VARCHAR(40) NOT NULL, starts_at DATETIME NOT NULL, ends_at DATETIME NULL,
  all_day TINYINT NOT NULL DEFAULT 0, visibility VARCHAR(20) NOT NULL DEFAULT 'private',
  store_id INT NULL, created_by INT NOT NULL, updated_by INT NOT NULL,
  created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL, version INT NOT NULL DEFAULT 1,
  INDEX idx_calendar_events_range(starts_at,ends_at),
  INDEX idx_calendar_events_owner(owner_id,starts_at),
  FOREIGN KEY (owner_id) REFERENCES users(id), FOREIGN KEY (store_id) REFERENCES stores(id)
);
CREATE TABLE IF NOT EXISTS bulletin_posts (
  id CHAR(36) PRIMARY KEY, post_type VARCHAR(40) NOT NULL, title VARCHAR(255) NOT NULL,
  body TEXT NOT NULL, author_id INT NOT NULL, department VARCHAR(120) NULL, store_id INT NULL,
  visibility VARCHAR(20) NOT NULL DEFAULT 'company', status VARCHAR(20) NOT NULL DEFAULT 'published',
  pinned TINYINT NOT NULL DEFAULT 0, published_at DATETIME NULL, created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL, daily_report_user_id INT NULL, daily_report_date DATE NULL,
  UNIQUE KEY uq_bulletin_daily_report(daily_report_user_id,daily_report_date),
  INDEX idx_bulletin_scope(status,visibility,store_id,published_at),
  FOREIGN KEY (author_id) REFERENCES users(id), FOREIGN KEY (store_id) REFERENCES stores(id)
);
CREATE TABLE IF NOT EXISTS bulletin_comments (
  id BIGINT AUTO_INCREMENT PRIMARY KEY, post_id CHAR(36) NOT NULL, author_id INT NOT NULL,
  body TEXT NOT NULL, created_at DATETIME NOT NULL,
  INDEX idx_bulletin_comments_post(post_id,created_at),
  FOREIGN KEY (post_id) REFERENCES bulletin_posts(id), FOREIGN KEY (author_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS sla_settings (
  reminder_type VARCHAR(40) PRIMARY KEY, days_before INT NOT NULL, label_ja VARCHAR(120) NOT NULL,
  label_zh VARCHAR(120) NOT NULL
);
"""

TABLES = [
    *rental.RENTAL_RESET_TABLES,
    "user_preferences", "bulletin_comments", "bulletin_posts", "calendar_events",
    "audit_logs", "daily_report_drafts", "export_jobs", "import_row_results",
    "import_jobs", "external_record_mappings", "month_closes", "month_close_period_locks", "expenses",
    "referral_document_generations", "referral_documents", "referral_document_files",
    "data_correction_requests", "tasks", "data_disclosures", "consents", "referral_disputes",
    "fee_entitlements", "construction_projects", "contracts", "negotiations", "introductions",
    "partner_agreements", "fee_rules", "partner_staff", "partners", "stage_events", "activities",
    "touches", "persons", "households", "users", "stores", "seed_metadata", "sla_settings",
]

STORES = [
    ("店舗A", "東京"), ("店舗B", "東京"), ("店舗C", "東京"), ("店舗D", "神奈川"),
    ("店舗E", "神奈川"), ("店舗F", "埼玉"), ("店舗G", "千葉"), ("店舗H", "千葉"),
    ("店舗I", "愛知"), ("店舗J", "大阪"), ("店舗K", "兵庫"), ("店舗L", "福岡"),
]
STAGES = ["新規予約", "初回相談済", "FP診断済", "紹介済", "訪問・商談中", "契約", "着工", "完了・見送り"]
SEED_BATCH = "mallboard-demo-2026-11-full-v2"
SAMPLE_SURNAMES = ["佐藤", "田中", "鈴木", "高橋", "伊藤", "渡辺", "山本", "中村", "小林", "加藤", "吉田", "山田"]
SAMPLE_SURNAMES_KANA = ["サトウ", "タナカ", "スズキ", "タカハシ", "イトウ", "ワタナベ", "ヤマモト", "ナカムラ", "コバヤシ", "カトウ", "ヨシダ", "ヤマダ"]
JST = ZoneInfo("Asia/Tokyo")
SESSION_COOKIE = "mallboard_session"
LEGACY_ROLE_ALIASES = ("advisor", "manager", "hq_finance", "executive", "hr")
ACCOUNT_ROLES = {
    "executive": "executive", "administrator": "executive", "hq_staff": "hq_finance",
    "store_manager": "manager", "advisor": "advisor", "finance": "hq_finance", "hr": "hr", "owner": "owner",
}

SYSTEM_CONFIG_DEFAULTS = {
    "auth.password_min_length": 12,
    "auth.password_require_uppercase": True,
    "auth.password_require_lowercase": True,
    "auth.password_require_number": True,
    "auth.password_require_symbol": True,
    "auth.password_history_count": 5,
    "auth.login_max_failed_attempts": 5,
    "auth.login_lock_duration_minutes": 15,
    "auth.login_rate_limit_count": 10,
    "auth.login_rate_limit_window_minutes": 15,
    "auth.session_idle_timeout_minutes": 30,
    "auth.session_absolute_timeout_hours": 12,
    "auth.password_reset_link_ttl_minutes": 30,
    "fee_rule.applicability_basis": "contract_date",
    "fee.bank_fee_tolerance_yen": 1000,
    "expense.approval_thresholds_yen": [10000, 50000],
    "expense.allowed_categories": ["交通費", "消耗品費", "会議費"],
    "retention.interview_online_years": 3,
    "retention.interview_archive_years": 5,
    "retention.daily_report_years": 3,
    "retention.monthly_report_years": 5,
    "retention.month_close_snapshot_years": 7,
    "retention.audit_years": 5,
    "attachment.allowed_extensions": ["pdf", "jpg", "jpeg", "png", "csv"],
    "attachment.max_file_mb": 10,
    "import.max_csv_rows": 50000,
    "import.max_csv_mb": 10,
    "export.max_rows": 5000,
    "export.max_csv_mb": 10,
    "export.max_pdf_mb": 10,
    "export.expiry_hours": 24,
    "pdf.render_concurrency": 1,
    "pdf.render_max_pending": 1,
    "pdf.render_timeout_seconds": 45,
    # Provisional demo policy; production validity and consent wording require company approval.
    "pdf.referral_validity_days": 30,
    "construction.expected_start_months": 6,
    "search.alert_queries_per_minute": 30,
    "notification.email_retry_minutes": [1, 5, 15],
    "notification.quiet_hours": {"start": "21:00", "end": "07:00"},
    "calendar.retry_minutes": [1, 5, 15, 60],
    "calendar.max_retries": 4,
    "finance.sync_interval_minutes": 60,
    "finance.summary_stale_after_minutes": 120,
    "task.followup_sla_days": 3,
    "task.partner_feedback_sla_days": 5,
    "task.construction_evidence_sla_days": 7,
    # Provisional demo defaults; final SLA days require company confirmation.
    "sla.introduction_validity_days": 30,
    "sla.construction_evidence_days": 7,
    "sla.dispute_resolution_days": 14,
    "sla.agreement_renewal_days": 30,
    "sla.fee_rule_validity_days": 30,
    "month_close.lock_working_day": 5,
    "month_close.locked_resources": [
        "expenses", "fee_entitlements", "contracts", "construction_projects",
        "activities", "introductions", "stage_events",
    ],
    "expense.max_receipt_mb": 10,
}

SYSTEM_CONFIG_RANGES = {
    "auth.password_min_length": (8, 128),
    "auth.password_history_count": (0, 20),
    "auth.login_max_failed_attempts": (1, 20),
    "auth.login_lock_duration_minutes": (1, 1440),
    "auth.login_rate_limit_count": (1, 1000),
    "auth.login_rate_limit_window_minutes": (1, 1440),
    "auth.session_idle_timeout_minutes": (1, 1440),
    "auth.session_absolute_timeout_hours": (1, 168),
    "auth.password_reset_link_ttl_minutes": (1, 1440),
    "fee.bank_fee_tolerance_yen": (0, 100000),
    "retention.interview_online_years": (1, 10),
    "retention.interview_archive_years": (1, 20),
    "retention.daily_report_years": (1, 10),
    "retention.monthly_report_years": (1, 20),
    "retention.month_close_snapshot_years": (1, 20),
    "retention.audit_years": (1, 20),
    "attachment.max_file_mb": (1, 100),
    "import.max_csv_rows": (1, 50000),
    "import.max_csv_mb": (1, 100),
    "export.max_rows": (1, 50000),
    "export.max_csv_mb": (1, 100),
    "export.max_pdf_mb": (1, 100),
    "export.expiry_hours": (1, 720),
    "pdf.render_concurrency": (1, 4),
    "pdf.render_max_pending": (0, 8),
    "pdf.render_timeout_seconds": (5, 120),
    "pdf.referral_validity_days": (1, 365),
    "construction.expected_start_months": (1, 24),
    "search.alert_queries_per_minute": (1, 10000),
    "calendar.max_retries": (1, 4),
    "finance.sync_interval_minutes": (5, 1440),
    "finance.summary_stale_after_minutes": (5, 10080),
    "task.followup_sla_days": (0, 365),
    "task.partner_feedback_sla_days": (0, 365),
    "task.construction_evidence_sla_days": (0, 365),
    "sla.introduction_validity_days": (0, 365),
    "sla.construction_evidence_days": (0, 365),
    "sla.dispute_resolution_days": (0, 365),
    "sla.agreement_renewal_days": (0, 365),
    "sla.fee_rule_validity_days": (0, 365),
    "month_close.lock_working_day": (1, 10),
    "expense.max_receipt_mb": (1, 100),
}


def connect():
    return Database(pymysql.connect(**DB_CONFIG))


def now_jst():
    return datetime.now(JST).replace(tzinfo=None)


def normalize_kana(value):
    normalized = unicodedata.normalize("NFKC", value or "")
    return "".join(chr(ord(char) + 0x60) if "ぁ" <= char <= "ゖ" else char
                   for char in normalized)


def construction_confirmation_backlog(db, store_id=None):
    sql = """SELECT COUNT(DISTINCT cp.id) AS count FROM construction_projects cp
             JOIN contracts c ON c.id=cp.contract_id
             JOIN negotiations n ON n.id=c.negotiation_id
             JOIN introductions i ON i.id=n.introduction_id
             JOIN households h ON h.id=i.household_id
             WHERE cp.planned_start_date<CURRENT_DATE AND cp.confirmed_start_date IS NULL"""
    args = ()
    if store_id is not None:
        sql += " AND h.store_id=?"
        args = (store_id,)
    return int(db.execute(sql, args).fetchone()["count"])


def demo_mode_enabled():
    return os.getenv("DEMO_MODE", "false").strip().lower() == "true"


def public_sample_mode_enabled():
    return os.getenv("PUBLIC_SAMPLE_MODE", "false").strip().lower() == "true"


SAMPLE_GUEST_EMPLOYEE_CODE = os.getenv("SAMPLE_GUEST_EMPLOYEE_CODE", "EX-01")
SAMPLE_BLOCK_MESSAGE = "公開サンプルではこの操作はできません（表示データはすべて架空で、毎日自動リセットされます）"

def sample_or_demo_enabled():
    return demo_mode_enabled() or public_sample_mode_enabled()


# Public sample API classification. Exact method/path pairs cover shell reads,
# authentication, reset and shared infrastructure. Only rental is a prefix.
# Every other API route (including legacy business APIs and admin writes) is 410.
_SAMPLE_EXACT = {
    "GET": {
        "/api/health", "/api/public-config", "/api/bootstrap", "/api/auth/demo-accounts",
        "/api/notifications", "/api/calendar", "/api/bulletin", "/api/audit-events",
        "/api/system-config", "/api/accounts", "/api/operations/status",
        "/api/month-closes", "/api/month-closes/lock-matrix",
    },
    "POST": {
        "/api/auth/login", "/api/auth/logout", "/api/auth/demo-login", "/api/auth/guest-login",
        "/api/reset", "/api/calendar",
    },
    "PUT": {"/api/preferences"},
}
_SAMPLE_PARAMETERIZED = {
    "GET": re.compile(r"/api/audit-events/[^/]+"),
    "PUT": re.compile(r"/api/(?:notifications/[^/]+/(?:read|archive)|calendar/[^/]+)"),
}
_SAMPLE_WRITES = {"POST", "PUT", "PATCH", "DELETE"}


def sample_route_allowed(method, raw_path):
    path = raw_path.removesuffix("/")
    pattern = _SAMPLE_PARAMETERIZED.get(method)
    return (
        raw_path.startswith("/api/rental/")
        or path in _SAMPLE_EXACT.get(method, ())
        or (pattern is not None and pattern.fullmatch(path) is not None)
    )


_SAMPLE_BLOCKED = [
    ({"POST", "PUT", "PATCH", "DELETE"}, r"^/api/bulletin(/.*)?$"),
    ({"POST"}, r"^/api/expenses$"),
    ({"PUT"}, r"^/api/expenses/\d+$"),
    ({"POST"}, r"^/api/expenses/\d+/receipt$"),
    ({"POST"}, r"^/api/households/\d+/disclosures$"),
    ({"POST"}, r"^/api/households/\d+/data-corrections$"),
    ({"POST"}, r"^/api/data-corrections/[^/]+/decision$"),
    ({"POST"}, r"^/api/introductions/\d+/dispute$"),
    ({"POST"}, r"^/api/referral-disputes/[^/]+/decision$"),
    ({"POST"}, r"^/api/introductions/\d+/referral-documents$"),
    ({"POST"}, r"^/api/referral-documents/cleanup$"),
    ({"POST"}, r"^/api/consents/[^/]+/revoke$"),
    ({"POST"}, r"^/api/month-closes(/.*)?$"),
    ({"PUT"}, r"^/api/system-config/[^/]+$"),
    ({"PUT"}, r"^/api/accounts/\d+/(status|role)$"),
    ({"POST"}, r"^/api/export-jobs$"),
    ({"POST"}, r"^/api/imports(/.*)?$"),
    ({"POST"}, r"^/api/auth/change-password$"),
    ({"POST"}, r"^/api/auth/password-reset-requests$"),
    ({"POST"}, r"^/api/auth/password-reset$"),
    ({"POST"}, r"^/api/reset$"),
]

_SAMPLE_NEUTRALIZE = [
    ("POST", r"^/api/activities$", {"body": "サンプル活動メモ",
                                    "next_action": lambda v: "フォローアップ" if v else v}),
    ("POST", r"^/api/calendar$", {"title": "サンプル予定"}),
    ("PUT", r"^/api/calendar/[^/]+$", {"title": "サンプル予定"}),
    ("POST", r"^/api/introductions/\d+/referral-consent$", {"evidence_reference": "サンプル確認済"}),
    ("PUT", r"^/api/report$", {"manual_note": ""}),
    ("POST", r"^/api/expenses/\d+/(approve|reject)$", {"reason": None}),
]


class SampleGuardMiddleware:
    """Serialize demo resets and apply the public-sample API guards."""

    def __init__(self, app):
        self.app = app
        self.resetting = False
        self.reset_failed = False
        self.active_requests = 0
        self.idle = asyncio.Event()
        self.idle.set()
        self.write_windows = OrderedDict()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not sample_or_demo_enabled():
            await self.app(scope, receive, send)
            return
        method = scope["method"]
        raw_path = scope["path"]
        if not raw_path.startswith("/api/"):
            await self.app(scope, receive, send)
            return
        path = raw_path.removesuffix("/")
        public_sample = public_sample_mode_enabled()
        if self.reset_failed:
            await JSONResponse({"detail": "サンプルデータのリセットに失敗しました"},
                               status_code=503)(scope, receive, send)
            return
        if public_sample and not sample_route_allowed(method, raw_path):
            await JSONResponse({"detail": SAMPLE_BLOCK_MESSAGE}, status_code=410)(scope, receive, send)
            return
        if self.resetting:
            await JSONResponse({"detail": "サンプルデータをリセット中です"}, status_code=409)(scope, receive, send)
            return
        if path == "/api/reset" and method == "POST":
            if public_sample:
                presented = Request(scope).headers.get("x-sample-reset-token", "")
                expected = os.getenv("SAMPLE_RESET_TOKEN", "")
                if not presented or not expected or not hmac.compare_digest(presented.encode(), expected.encode()):
                    await JSONResponse({"detail": SAMPLE_BLOCK_MESSAGE}, status_code=422)(scope, receive, send)
                    return
            scope.setdefault("state", {})["sample_guard"] = self
            self.resetting = True
            try:
                await self.idle.wait()
                await self.app(scope, receive, send)
            finally:
                if not self.reset_failed:
                    self.resetting = False
            return
        if public_sample and method in _SAMPLE_WRITES and not path.startswith("/api/auth/"):
            if not self.allow_write(Request(scope)):
                await JSONResponse({"detail": "書き込み回数の上限に達しました"},
                                   status_code=429)(scope, receive, send)
                return
        self.active_requests += 1
        self.idle.clear()
        try:
            if public_sample:
                await self.guard_request(scope, receive, send, method, path)
            else:
                await self.app(scope, receive, send)
        finally:
            self.active_requests -= 1
            if not self.active_requests:
                self.idle.set()

    def allow_write(self, request):
        now = time.monotonic()
        cutoff = now - 60
        # Windows are ordered by their most recent accepted write.
        while self.write_windows and next(iter(self.write_windows.values()))[-1] <= cutoff:
            self.write_windows.popitem(last=False)
        token = request.cookies.get(SESSION_COOKIE)
        key = ("session", token) if token else ("ip", request.client.host if request.client else None)
        window = self.write_windows.setdefault(key, deque())
        while window and window[0] <= cutoff:
            window.popleft()
        if len(window) >= 60:
            return False
        window.append(now)
        self.write_windows.move_to_end(key)
        return True

    async def guard_request(self, scope, receive, send, method, path):
        if method not in _SAMPLE_WRITES:
            await self.app(scope, receive, send)
            return
        for methods, pattern in _SAMPLE_BLOCKED:
            if method in methods and re.match(pattern, path):
                response = JSONResponse({"detail": SAMPLE_BLOCK_MESSAGE}, status_code=422)
                await response(scope, receive, send)
                return
        for rule_method, pattern, fields in _SAMPLE_NEUTRALIZE:
            if method == rule_method and re.match(pattern, path):
                body = b""
                while True:
                    message = await receive()
                    if message["type"] == "http.request":
                        body += message.get("body", b"")
                        if not message.get("more_body"):
                            break
                    elif message["type"] == "http.disconnect":
                        break
                try:
                    payload = json.loads(body or b"{}")
                except (ValueError, TypeError):
                    payload = None
                if isinstance(payload, dict):
                    for field, replacement in fields.items():
                        if field in payload:
                            payload[field] = (replacement(payload[field])
                                              if callable(replacement) else replacement)
                    body = json.dumps(payload).encode("utf-8")
                headers = [(k, v) for k, v in scope.get("headers") or []
                           if k.lower() != b"content-length"]
                headers.append((b"content-length", str(len(body)).encode("ascii")))
                scope = dict(scope)
                scope["headers"] = headers
                replayed = False

                async def replay_receive():
                    nonlocal replayed
                    if not replayed:
                        replayed = True
                        return {"type": "http.request", "body": body, "more_body": False}
                    return await receive()

                await self.app(scope, replay_receive, send)
                return
        await self.app(scope, receive, send)


app.add_middleware(SampleGuardMiddleware)


def hash_secret(secret):
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(secret.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${derived.hex()}"


def verify_secret(secret, encoded):
    try:
        algorithm, salt_hex, digest_hex = encoded.split("$", 2)
        if algorithm != "scrypt":
            return False
        derived = hashlib.scrypt(secret.encode("utf-8"), salt=bytes.fromhex(salt_hex),
                                 n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(derived.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def token_digest(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def config_value(db, key):
    row = db.execute("SELECT value_json FROM system_configs WHERE config_key=?", (key,)).fetchone()
    if not row:
        return SYSTEM_CONFIG_DEFAULTS[key]
    return json.loads(row["value_json"]) if isinstance(row["value_json"], str) else row["value_json"]


def assert_month_period_open(db, event_date, resource):
    if resource not in config_value(db, "month_close.locked_resources"):
        return
    if isinstance(event_date, datetime):
        event_date = event_date.date()
    if isinstance(event_date, str):
        try:
            event_date = date.fromisoformat(event_date[:10])
        except ValueError as error:
            raise HTTPException(422, "日付はYYYY-MM-DD形式で指定してください") from error
    period = event_date.strftime("%Y-%m")
    close = db.execute(
        """SELECT id,status FROM month_closes WHERE period=? AND status IN ('CLOSED','REOPEN_REQUESTED')
           ORDER BY snapshot_version DESC LIMIT 1""",
        (period,),
    ).fetchone()
    if close:
        raise HTTPException(423, f"{period} は月次締め済みで、{resource} は変更できません")


def build_month_snapshot(db, period):
    start = datetime.strptime(period, "%Y-%m").date().replace(day=1)
    if start.month == 12:
        end = date(start.year + 1, 1, 1)
    else:
        end = date(start.year, start.month + 1, 1)
    contracts = db.execute(
        """SELECT COUNT(*) AS count,COALESCE(SUM(contract_amount),0) AS amount
           FROM contracts WHERE contract_date>=? AND contract_date<?""",
        (start, end),
    ).fetchone()
    expense_rows = db.execute(
        """SELECT status,COUNT(*) AS count,COALESCE(SUM(amount),0) AS amount
           FROM expenses WHERE expense_date>=? AND expense_date<? GROUP BY status ORDER BY status""",
        (start, end),
    ).fetchall()
    fee_rows = db.execute(
        """SELECT state,COUNT(*) AS count,COALESCE(SUM(calculated_amount),0) AS amount
           FROM fee_entitlements WHERE calculated_at>=? AND calculated_at<?
           GROUP BY state ORDER BY state""",
        (start, end),
    ).fetchall()
    construction_rows = db.execute(
        """SELECT confirmation_status,COUNT(*) AS count
           FROM construction_projects WHERE confirmed_start_date>=? AND confirmed_start_date<?
           GROUP BY confirmation_status ORDER BY confirmation_status""",
        (start, end),
    ).fetchall()
    return {
        "period": period,
        "range_start": start.isoformat(),
        "range_end_exclusive": end.isoformat(),
        "generated_at": now_jst().isoformat(timespec="seconds"),
        "contracts": {"count": contracts["count"], "contract_amount": int(contracts["amount"] or 0)},
        "expenses": [
            {"status": row["status"], "count": row["count"], "amount": int(row["amount"] or 0)}
            for row in expense_rows
        ],
        "fee_entitlements": [
            {"state": row["state"], "count": row["count"], "amount": int(row["amount"] or 0)}
            for row in fee_rows
        ],
        "construction_confirmations": [dict(row) for row in construction_rows],
    }


class CurrentActor(str):
    def __new__(cls, account_role, user_id, store_id):
        legacy_role = ACCOUNT_ROLES.get(account_role)
        actor = super().__new__(cls, legacy_role or account_role)
        actor.user_id = int(user_id)
        actor.account_role = account_role
        actor.store_id = store_id
        return actor


async def require_actor(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(401, "認証が必要です")
    now = now_jst()
    with connect() as db:
        idle_timeout = config_value(db, "auth.session_idle_timeout_minutes")
        row = db.execute(
            """SELECT s.id AS session_id,s.expires_at,s.last_seen_at,u.id,u.role,u.store_id,
                      u.account_status,u.must_change_password
               FROM auth_sessions s JOIN users u ON u.id=s.user_id
               WHERE s.token_hash=? AND s.revoked_at IS NULL""",
            (token_digest(token),),
        ).fetchone()
        if not row or row["account_status"] != "ACTIVE":
            raise HTTPException(401, "認証が必要です")
        idle_limit = now - timedelta(minutes=idle_timeout)
        if row["expires_at"] <= now or row["last_seen_at"] < idle_limit:
            db.execute("UPDATE auth_sessions SET revoked_at=? WHERE id=?", (now, row["session_id"]))
            db.commit()
            raise HTTPException(401, "認証が必要です")
        if row["role"] == "owner" and request.url.path not in (
                "/api/bootstrap", "/api/auth/logout", "/api/notifications"):
            if not request.url.path.startswith("/api/rental/"):
                raise HTTPException(403, "オーナーアカウントからこの操作はできません")
        if row["must_change_password"] and request.url.path not in (
                "/api/bootstrap", "/api/auth/change-password", "/api/auth/logout"):
            raise HTTPException(403, "初回ログイン時にパスワードを変更してください")
        db.execute("UPDATE auth_sessions SET last_seen_at=? WHERE id=?", (now, row["session_id"]))
        request.state.actor = dict(row)
        return CurrentActor(row["role"], row["id"], row["store_id"])


def create_session(db, user_id, request):
    token = secrets.token_urlsafe(48)
    now = now_jst()
    timeout_hours = config_value(db, "auth.session_absolute_timeout_hours")
    session_id = str(uuid.uuid4())
    ua = request.headers.get("user-agent", "")
    db.execute(
        """INSERT INTO auth_sessions(id,user_id,token_hash,created_at,last_seen_at,expires_at,
           source_ip,user_agent_hash) VALUES(?,?,?,?,?,?,?,?)""",
        (session_id, user_id, token_digest(token), now, now,
         now + timedelta(hours=timeout_hours),
         request.client.host if request.client else None,
         hashlib.sha256(ua.encode("utf-8")).hexdigest()),
    )
    return token


def set_session_cookie(request: Request, response: Response, token: str, max_age_hours):
    response.set_cookie(SESSION_COOKIE, token, httponly=True, secure=request.url.scheme == "https",
                        samesite="lax", max_age=max_age_hours * 3600, path="/")


SLA_CONFIG = [
    ("introduction_validity", "sla.introduction_validity_days", "紹介有効期間", "介绍有效期"),
    ("construction_evidence", "sla.construction_evidence_days", "着工証拠提出期限", "开工证据提交期限"),
    ("dispute_resolution", "sla.dispute_resolution_days", "争議処理期限", "争议处理期限"),
    ("agreement_renewal", "sla.agreement_renewal_days", "提携契約更新期限", "合作协议续约期限"),
    ("fee_rule_validity", "sla.fee_rule_validity_days", "FeeRule適用期限", "FeeRule 适用期限"),
]


class Row(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


class Cursor:
    def __init__(self, cursor):
        self.cursor = cursor

    def fetchone(self):
        row = self.cursor.fetchone()
        return Row(row) if row is not None else None

    def fetchall(self):
        return [Row(row) for row in self.cursor.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())

    @property
    def lastrowid(self):
        return self.cursor.lastrowid

    @property
    def rowcount(self):
        return self.cursor.rowcount


class Database:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, query, params=()):
        cursor = self.connection.cursor()
        cursor.execute(query.replace("?", "%s"), params)
        return Cursor(cursor)

    def executemany(self, query, params):
        cursor = self.connection.cursor()
        cursor.executemany(query.replace("?", "%s"), params)
        return Cursor(cursor)

    def executescript(self, script):
        for statement in script.split(";"):
            if statement.strip():
                self.execute(statement)

    def commit(self):
        self.connection.commit()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self.connection.commit()
        else:
            self.connection.rollback()
        self.connection.close()


def audit(db, user_id, action, target_type, target_id, detail):
    actor = db.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone() if user_id else None
    event_at = now_jst().isoformat(timespec="seconds")
    numeric_target_id = target_id if type(target_id) is int else None
    text_target_id = str(target_id) if target_id is not None and numeric_target_id is None else None
    previous_hash = db.execute(
        "SELECT last_hash FROM audit_chain WHERE id=1 FOR UPDATE"
    ).fetchone()
    previous_hash = previous_hash["last_hash"] if previous_hash else "0" * 64
    event = {
        "actor_id": user_id,
        "actor_role": actor["role"] if actor else "system",
        "action": action,
        "object_type": target_type,
        "object_id": numeric_target_id,
        "reason": detail,
        "event_at": event_at,
        "previous_hash": previous_hash,
    }
    if text_target_id is not None:
        event["object_id_text"] = text_target_id
    event_hash = hashlib.sha256(
        (previous_hash + json.dumps(event, ensure_ascii=False, sort_keys=True)).encode("utf-8")
    ).hexdigest()
    db.execute(
        """INSERT INTO audit_logs(user_id,action,target_type,target_id,target_id_text,`at`,detail)
           VALUES(?,?,?,?,?,?,?)""",
        (user_id, action, target_type, numeric_target_id, text_target_id, event_at, detail),
    )
    event_row = db.execute(
        """INSERT INTO audit_events(actor_id,actor_role,action,object_type,object_id,reason,event_at,
           object_id_text,previous_hash,event_hash,event_type,result) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (user_id, event["actor_role"], action, target_type, numeric_target_id, detail, event_at,
         text_target_id,
         previous_hash, event_hash, action.upper().replace(".", "_"), "SUCCEEDED"),
    )
    db.execute("UPDATE audit_chain SET last_hash=? WHERE id=1", (event_hash,))
    aggregate_id = f"{target_type}:{target_id if target_id is not None else user_id or 'system'}"
    sequence = db.execute(
        "SELECT COALESCE(MAX(sequence_no),0)+1 AS next_sequence FROM audit_outbox WHERE aggregate_id=? FOR UPDATE",
        (aggregate_id,),
    ).fetchone()["next_sequence"]
    db.execute(
        """INSERT INTO audit_outbox(id,event_type,aggregate_id,sequence_no,payload_hash,status,
           attempt_count,created_at) VALUES(?,?,?,?,?,'PENDING',0,?)""",
        (str(uuid.uuid4()), action.upper().replace(".", "_"), aggregate_id, sequence, event_hash, event_at),
    )
    return event_row.lastrowid


def audit_visibility_clause(actor):
    account_role = getattr(actor, "account_role", "")
    if account_role in ("administrator", "executive", "hr"):
        return "1=1", []
    if account_role == "store_manager" and actor.store_id:
        return "actor_id IN (SELECT id FROM users WHERE store_id=?)", [actor.store_id]
    return "actor_id=?", [actor.user_id]


@app.get("/api/audit-events")
def audit_event_list(limit: int = 50, before_id: Optional[int] = None,
                     actor: CurrentActor = Depends(require_actor)):
    if not 1 <= limit <= 100:
        raise HTTPException(422, "取得件数は1から100まで指定してください")
    visibility, args = audit_visibility_clause(actor)
    conditions = [visibility]
    if before_id is not None:
        conditions.append("id<?")
        args.append(before_id)
    with connect() as db:
        rows = db.execute(
            f"""SELECT id,actor_id,actor_role,action,object_type,object_id,object_id_text,reason,event_at,
                       event_type,result,error_code FROM audit_events
                WHERE {' AND '.join(conditions)} ORDER BY id DESC LIMIT ?""",
            (*args, limit),
        ).fetchall()
    return {"items": [dict(row) for row in rows]}


@app.get("/api/audit-events/{event_id}")
def audit_event_detail(event_id: int, actor: CurrentActor = Depends(require_actor)):
    visibility, args = audit_visibility_clause(actor)
    with connect() as db:
        row = db.execute(
            f"""SELECT id,actor_id,actor_role,action,object_type,object_id,object_id_text,reason,event_at,
                       event_type,before_hash,after_hash,previous_hash,event_hash,request_id,result,error_code
                FROM audit_events WHERE id=? AND {visibility}""",
            (event_id, *args),
        ).fetchone()
        if not row:
            raise HTTPException(404, "監査イベントが見つかりません")
    return dict(row)


def create_notification(db, user_id, notification_type, title, message, related_type=None,
                        related_id=None, event_code=None, title_zh=None, message_zh=None):
    allowed_types = {
        "TASK", "APPROVAL", "EXPENSE", "DAILY_REPORT", "IMPORT", "MONTHLY_CLOSE",
        "DOCUMENT", "EXPORT", "DATA_CORRECTION", "SECURITY", "SYSTEM",
    }
    if notification_type not in allowed_types:
        raise ValueError(f"Unsupported notification type: {notification_type}")
    if notification_type == "SYSTEM" and not event_code:
        raise ValueError("SYSTEM notifications require a system_event_code")
    notification_id = str(uuid.uuid4())
    now = now_jst()
    preference = db.execute(
        "SELECT notification_preferences FROM user_preferences WHERE user_id=?", (user_id,)
    ).fetchone()
    preferences = preference["notification_preferences"] if preference else {"in_app": True, "email": False}
    if isinstance(preferences, str):
        preferences = json.loads(preferences)
    if preferences.get("in_app", True):
        db.execute(
            """INSERT INTO notifications(id,user_id,notification_type,system_event_code,title,title_zh,
               message,message_zh,related_record_type,related_record_id,status,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?, 'UNREAD',?)""",
            (notification_id, user_id, notification_type, event_code, title, title_zh,
             message, message_zh,
             related_type, str(related_id) if related_id is not None else None, now),
        )
        db.execute(
            """INSERT INTO notification_deliveries(id,notification_id,channel,delivery_status,
               attempt_count,sent_at) VALUES(?,?,'IN_APP','DELIVERED',1,?)""",
            (str(uuid.uuid4()), notification_id, now),
        )
    email_requested = bool(preferences.get("email", False))
    if not preferences.get("in_app", True) or email_requested:
        related_household_id = None
        if related_type == "household" and str(related_id or "").isdigit():
            related_household_id = int(related_id)
        elif related_type == "introduction":
            row = db.execute("SELECT household_id FROM introductions WHERE id=?", (related_id,)).fetchone()
            related_household_id = row["household_id"] if row else None
        elif related_type == "fee_entitlement":
            row = db.execute(
                """SELECT i.household_id FROM fee_entitlements fe JOIN introductions i
                   ON i.id=fe.introduction_id WHERE fe.id=?""", (related_id,),
            ).fetchone()
            related_household_id = row["household_id"] if row else None
        elif related_type == "construction_project":
            row = db.execute(
                """SELECT i.household_id FROM construction_projects cp JOIN contracts c ON c.id=cp.contract_id
                   JOIN negotiations n ON n.id=c.negotiation_id
                   JOIN introductions i ON i.id=n.introduction_id WHERE cp.id=?""", (related_id,),
            ).fetchone()
            related_household_id = row["household_id"] if row else None
        task_id = db.execute(
            """INSERT INTO tasks(assignee_id,title,due_at,source,related_household_id,task_type,
               priority,related_type,related_id) VALUES(?,?,?,'notification_fallback',?,
               'notification_fallback','high',?,?)""",
            (user_id, f"通知対応: {title}"[:255], now.date(), related_household_id,
             related_type or "notification",
             int(related_id) if str(related_id or "").isdigit() else None),
        ).lastrowid
        if email_requested and preferences.get("in_app", True):
            db.execute(
                """INSERT INTO notification_deliveries(id,notification_id,channel,delivery_status,
                   attempt_count,last_error,sent_at) VALUES(?,?,'EMAIL','FALLBACK_TASK',0,
                   'EMAIL_NOT_CONFIGURED',?)""",
                (str(uuid.uuid4()), notification_id, now),
            )
        return task_id
    return notification_id


def process_audit_outbox(batch_size=50, max_attempts=5):
    now = now_jst()
    processed = 0
    with connect() as db:
        rows = db.execute(
            """SELECT id,event_type,aggregate_id,sequence_no,payload_hash,attempt_count
               FROM audit_outbox
               WHERE status='PENDING' AND (next_retry_at IS NULL OR next_retry_at<=?)
               ORDER BY aggregate_id,sequence_no LIMIT ? FOR UPDATE SKIP LOCKED""",
            (now, batch_size),
        ).fetchall()
        for row in rows:
            previous = db.execute(
                """SELECT status FROM audit_outbox WHERE aggregate_id=? AND sequence_no<?
                   ORDER BY sequence_no DESC LIMIT 1""",
                (row["aggregate_id"], row["sequence_no"]),
            ).fetchone()
            if previous and previous["status"] != "COMPLETED":
                continue
            event = db.execute(
                "SELECT event_hash FROM audit_events WHERE event_hash=?",
                (row["payload_hash"],),
            ).fetchone()
            if event:
                db.execute(
                    """UPDATE audit_outbox SET status='COMPLETED',attempt_count=attempt_count+1,
                       next_retry_at=NULL,error_code=NULL WHERE id=? AND status='PENDING'""",
                    (row["id"],),
                )
                processed += 1
                continue

            attempts = row["attempt_count"] + 1
            dead_letter = attempts >= max_attempts
            retry_at = None if dead_letter else now + timedelta(seconds=min(2 ** attempts, 300))
            db.execute(
                """UPDATE audit_outbox SET status=?,attempt_count=?,next_retry_at=?,error_code=?
                   WHERE id=? AND status='PENDING'""",
                ("DEAD_LETTER" if dead_letter else "PENDING", attempts, retry_at,
                 "AUDIT_EVENT_NOT_FOUND", row["id"]),
            )
            if dead_letter:
                recipients = db.execute(
                    "SELECT id FROM users WHERE role IN ('administrator','executive') AND account_status='ACTIVE'"
                ).fetchall()
                for recipient in recipients:
                    create_notification(
                        db, recipient["id"], "SYSTEM", "Audit outbox dead letter",
                        f"監査イベントの配信検証に失敗しました: {row['id']}",
                        "audit_outbox", row["id"], "AUDIT_OUTBOX_DEAD_LETTER",
                        title_zh="审计事件已进入死信队列",
                        message_zh=f"审计事件投递校验失败：{row['id']}",
                    )
    return processed


async def audit_outbox_worker():
    while True:
        try:
            await asyncio.to_thread(process_audit_outbox)
        except Exception:
            LOGGER.exception("Audit outbox processing failed; pending events will be retried.")
        await asyncio.sleep(5)


@app.on_event("startup")
async def start_audit_outbox_worker():
    app.state.audit_outbox_task = asyncio.create_task(audit_outbox_worker())


@app.on_event("shutdown")
async def stop_audit_outbox_worker():
    task = getattr(app.state, "audit_outbox_task", None)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def validate_password(db, password):
    if len(password) < config_value(db, "auth.password_min_length"):
        raise HTTPException(422, "パスワードの長さが要件を満たしていません")
    checks = (
        ("auth.password_require_uppercase", lambda value: any(c.isupper() for c in value)),
        ("auth.password_require_lowercase", lambda value: any(c.islower() for c in value)),
        ("auth.password_require_number", lambda value: any(c.isdigit() for c in value)),
        ("auth.password_require_symbol", lambda value: any(not c.isalnum() for c in value)),
    )
    for key, check in checks:
        if config_value(db, key) and not check(password):
            raise HTTPException(422, "パスワードが設定済みポリシーを満たしていません")


def privileged_account_management(actor):
    if getattr(actor, "account_role", None) not in ("administrator", "hr"):
        raise HTTPException(403, "この操作を行う権限がありません")


class DemoLoginInput(BaseModel):
    account_id: int


class PasswordLoginInput(BaseModel):
    employee_code: str
    password: str


class PasswordResetRequestInput(BaseModel):
    user_id: int
    verification_method: str


class PasswordResetCompleteInput(BaseModel):
    reset_token: str
    new_password: str


class ChangePasswordInput(BaseModel):
    current_password: Optional[str] = None
    new_password: str


@app.get("/api/auth/demo-accounts")
def demo_accounts(request: Request):
    if not sample_or_demo_enabled():
        with connect() as db:
            audit(db, None, "demo.login.disabled", "security", None,
                  json.dumps({"source_ip": request.client.host if request.client else None,
                              "user_agent": request.headers.get("user-agent", "")[:200]}))
            db.commit()
        raise HTTPException(403, "デモモードは無効です")
    with connect() as db:
        return {"accounts": [
            {"id": row["id"], "employee_code": row["employee_code"], "display_name": row["display_name"],
             "role": row["role"], "store_id": row["store_id"]}
            for row in db.execute(
                "SELECT id,employee_code,display_name,role,store_id FROM users "
                "WHERE account_status='ACTIVE' ORDER BY role,store_id,employee_code"
            )
        ]}


@app.post("/api/auth/demo-login")
def demo_login(payload: DemoLoginInput, request: Request, response: Response):
    if not sample_or_demo_enabled():
        with connect() as db:
            audit(db, None, "demo.login.disabled", "security", None,
                  json.dumps({"source_ip": request.client.host if request.client else None,
                              "user_agent": request.headers.get("user-agent", "")[:200]}))
            db.commit()
        raise HTTPException(403, "デモモードは無効です")
    with connect() as db:
        user = db.execute(
            "SELECT id,role,store_id,account_status FROM users WHERE id=?", (payload.account_id,)
        ).fetchone()
        if not user or user["account_status"] != "ACTIVE":
            raise HTTPException(401, "認証が必要です")
        previous = request.cookies.get(SESSION_COOKIE)
        if previous:
            db.execute("UPDATE auth_sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL",
                       (now_jst(), token_digest(previous)))
        db.execute("UPDATE users SET last_login_at=? WHERE id=?", (now_jst(), user["id"]))
        token = create_session(db, user["id"], request)
        audit(db, user["id"], "DEMO_ROLE_SWITCH", "user", user["id"],
              json.dumps({"role": user["role"], "source_ip": request.client.host if request.client else None,
                          "user_agent": request.headers.get("user-agent", "")[:200]}))
        account = {"id": user["id"], "role": user["role"], "store_id": user["store_id"]}
        session_hours = config_value(db, "auth.session_absolute_timeout_hours")
    set_session_cookie(request, response, token, session_hours)
    return {"ok": True, "account": account}


@app.get("/api/public-config")
def public_config():
    return {"demo": demo_mode_enabled(), "public_sample": public_sample_mode_enabled()}


@app.post("/api/auth/guest-login")
def guest_login(request: Request, response: Response):
    if not public_sample_mode_enabled():
        raise HTTPException(403, "公開サンプルモードは無効です")
    with connect() as db:
        user = db.execute(
            "SELECT id,role,store_id,account_status FROM users WHERE employee_code=?",
            (SAMPLE_GUEST_EMPLOYEE_CODE,),
        ).fetchone()
        if not user or user["account_status"] != "ACTIVE":
            raise HTTPException(503, "サンプルアカウントが利用できません")
        previous = request.cookies.get(SESSION_COOKIE)
        if previous:
            db.execute("UPDATE auth_sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL",
                       (now_jst(), token_digest(previous)))
        db.execute("UPDATE users SET last_login_at=? WHERE id=?", (now_jst(), user["id"]))
        token = create_session(db, user["id"], request)
        audit(db, user["id"], "SAMPLE_GUEST_LOGIN", "user", user["id"],
              json.dumps({"source_ip": request.client.host if request.client else None,
                          "user_agent": request.headers.get("user-agent", "")[:200]}))
        db.commit()
        account = {"id": user["id"], "role": user["role"], "store_id": user["store_id"]}
        session_hours = config_value(db, "auth.session_absolute_timeout_hours")
    set_session_cookie(request, response, token, session_hours)
    return {"ok": True, "account": account, "guest": True}


@app.post("/api/auth/login")
def password_login(payload: PasswordLoginInput, request: Request, response: Response):
    identity = payload.employee_code.strip().upper()
    identity_hash = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    source_ip = request.client.host if request.client else None
    now = now_jst()
    with connect() as db:
        window_minutes = config_value(db, "auth.login_rate_limit_window_minutes")
        threshold = config_value(db, "auth.login_rate_limit_count")
        recent = db.execute(
            """SELECT COUNT(*) AS count FROM auth_login_attempts
               WHERE (identity_hash=? OR source_ip=?) AND attempted_at>=?""",
            (identity_hash, source_ip, now - timedelta(minutes=window_minutes)),
        ).fetchone()["count"]
        if recent >= threshold:
            raise HTTPException(429, "ログイン試行が多すぎます。しばらくしてから再試行してください")
        user = db.execute("SELECT * FROM users WHERE employee_code=?", (identity,)).fetchone()
        if not user or user["account_status"] != "ACTIVE":
            valid = False
        elif user["locked_until"] and user["locked_until"] > now:
            valid = False
        else:
            valid = bool(user["password_hash"] and verify_secret(payload.password, user["password_hash"]))
        db.execute(
            "INSERT INTO auth_login_attempts(identity_hash,source_ip,attempted_at,succeeded) VALUES(?,?,?,?)",
            (identity_hash, source_ip, now, int(valid)),
        )
        if not valid:
            if user:
                attempts = user["failed_login_attempts"] + 1
                max_attempts = config_value(db, "auth.login_max_failed_attempts")
                lock_minutes = config_value(db, "auth.login_lock_duration_minutes")
                lock_until = now + timedelta(minutes=lock_minutes) if attempts >= max_attempts else None
                db.execute("UPDATE users SET failed_login_attempts=?,locked_until=? WHERE id=?",
                           (attempts, lock_until, user["id"]))
            db.commit()
            raise HTTPException(401, "社員番号またはパスワードを確認してください")
        db.execute("UPDATE users SET failed_login_attempts=0,locked_until=NULL,last_login_at=? WHERE id=?",
                   (now, user["id"]))
        token = create_session(db, user["id"], request)
        audit(db, user["id"], "auth.login", "user", user["id"], "パスワード認証")
        db.commit()
        session_hours = config_value(db, "auth.session_absolute_timeout_hours")
        account = {"id": user["id"], "role": user["role"], "must_change_password": bool(user["must_change_password"])}
    set_session_cookie(request, response, token, session_hours)
    return {"ok": True, "account": account}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        with connect() as db:
            row = db.execute(
                "SELECT user_id FROM auth_sessions WHERE token_hash=? AND revoked_at IS NULL",
                (token_digest(token),),
            ).fetchone()
            if row:
                db.execute("UPDATE auth_sessions SET revoked_at=? WHERE token_hash=?",
                           (now_jst(), token_digest(token)))
                audit(db, row["user_id"], "auth.logout", "user", row["user_id"], "ログアウト")
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="lax")
    return {"ok": True}


@app.post("/api/auth/password-reset-requests")
def password_reset_request(payload: PasswordResetRequestInput, actor: CurrentActor = Depends(require_actor)):
    privileged_account_management(actor)
    if payload.verification_method not in ("in_person", "video_call", "identity_checked"):
        raise HTTPException(422, "本人確認方法が正しくありません")
    with connect() as db:
        target = db.execute("SELECT id,account_status FROM users WHERE id=?", (payload.user_id,)).fetchone()
        if not target or target["account_status"] not in ("ACTIVE", "INVITED", "LOCKED_SECURITY"):
            raise HTTPException(404, "対象アカウントが見つかりません")
        token = secrets.token_urlsafe(40)
        ttl = config_value(db, "auth.password_reset_link_ttl_minutes")
        expires = now_jst() + timedelta(minutes=ttl)
        reset_id = str(uuid.uuid4())
        db.execute(
            """INSERT INTO password_reset_tokens(id,user_id,token_hash,expires_at,created_by,
               verification_method,created_at) VALUES(?,?,?,?,?,?,?)""",
            (reset_id, target["id"], token_digest(token), expires, actor.user_id,
             payload.verification_method, now_jst()),
        )
        audit(db, actor.user_id, "PASSWORD_RESET_REQUESTED", "user", target["id"],
              json.dumps({"reset_id": reset_id, "verification_method": payload.verification_method}))
    return {"reset_token": token, "expires_at": expires.isoformat(timespec="seconds")}


@app.post("/api/auth/password-reset")
def complete_password_reset(payload: PasswordResetCompleteInput):
    with connect() as db:
        validate_password(db, payload.new_password)
        row = db.execute(
            """SELECT id,user_id,expires_at,used_at FROM password_reset_tokens
               WHERE token_hash=? FOR UPDATE""", (token_digest(payload.reset_token),)
        ).fetchone()
        now = now_jst()
        if not row or row["used_at"] or row["expires_at"] <= now:
            raise HTTPException(400, "リセットリンクが無効か期限切れです")
        encoded = hash_secret(payload.new_password)
        history_limit = config_value(db, "auth.password_history_count")
        previous_hashes = db.execute(
            "SELECT password_hash FROM password_history WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (row["user_id"], history_limit),
        ).fetchall() if history_limit else []
        user = db.execute("SELECT password_hash FROM users WHERE id=? FOR UPDATE", (row["user_id"],)).fetchone()
        if (user["password_hash"] and verify_secret(payload.new_password, user["password_hash"])) or any(
                verify_secret(payload.new_password, item["password_hash"]) for item in previous_hashes):
            raise HTTPException(422, "過去に使用したパスワードは再利用できません")
        db.execute("UPDATE users SET password_hash=?,must_change_password=1,failed_login_attempts=0,"
                   "locked_until=NULL,password_changed_at=?,last_password_reset_at=? WHERE id=?",
                   (encoded, now, now, row["user_id"]))
        db.execute("UPDATE password_reset_tokens SET used_at=? WHERE id=?", (now, row["id"]))
        db.execute("DELETE FROM auth_sessions WHERE user_id=?", (row["user_id"],))
        db.execute("INSERT INTO password_history(user_id,password_hash,created_at) VALUES(?,?,?)",
                   (row["user_id"], encoded, now))
        create_notification(db, row["user_id"], "SECURITY", "パスワードを再設定しました",
                            "管理者が本人確認のうえパスワードを再設定しました。",
                            "user", row["user_id"], title_zh="密码已重置",
                            message_zh="管理员已完成本人核验并重置密码。")
        audit(db, row["user_id"], "PASSWORD_RESET", "user", row["user_id"], "本人確認後のパスワード再設定")
    return {"ok": True}


@app.post("/api/auth/change-password")
def change_password(payload: ChangePasswordInput, request: Request,
                    actor: CurrentActor = Depends(require_actor)):
    with connect() as db:
        user = db.execute("SELECT password_hash,must_change_password FROM users WHERE id=? FOR UPDATE",
                          (actor.user_id,)).fetchone()
        if not user or (not user["must_change_password"] and
                        (not payload.current_password or
                         not verify_secret(payload.current_password, user["password_hash"] or ""))):
            raise HTTPException(401, "認証が必要です")
        validate_password(db, payload.new_password)
        encoded = hash_secret(payload.new_password)
        history_limit = config_value(db, "auth.password_history_count")
        previous_hashes = db.execute(
            "SELECT password_hash FROM password_history WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (actor.user_id, history_limit),
        ).fetchall() if history_limit else []
        if verify_secret(payload.new_password, user["password_hash"]) or any(
                verify_secret(payload.new_password, item["password_hash"]) for item in previous_hashes):
            raise HTTPException(422, "過去に使用したパスワードは再利用できません")
        now = now_jst()
        db.execute("INSERT INTO password_history(user_id,password_hash,created_at) VALUES(?,?,?)",
                   (actor.user_id, user["password_hash"], now))
        db.execute("UPDATE users SET password_hash=?,must_change_password=0,password_changed_at=? WHERE id=?",
                   (encoded, now, actor.user_id))
        token = request.cookies.get(SESSION_COOKIE)
        if token:
            db.execute("DELETE FROM auth_sessions WHERE user_id=? AND token_hash<>?",
                       (actor.user_id, token_digest(token)))
        audit(db, actor.user_id, "auth.password_changed", "user", actor.user_id, "本人によるパスワード変更")
    return {"ok": True}


@app.get("/api/accounts")
def account_list(actor: CurrentActor = Depends(require_actor)):
    privileged_account_management(actor)
    with connect() as db:
        return {"accounts": [
            {"id": row["id"], "public_id": row["public_id"], "employee_code": row["employee_code"],
             "display_name": row["display_name"], "role": row["role"], "store_id": row["store_id"],
             "account_status": row["account_status"], "must_change_password": bool(row["must_change_password"]),
             "last_login_at": row["last_login_at"], "version": row["version"]}
            for row in db.execute(
                """SELECT id,public_id,employee_code,display_name,role,store_id,account_status,
                          must_change_password,last_login_at,version FROM users ORDER BY employee_code"""
            )
        ]}


class AccountStatusInput(BaseModel):
    account_status: str
    version: int
    handoff_to_user_id: Optional[int] = None


@app.put("/api/accounts/{user_id}/status")
def update_account_status(user_id: int, payload: AccountStatusInput,
                          actor: CurrentActor = Depends(require_actor)):
    privileged_account_management(actor)
    if user_id == actor.user_id:
        raise HTTPException(422, "自分自身のアカウント状態は変更できません")
    transitions = {
        "PENDING_PROVISIONING": {"INVITED", "DEACTIVATED"},
        "INVITED": {"ACTIVE", "DEACTIVATED"},
        "ACTIVE": {"TRANSFER_PENDING", "LEAVE_RESTRICTED", "SUSPENDED", "LOCKED_SECURITY", "DEACTIVATED"},
        "TRANSFER_PENDING": {"ACTIVE", "DEACTIVATED"},
        "LEAVE_RESTRICTED": {"DEACTIVATED"},
        "SUSPENDED": {"ACTIVE", "DEACTIVATED"},
        "LOCKED_SECURITY": {"ACTIVE", "DEACTIVATED"},
        "DEACTIVATED": {"ARCHIVED"},
        "ARCHIVED": set(),
    }
    if payload.account_status not in transitions:
        raise HTTPException(422, "不明なアカウント状態です")
    with connect() as db:
        target = db.execute("SELECT * FROM users WHERE id=? FOR UPDATE", (user_id,)).fetchone()
        if not target:
            raise HTTPException(404, "対象アカウントが見つかりません")
        if target["version"] != payload.version:
            raise HTTPException(409, "他のユーザーが変更しました。更新して再試行してください")
        if payload.account_status not in transitions.get(target["account_status"], set()):
            raise HTTPException(409, "この状態遷移は許可されていません")
        if payload.account_status in ("DEACTIVATED", "LEAVE_RESTRICTED"):
            active_households = db.execute(
                "SELECT COUNT(*) AS count FROM households WHERE advisor_id=?", (user_id,)
            ).fetchone()["count"]
            active_tasks = db.execute(
                "SELECT COUNT(*) AS count FROM tasks WHERE assignee_id=? AND done=0 AND cancelled=0",
                (user_id,),
            ).fetchone()["count"]
            if active_households or active_tasks:
                successor = db.execute(
                    "SELECT id,store_id,role,account_status FROM users WHERE id=? FOR UPDATE",
                    (payload.handoff_to_user_id,),
                ).fetchone() if payload.handoff_to_user_id else None
                if (not successor or successor["id"] == user_id or successor["role"] not in
                        ("advisor", "store_manager") or successor["account_status"] != "ACTIVE"
                        or successor["store_id"] != target["store_id"]):
                    raise HTTPException(409, "未完了の顧客・タスクがあります。自店舗の有効な引継ぎ先を指定してください")
                db.execute("UPDATE households SET advisor_id=? WHERE advisor_id=?",
                           (successor["id"], user_id))
                db.execute("UPDATE introductions SET advisor_id=? WHERE advisor_id=?",
                           (successor["id"], user_id))
                db.execute("UPDATE tasks SET assignee_id=? WHERE assignee_id=? AND done=0 AND cancelled=0",
                           (successor["id"], user_id))
                audit(db, actor.user_id, "account.handoff", "user", user_id,
                      f"successor_user_id={successor['id']}")
        db.execute("UPDATE users SET account_status=?,version=version+1 WHERE id=? AND version=?",
                   (payload.account_status, user_id, payload.version))
        if payload.account_status != "ACTIVE":
            db.execute("DELETE FROM auth_sessions WHERE user_id=?", (user_id,))
        audit(db, actor.user_id, "account.status_changed", "user", user_id,
              f"status={payload.account_status}; version={payload.version + 1}")
    return {"ok": True, "account_status": payload.account_status, "version": payload.version + 1}


class AccountTransferInput(BaseModel):
    role: str
    store_id: Optional[int] = None
    version: int


@app.put("/api/accounts/{user_id}/role")
def transfer_account(user_id: int, payload: AccountTransferInput,
                     actor: CurrentActor = Depends(require_actor)):
    privileged_account_management(actor)
    roles = {"executive", "administrator", "hq_staff", "store_manager", "advisor", "finance", "hr"}
    if payload.role not in roles or (payload.role in ("advisor", "store_manager") and not payload.store_id):
        raise HTTPException(422, "ロールまたは店舗を指定してください")
    with connect() as db:
        target = db.execute("SELECT * FROM users WHERE id=? FOR UPDATE", (user_id,)).fetchone()
        if not target:
            raise HTTPException(404, "対象アカウントが見つかりません")
        if target["version"] != payload.version:
            raise HTTPException(409, "他のユーザーが変更しました。更新して再試行してください")
        if payload.store_id and not db.execute("SELECT id FROM stores WHERE id=?", (payload.store_id,)).fetchone():
            raise HTTPException(422, "指定した店舗がありません")
        store_id = payload.store_id if payload.role in ("advisor", "store_manager") else None
        db.execute(
            """UPDATE users SET role=?,store_id=?,account_status='TRANSFER_PENDING',
               version=version+1 WHERE id=? AND version=?""",
            (payload.role, store_id, user_id, payload.version),
        )
        db.execute("DELETE FROM auth_sessions WHERE user_id=?", (user_id,))
        audit(db, actor.user_id, "account.role_transferred", "user", user_id,
              f"role={payload.role}; store_id={store_id}; prior_role={target['role']}; "
              f"prior_store_id={target['store_id']}")
    return {"ok": True, "account_status": "TRANSFER_PENDING", "version": payload.version + 1}


def ensure_system_config(db):
    db.execute("INSERT IGNORE INTO audit_chain(id,last_hash) VALUES(1,?)", ("0" * 64,))
    now = datetime.now().isoformat(timespec="seconds")
    for key, value in SYSTEM_CONFIG_DEFAULTS.items():
        db.execute(
            "INSERT IGNORE INTO system_configs(config_key,value_json,updated_at) VALUES(?,?,?)",
            (key, json.dumps(value, ensure_ascii=False, sort_keys=True), now),
        )
    sync_sla_settings(db)
    verify_audit_chain(db)


def sync_sla_settings(db):
    for reminder_type, config_key, label_ja, label_zh in SLA_CONFIG:
        row = db.execute(
            "SELECT value_json FROM system_configs WHERE config_key=?", (config_key,)
        ).fetchone()
        if not row:
            continue
        days = json.loads(row["value_json"]) if isinstance(row["value_json"], str) else row["value_json"]
        db.execute(
            """INSERT INTO sla_settings(reminder_type,days_before,label_ja,label_zh)
               VALUES(?,?,?,?) ON DUPLICATE KEY UPDATE days_before=VALUES(days_before),
               label_ja=VALUES(label_ja),label_zh=VALUES(label_zh)""",
            (reminder_type, days, label_ja, label_zh),
        )


def verify_audit_chain(db):
    previous_hash = "0" * 64
    for row in db.execute("SELECT * FROM audit_events ORDER BY id"):
        event_at = row["event_at"]
        if isinstance(event_at, datetime):
            event_at = event_at.isoformat(timespec="seconds")
        event = {
            "actor_id": row["actor_id"],
            "actor_role": row["actor_role"],
            "action": row["action"],
            "object_type": row["object_type"],
            "object_id": row["object_id"],
            "reason": row["reason"],
            "event_at": event_at,
            "previous_hash": previous_hash,
        }
        if row["object_id_text"] is not None:
            event["object_id_text"] = row["object_id_text"]
        expected_hash = hashlib.sha256(
            (previous_hash + json.dumps(event, ensure_ascii=False, sort_keys=True)).encode("utf-8")
        ).hexdigest()
        if row["previous_hash"] != previous_hash or row["event_hash"] != expected_hash:
            raise RuntimeError(f"Audit event chain verification failed at event {row['id']}")
        previous_hash = expected_hash
    head = db.execute("SELECT last_hash FROM audit_chain WHERE id=1").fetchone()
    if not head or head["last_hash"] != previous_hash:
        raise RuntimeError("Audit event chain head does not match the recorded events")


def ensure_schema(db):
    db.executescript(SCHEMA)
    migrations = {
        "users": {
            "employee_code": "VARCHAR(30) NULL",
            "public_id": "CHAR(36) NULL",
            "display_name": "VARCHAR(120) NULL",
            "password_hash": "VARCHAR(255) NULL",
            "account_status": "VARCHAR(40) NOT NULL DEFAULT 'ACTIVE'",
            "failed_login_attempts": "INT NOT NULL DEFAULT 0",
            "locked_until": "DATETIME NULL",
            "must_change_password": "TINYINT NOT NULL DEFAULT 1",
            "last_login_at": "DATETIME NULL",
            "password_changed_at": "DATETIME NULL",
            "last_password_reset_at": "DATETIME NULL",
            "version": "INT NOT NULL DEFAULT 1",
        },
        "audit_events": {
            "object_id_text": "VARCHAR(160) NULL",
            "event_type": "VARCHAR(80) NULL",
            "before_hash": "CHAR(64) NULL",
            "after_hash": "CHAR(64) NULL",
            "request_id": "CHAR(36) NULL",
            "result": "VARCHAR(40) NULL",
            "error_code": "VARCHAR(80) NULL",
        },
        "audit_logs": {"target_id_text": "VARCHAR(160) NULL"},
        "migration_mappings": {"old_user_id": "INT NULL"},
        "households": {"household_code": "VARCHAR(24) NULL", "kana": "VARCHAR(120) NULL"},
        "persons": {"kana": "VARCHAR(120) NULL"},
        "stores": {"opened_at": "DATE NULL"},
        "partner_staff": {"branch_name": "VARCHAR(120) NULL"},
        "fee_rules": {"effective_to": "DATE NULL"},
        "introductions": {
            "advisor_id": "INT NULL", "valid_until": "DATE NULL",
            "referral_letter_id": "CHAR(36) NULL",
        },
        "consents": {
            "consent_method": "VARCHAR(80) NULL",
            "content_version": "VARCHAR(40) NULL",
            "allowed_fields_json": "JSON NULL",
            "partner_id": "INT NULL",
            "expires_at": "DATETIME NULL",
            "evidence_reference": "VARCHAR(255) NULL",
        },
        "construction_projects": {
            "confirmation_due_date": "DATE NULL",
            "confirmation_status": "VARCHAR(40) NOT NULL DEFAULT 'pending_review'",
            "delayed_note": "TEXT NULL",
        },
        "fee_entitlements": {
            "invoice_data_generated": "TINYINT NOT NULL DEFAULT 0",
            "reference_amount": "BIGINT NOT NULL DEFAULT 0",
        },
        "referral_disputes": {
            "due_date": "DATE NULL",
            "dispute_type": "VARCHAR(40) NOT NULL DEFAULT 'referral'",
            "reference_amount": "BIGINT NOT NULL DEFAULT 0",
        },
        "notifications": {
            "title_zh": "VARCHAR(255) NULL",
            "message_zh": "TEXT NULL",
        },
        "export_jobs": {
            "format": "VARCHAR(12) NOT NULL DEFAULT 'csv'",
            "template_version": "VARCHAR(40) NOT NULL DEFAULT 'csv-v1'",
            "created_role": "VARCHAR(40) NOT NULL DEFAULT ''",
            "scope_store_id": "INT NULL",
            "include_personal_data": "TINYINT NOT NULL DEFAULT 0",
            "record_ids_json": "LONGTEXT NULL",
            "downloaded_at": "DATETIME NULL",
        },
        "import_jobs": {
            "content_sha256": "CHAR(64) NULL",
            "mapping_json": "JSON NULL",
            "preview_expires_at": "DATETIME NULL",
        },
        "expenses": {
            "applied_at": "DATETIME NULL",
            "tax_amount": "BIGINT NOT NULL DEFAULT 0",
            "tax_category": "VARCHAR(40) NOT NULL DEFAULT '課税10%%（税込）'",
            "accounting_integration_id": "VARCHAR(160) NULL",
            "recorded_reference": "VARCHAR(500) NULL",
            "recorded_confirmed_at": "DATETIME NULL",
        },
        "tasks": {
            "task_type": "VARCHAR(40) NOT NULL DEFAULT 'followup'",
            "priority": "VARCHAR(20) NOT NULL DEFAULT 'normal'",
            "related_type": "VARCHAR(40) NOT NULL DEFAULT 'household'",
            "related_id": "INT NULL",
            "cancelled": "TINYINT NOT NULL DEFAULT 0",
            "status": "VARCHAR(20) NOT NULL DEFAULT 'open'",
        },
        "negotiations": {
            "next_action": "VARCHAR(255) NULL",
            "next_action_due": "DATE NULL",
            "next_action_owner_id": "INT NULL",
            "risk_level": "VARCHAR(20) NOT NULL DEFAULT 'none'",
            "version": "INT NOT NULL DEFAULT 1",
        },
        "calendar_events": {"version": "INT NOT NULL DEFAULT 1"},
        "user_preferences": {
            "dashboard_widgets": "JSON NULL",
            "notification_preferences": "JSON NULL",
        },
    }
    for table, columns in migrations.items():
        for column, definition in columns.items():
            exists = db.execute(
                """SELECT COUNT(*) FROM information_schema.columns
                   WHERE table_schema=DATABASE() AND table_name=? AND column_name=?""",
                (table, column),
            ).fetchone()[0]
            if not exists:
                db.execute(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {definition}")
    for seed_household in db.execute(
            "SELECT id,household_code FROM households WHERE household_code LIKE ? AND kana IS NULL",
            ("HH-D%",)):
        try:
            seed_number = int(seed_household["household_code"][-3:])
        except (TypeError, ValueError):
            continue
        seed_kana = f"{SAMPLE_SURNAMES_KANA[(seed_number - 1) % 12]}{chr(65 + (seed_number - 1) // 12)}"
        db.execute("UPDATE households SET kana=? WHERE id=?", (seed_kana, seed_household["id"]))
        db.execute("UPDATE persons SET kana=? WHERE household_id=? AND kana IS NULL",
                   (seed_kana, seed_household["id"]))
    db.execute("""UPDATE consents SET expires_at='2027-12-31 23:59:59'
                WHERE consent_method='DEMO_WRITTEN' AND content_version='referral-consent-v1'
                AND partner_id IS NOT NULL""")
    for index_name, column_name in (("uq_users_employee_code", "employee_code"),
                                    ("uq_users_public_id", "public_id")):
        exists = db.execute(
            """SELECT COUNT(*) FROM information_schema.statistics
               WHERE table_schema=DATABASE() AND table_name='users' AND index_name=?""",
            (index_name,),
        ).fetchone()[0]
        if not exists:
            db.execute(f"CREATE UNIQUE INDEX `{index_name}` ON users(`{column_name}`)")
    for table, index_name, columns in (
        ("negotiations", "idx_negotiations_next_action", "next_action_due,next_action_owner_id"),
        ("calendar_events", "idx_calendar_events_range", "starts_at,ends_at"),
    ):
        exists = db.execute(
            """SELECT COUNT(*) FROM information_schema.statistics
               WHERE table_schema=DATABASE() AND table_name=? AND index_name=?""",
            (table, index_name),
        ).fetchone()[0]
        if not exists:
            db.execute(f"CREATE INDEX `{index_name}` ON `{table}`({columns})")
    db.execute("UPDATE tasks SET status=IF(done=1,'done','open') WHERE status IS NULL")


def ensure_demo_accounts(db):
    existing = db.execute(
        "SELECT id,role,store_id,name,employee_code FROM users ORDER BY id"
    ).fetchall()
    if not existing:
        return
    now = now_jst()
    for row in existing:
        if row["employee_code"]:
            continue
        db.execute(
            """INSERT IGNORE INTO migration_mappings(old_demo_role,old_user_id,new_user_id,store_id,
               mapped_at,status,old_display_name) VALUES(?,?,?,?,?,'MAPPED',?)""",
            (row["role"], row["id"], row["id"], row["store_id"], now, row["name"]),
        )

    def update_user(user_id, role, store_id, employee_code, display_name):
        db.execute(
            """UPDATE users SET role=?,store_id=?,employee_code=?,public_id=COALESCE(public_id,?),
               display_name=?,name=?,password_hash=COALESCE(password_hash,?),account_status='ACTIVE'
               WHERE id=?""",
            (role, store_id, employee_code, str(uuid.uuid4()), display_name, display_name,
             hash_secret(secrets.token_urlsafe(32)), user_id),
        )

    advisors = db.execute("SELECT id,store_id FROM users WHERE role='advisor' ORDER BY store_id,id").fetchall()
    advisor_slots = {row["store_id"]: [] for row in advisors}
    for row in advisors:
        advisor_slots.setdefault(row["store_id"], []).append(row["id"])
    for store_id in range(1, 13):
        letter = chr(64 + store_id)
        current_ids = advisor_slots.get(store_id, [])
        if not current_ids:
            user_id = db.execute(
                "INSERT INTO users(name,role,store_id) VALUES(?,?,?)",
                (f"顧問{letter}A", "advisor", store_id),
            ).lastrowid
            current_ids = [user_id]
        for slot, user_id in enumerate(current_ids[:2]):
            update_user(user_id, "advisor", store_id, f"AD-{store_id:02}-{slot + 1}",
                        f"佐藤{letter}{chr(65 + slot)}")
        if len(current_ids) < 2:
            user_id = db.execute(
                "INSERT INTO users(name,role,store_id,employee_code,public_id,display_name,password_hash) "
                "VALUES(?,?,?,?,?,?,?)",
                (f"田中{letter}B", "advisor", store_id, f"AD-{store_id:02}-2",
                 str(uuid.uuid4()), f"田中{letter}B", hash_secret(secrets.token_urlsafe(32))),
            ).lastrowid

    managers = db.execute(
        "SELECT id,store_id FROM users WHERE role IN ('manager','store_manager') ORDER BY id"
    ).fetchall()
    manager_by_store = {row["store_id"]: row["id"] for row in managers if row["store_id"]}
    for store_id in range(1, 13):
        letter = chr(64 + store_id)
        user_id = manager_by_store.get(store_id)
        if user_id is None:
            user_id = db.execute(
                "INSERT INTO users(name,role,store_id) VALUES(?,?,?)",
                (f"店長{letter}", "manager", store_id),
            ).lastrowid
        update_user(user_id, "store_manager", store_id, f"SM-{store_id:02}", f"店長{letter}")

    legacy_roles = {
        "executive": ("executive", "社長A", "EX-01", None),
        "hq_finance": ("finance", "財務A", "FN-01", None),
    }
    for old_role, (new_role, display_name, employee_code, store_id) in legacy_roles.items():
        old = db.execute("SELECT id FROM users WHERE role=? ORDER BY id LIMIT 1", (old_role,)).fetchone()
        if old:
            update_user(old["id"], new_role, store_id, employee_code, display_name)

    additions = [
        ("administrator", None, "運用管理者A", "AM-01"),
        ("finance", None, "財務B", "FN-02"),
        ("hr", None, "人事A", "HR-01"), ("hr", None, "人事B", "HR-02"),
    ] + [("hq_staff", None, f"本社担当{chr(65 + index)}", f"HQ-{index + 1:02}")
         for index in range(4)]
    for role, store_id, display_name, employee_code in additions:
        if not db.execute("SELECT id FROM users WHERE employee_code=?", (employee_code,)).fetchone():
            db.execute(
                """INSERT INTO users(name,role,store_id,employee_code,public_id,display_name,password_hash)
                   VALUES(?,?,?,?,?,?,?)""",
                (display_name, role, store_id, employee_code, str(uuid.uuid4()), display_name,
                 hash_secret(secrets.token_urlsafe(32))),
            )
    demo_employee_codes = [
        *(f"AD-{store_id:02}-{slot}" for store_id in range(1, 13) for slot in (1, 2)),
        *(f"SM-{store_id:02}" for store_id in range(1, 13)),
        "EX-01", "FN-01", "AM-01", "FN-02", "HR-01", "HR-02",
        *(f"HQ-{index:02}" for index in range(1, 5)),
    ]
    placeholders = ",".join("?" for _ in demo_employee_codes)
    db.execute(
        f"UPDATE users SET must_change_password=0 WHERE employee_code IN ({placeholders})",
        demo_employee_codes,
    )
    count = db.execute("SELECT COUNT(*) AS count FROM users WHERE role <> 'owner'").fetchone()["count"]
    if count != 46:
        raise RuntimeError(f"Expected 46 demo accounts; found {count}")
def valid_config_value(key, value):
    default = SYSTEM_CONFIG_DEFAULTS[key]
    if type(value) is not type(default):
        return False
    if isinstance(default, dict):
        if value.keys() != default.keys():
            return False
        try:
            for item in value.values():
                datetime.strptime(item, "%H:%M")
        except (TypeError, ValueError):
            return False
    elif isinstance(default, list):
        if len(value) != len(default) or any(type(v) is not type(default[0]) for v in value):
            return False
        if all(type(v) is int for v in value) and value != sorted(value):
            return False
        if all(type(v) is str for v in value) and any(not v.strip() for v in value):
            return False
    if isinstance(value, int) and not isinstance(value, bool):
        minimum, maximum = SYSTEM_CONFIG_RANGES.get(key, (0, 100000))
        if not minimum <= value <= maximum:
            return False
    if key == "fee_rule.applicability_basis" and value not in (
        "contract_date", "agreement_date", "construction_confirmation_date"
    ):
        return False
    if key == "expense.allowed_categories" and not set(value).issubset(
        {"交通費", "消耗品費", "会議費", "通信費", "その他"}
    ):
        return False
    if key == "expense.approval_thresholds_yen" and value[0] >= value[1]:
        return False
    if key == "attachment.allowed_extensions" and not set(value).issubset(
        {"pdf", "jpg", "jpeg", "png", "csv", "xlsx"}
    ):
        return False
    if key == "month_close.locked_resources" and (
        len(value) != len(set(value)) or not set(value).issubset({
            "expenses", "fee_entitlements", "contracts", "construction_projects",
            "activities", "introductions", "stage_events",
        })
    ):
        return False
    if isinstance(value, list) and value and type(value[0]) is int:
        if any(v < 0 or v > 100000 for v in value):
            return False
    return True


def demo_receipt_pdf():
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 360 200] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length 108 >>\nstream\nBT /F1 12 Tf 25 150 Td "
        b"(SumaiBoard DEMO receipt) Tj 0 -25 Td "
        b"(FICTIONAL - NOT AN ACCOUNTING RECORD) Tj ET\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    content = bytearray(b"%PDF-1.4\n% Fictional SumaiBoard demo receipt\n")
    offsets = [0]
    for index, item in enumerate(objects, 1):
        offsets.append(len(content))
        content.extend(f"{index} 0 obj\n".encode("ascii") + item + b"\nendobj\n")
    xref_offset = len(content)
    content.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    content.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        content.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    content.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(content)


def seed(db):
    _seed_legacy(db)
    ensure_system_config(db)
    ensure_demo_accounts(db)
    rental.ensure_rental_schema(db)
    if sample_or_demo_enabled():
        rental.seed_rental(db)


def _seed_legacy(db):
    ensure_schema(db)
    if db.execute("SELECT COUNT(*) FROM seed_metadata WHERE id=1").fetchone()[0]:
        return
    if db.execute("SELECT COUNT(*) FROM stores").fetchone()[0]:
        return
    now = datetime.now().replace(microsecond=0)
    today = now_jst().date()
    db.executemany(
        "INSERT INTO stores(id,name,area,opened_at) VALUES(?,?,?,?)",
        [(index + 1, name, area, date(2020 + index % 5, index % 12 + 1, 1))
         for index, (name, area) in enumerate(STORES)],
    )
    users = {}
    for name, role, store_id in (
        ("デモ顧問A", "advisor", 1), ("デモ店長A", "manager", 3),
        ("デモ経理A", "hq_finance", None), ("デモ社長A", "executive", None),
    ):
        users[role] = db.execute(
            "INSERT INTO users(name,role,store_id) VALUES(?,?,?)", (name, role, store_id)
        ).lastrowid
    advisors = [users["advisor"]]
    for store_id in range(2, 13):
        advisors.append(db.execute(
            "INSERT INTO users(name,role,store_id) VALUES(?,?,?)",
            (f"デモ顧問{chr(64 + store_id)}", "advisor", store_id),
        ).lastrowid)

    month_counts = [(6, 7), (7, 8), (8, 10), (9, 12), (10, 14), (11, 9)]
    intake_dates = []
    for month, count in month_counts:
        start = date(2026, month, 1)
        next_month = date(2026 + (month == 12), month % 12 + 1, 1)
        days = (next_month - start).days
        intake_dates.extend(start + timedelta(days=(index * 3) % days) for index in range(count))
    intake_dates[-1] = date(2026, 11, 16)

    household_counts_by_store = [6, 6, 6, 6, 5, 5, 5, 5, 4, 4, 4, 4]
    store_ids = [store_id for store_id, count in enumerate(household_counts_by_store, 1)
                 for _ in range(count)]
    state_by_number = {
        **{i: "入金済" for i in range(1, 6)},
        **{i: "争議中" for i in range(6, 9)},
        **{i: "請求済" for i in range(9, 14)},
        **{i: "報酬承認待ち" for i in range(14, 18)},
        **{i: "着工確認待ち" for i in range(18, 23)},
        **{i: "契約済" for i in range(23, 29)},
        **{i: "紹介中" for i in range(29, 45)},
        **{i: "相談中" for i in range(45, 57)},
        **{i: "解約済" for i in range(57, 61)},
    }

    fee_rule_ids = {}
    partner_staff_ids = {}
    for partner_id in range(1, 13):
        letter = chr(64 + partner_id)
        db.execute(
            "INSERT INTO partners(id,name,area,tags,active) VALUES(?,?,?,?,1)",
            (partner_id, f"住宅会社{letter}", STORES[partner_id - 1][1],
             json.dumps(["価格", "性能"], ensure_ascii=False)),
        )
        for staff_letter, branch_letter in (("A", "A"), ("B", "A"), ("C", "B")):
            staff_id = db.execute(
                "INSERT INTO partner_staff(partner_id,name,branch_name) VALUES(?,?,?)",
                (partner_id, f"担当者{staff_letter}", f"支店{branch_letter}"),
            ).lastrowid
            partner_staff_ids.setdefault(partner_id, []).append(staff_id)
        old_rule = db.execute(
            """INSERT INTO fee_rules(version,type,params,base,effective_from,effective_to,approved_by)
               VALUES(?, 'rate', ?, '請負金額', '2025-01-01', '2025-12-31', ?)""",
            (f"2025.{letter}", '{"rate":0.018}', users["hq_finance"]),
        ).lastrowid
        current_rule = db.execute(
            """INSERT INTO fee_rules(version,type,params,base,effective_from,effective_to,approved_by)
               VALUES(?, 'rate', ?, '請負金額', '2026-01-01', ?, ?)""",
            (f"2026.{letter}", '{"rate":0.02}',
             today + timedelta(days=20) if partner_id == 1 else None, users["hq_finance"]),
        ).lastrowid
        fee_rule_ids[partner_id] = current_rule
        db.execute(
            "INSERT INTO partner_agreements(partner_id,effective_from,effective_to,fee_rule_id,status) VALUES(?,?,?,?,?)",
            (partner_id, "2025-01-01", "2025-12-31", old_rule, "expired"),
        )
        db.execute(
            "INSERT INTO partner_agreements(partner_id,effective_from,effective_to,fee_rule_id,status) VALUES(?,?,?,?,?)",
            (partner_id, "2026-01-01", today + timedelta(days=15) if partner_id == 1 else None,
             current_rule, "active"),
        )

    spread_households = {}
    for number in range(1, 61):
        code = f"HH-D{number:03}"
        store_id = store_ids[number - 1]
        advisor_id = advisors[store_id - 1]
        if number in (4, 17, 35, 44):
            advisor_id = None
        status_name = state_by_number[number]
        status = "lost" if status_name == "解約済" else "completed" if status_name == "入金済" else "active"
        intake_at = datetime.combine(intake_dates[number - 1], datetime.min.time())
        name = f"{SAMPLE_SURNAMES[(number - 1) % 12]}{chr(65 + (number - 1) // 12)}"
        kana = f"{SAMPLE_SURNAMES_KANA[(number - 1) % 12]}{chr(65 + (number - 1) // 12)}"
        household_id = db.execute(
            """INSERT INTO households(household_code,representative_name,store_id,advisor_id,budget_band,
               area_pref,land_status,status,created_at,lost_reason,kana)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (code, name, store_id, advisor_id,
             ("4,000〜5,000万円", "5,000〜6,000万円", "6,000〜7,000万円")[number % 3],
             f"{STORES[store_id - 1][1]}エリア", ("有", "無", "検討中")[number % 3],
             status, intake_at, "デモ見送り" if status == "lost" else None, kana),
        ).lastrowid
        spread_households[number] = {"id": household_id, "code": code, "store_id": store_id,
                                     "advisor_id": advisor_id, "name": name}
        db.execute(
            "INSERT INTO persons(household_id,name,relation,phone,email,kana) VALUES(?,?,?,?,?,?)",
            (household_id, name, "本人", f"090-0000-{number:04}", f"demo{number:03}@example.test", kana),
        )
        for touch_index, channel in enumerate(("Web広告", "直接来店")):
            touch_at = intake_at + timedelta(days=touch_index * 3)
            db.execute(
                """INSERT INTO touches(household_id,touch_at,channel,campaign_id,creative_id,
                   tracking_code,landing_referrer,store_id,capture_method) VALUES(?,?,?,?,?,?,?,?,?)""",
                (household_id, touch_at, channel, "DEMO_2026", "DEMO_CREATIVE",
                 f"DEMO-{number:03}-{touch_index}", "demo.example.test", store_id,
                 "UTM" if touch_index == 0 else "手入力"),
            )
        stage_paths = {
            "相談中": ["新規予約", "初回相談済"],
            "紹介中": ["新規予約", "初回相談済", "FP診断済", "紹介済"],
            "契約済": ["新規予約", "初回相談済", "FP診断済", "紹介済", "訪問・商談中", "契約"],
            "着工確認待ち": ["新規予約", "初回相談済", "FP診断済", "紹介済", "訪問・商談中", "契約", "着工"],
            "報酬承認待ち": ["新規予約", "初回相談済", "FP診断済", "紹介済", "訪問・商談中", "契約", "着工"],
            "請求済": ["新規予約", "初回相談済", "FP診断済", "紹介済", "訪問・商談中", "契約", "着工"],
            "入金済": ["新規予約", "初回相談済", "FP診断済", "紹介済", "訪問・商談中", "契約", "着工", "完了・見送り"],
            "争議中": ["新規予約", "初回相談済", "FP診断済", "紹介済"],
        }
        if status_name == "解約済":
            reached = 2 + number % 5
            stage_paths[status_name] = STAGES[:reached] + ["完了・見送り"]
        previous_stage = None
        for stage_index, stage_name in enumerate(stage_paths[status_name]):
            changed_at = intake_at + timedelta(days=stage_index * 3)
            db.execute(
                """INSERT INTO stage_events(household_id,from_stage,to_stage,changed_by,changed_at)
                   VALUES(?,?,?,?,?)""",
                (household_id, previous_stage, stage_name, advisors[store_id - 1], changed_at),
            )
            previous_stage = stage_name
        db.execute(
            "INSERT INTO consents(household_id,purpose,scope,granted_at) VALUES(?,?,?,?)",
            (household_id, "住宅会社への希望条件共有", "L3", intake_at + timedelta(days=2)),
        )
        db.execute(
            """INSERT INTO activities(household_id,user_id,type,body,acted_at,next_action,next_action_due)
               VALUES(?,?,'面談','ご希望条件を確認しました',?,?,?)""",
            (household_id, advisor_id or users["manager"], intake_at + timedelta(days=2),
             "次回相談の確認", intake_dates[number - 1] + timedelta(days=4)),
        )

    introduced_households = set(range(1, 45)) | set(range(52, 56))
    double_households = set(range(24, 36))
    triple_households = set(range(18, 24))
    introductions_by_household = {}
    for number in sorted(introduced_households):
        household = spread_households[number]
        count = 3 if number in triple_households else 2 if number in double_households else 1
        rows = []
        for position in range(count):
            partner_id = ((number + position * 4 - 1) % 12) + 1
            introduced_at = datetime.combine(
                intake_dates[number - 1] + timedelta(days=7 + position), datetime.min.time()
            )
            status = "受付確認済" if number % 4 else "紹介済"
            intro_id = db.execute(
                """INSERT INTO introductions(household_id,partner_id,partner_staff_id,advisor_id,
                   introduced_at,reception_confirmed_at,status,valid_until)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (household["id"], partner_id, partner_staff_ids[partner_id][0],
                 household["advisor_id"] if number % 13 else None, introduced_at,
                 introduced_at + timedelta(days=1) if status == "受付確認済" else None,
                 status, today + timedelta(days=5) if number == 11 else introduced_at.date() + timedelta(days=30)),
            ).lastrowid
            db.execute(
                """INSERT INTO consents(household_id,purpose,scope,granted_at,consent_method,
                   content_version,allowed_fields_json,partner_id,expires_at)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (household["id"], "住宅会社への住宅紹介状作成", "L3",
                 introduced_at - timedelta(days=1), "DEMO_WRITTEN",
                 "referral-consent-v1",
                 json.dumps(["household_code", "area_pref", "budget_band", "land_status",
                             "family_summary"], ensure_ascii=False),
                 partner_id, introduced_at + timedelta(days=90)),
            )
            negotiation_id = db.execute(
                "INSERT INTO negotiations(introduction_id,status,last_activity_at) VALUES(?,?,?)",
                (intro_id, ("訪問予定", "商談中", "見積提示")[position % 3],
                 introduced_at + timedelta(days=position + 2)),
            ).lastrowid
            if number in (52, 53, 54, 55) and position == 0:
                action_owner = household["advisor_id"] or advisors[household["store_id"] - 1]
                action_due = today + timedelta(days=number % 3 - 1)
                action_text = "住宅会社へ次回相談の日程を確認"
                db.execute(
                    """UPDATE negotiations SET next_action=?,next_action_due=?,
                       next_action_owner_id=?,risk_level='watch' WHERE id=?""",
                    (action_text, action_due, action_owner, negotiation_id),
                )
                db.execute(
                    """INSERT INTO tasks(assignee_id,title,due_at,source,related_household_id,
                       task_type,priority,related_type,related_id,status)
                       VALUES(?,?,?,'demo_seed',?,'negotiation_action','normal','negotiation',?,'open')""",
                    (action_owner, action_text, action_due, household["id"], negotiation_id),
                )
            rows.append((intro_id, negotiation_id, partner_id))
        introductions_by_household[number] = rows

    def create_contract(number, position=0, amount=32_000_000, project=None,
                        fee_state=None, dispute=None, contract_date_override=None):
        intro_id, negotiation_id, partner_id = introductions_by_household[number][position]
        contract_date = contract_date_override or intake_dates[number - 1] + timedelta(days=45)
        db.execute("UPDATE negotiations SET status='契約' WHERE id=?", (negotiation_id,))
        contract_id = db.execute(
            "INSERT INTO contracts(negotiation_id,contract_date,contract_amount,builder_contact) VALUES(?,?,?,?)",
            (negotiation_id, contract_date, amount, "担当者A"),
        ).lastrowid
        if project is not None:
            planned, actual, confirmed, evidence, confirm_due, confirm_state, delayed_note = project
            db.execute(
                """INSERT INTO construction_projects(contract_id,planned_start_date,actual_start_date,
                   confirmed_start_date,confirmation_evidence,confirmation_due_date,confirmation_status,delayed_note)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (contract_id, planned, actual, confirmed, evidence, confirm_due, confirm_state, delayed_note),
            )
        entitlement_id = None
        if fee_state:
            fee_amount = round(amount * 0.02)
            if dispute:
                fee_amount = dispute["amount"]
            entitlement_id = db.execute(
                """INSERT INTO fee_entitlements(contract_id,introduction_id,fee_rule_id,base_amount,
                   calculated_amount,state,dispute_reason,calculated_at,confirmed_by,
                   invoice_data_generated,reference_amount) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (contract_id, intro_id, fee_rule_ids[partner_id], amount, fee_amount, fee_state,
                 dispute["reason"] if dispute else None, now, users["hq_finance"],
                 1 if fee_state in ("Invoiced", "Paid") else 0,
                 dispute["amount"] if dispute else 0),
            ).lastrowid
            if dispute:
                db.execute(
                    """INSERT INTO referral_disputes(fee_entitlement_id,raised_by,reason,evidence_level,
                       status,dispute_type,reference_amount,due_date) VALUES(?,?,?,?,'Open',?,?,?)""",
                    (entitlement_id, users["manager"], dispute["reason"], dispute["evidence"], dispute["type"],
                     dispute["amount"], today + timedelta(days=7)),
                )
                db.execute(
                    "UPDATE introductions SET status='帰属争議中',existing_customer_flag=1,evidence_note=? WHERE id=?",
                    (dispute["reason"], intro_id),
                )
        return contract_id, intro_id, partner_id, entitlement_id

    for number in range(1, 6):
        amount = 16_500_000 if number == 1 else 32_000_000 + number * 100_000
        create_contract(
            number, amount=amount,
            project=(intake_dates[number - 1] + timedelta(days=60),
                     intake_dates[number - 1] + timedelta(days=75),
                     intake_dates[number - 1] + timedelta(days=77), "着工写真を確認済み",
                     intake_dates[number - 1] + timedelta(days=76), "confirmed", None),
            fee_state="Paid",
        )

    dispute_cases = [
        {"number": 6, "amount": 16_500_000, "fee": 330_000, "type": "referral", "reason": "紹介帰属の確認", "evidence": "A"},
        {"number": 7, "amount": 11_000_000, "fee": 220_000, "type": "amount", "reason": "報酬金額の確認", "evidence": "C"},
        {"number": 8, "amount": 13_750_000, "fee": 275_000, "type": "construction", "reason": "着工証拠の確認", "evidence": "B"},
    ]
    construction_queue = []
    for case in dispute_cases:
        project = (today - timedelta(days=8), today - timedelta(days=5), None, None,
                   today - timedelta(days=2), "evidence_missing", None) if case["type"] == "construction" else None
        contract_id, intro_id, _, _ = create_contract(
            case["number"], amount=case["amount"], project=project, fee_state="Disputed",
            dispute={"reason": case["reason"], "type": case["type"], "amount": case["fee"],
                     "evidence": case["evidence"]},
        )
        if project:
            project_id = db.execute(
                "SELECT id FROM construction_projects WHERE contract_id=?", (contract_id,)
            ).fetchone()["id"]
            construction_queue.append((project_id, case["number"], "evidence_missing", today - timedelta(days=2)))

    for number in range(9, 14):
        create_contract(
            number, amount=32_000_000,
            project=(intake_dates[number - 1] + timedelta(days=60),
                     intake_dates[number - 1] + timedelta(days=75),
                     intake_dates[number - 1] + timedelta(days=77), "着工確認済み",
                     intake_dates[number - 1] + timedelta(days=76), "confirmed", None),
            fee_state="Invoiced",
        )
    for number in range(14, 18):
        create_contract(
            number, amount=30_000_000,
            project=(intake_dates[number - 1] + timedelta(days=60),
                     intake_dates[number - 1] + timedelta(days=75),
                     intake_dates[number - 1] + timedelta(days=77), "証跡確認済み",
                     intake_dates[number - 1] + timedelta(days=76), "confirmed", None),
            fee_state="Pending",
        )

    project_specs = [
        (18, 0, "planned_due", -2), (18, 1, "pending_review", 9),
        (19, 0, "planned_due", -1), (19, 1, "evidence_missing", -5),
        (20, 1, "planned_due_today", 0), (21, 0, "pending_review", -2),
        (22, 0, "delayed", 10),
    ]
    for number, position, state, days_late in project_specs:
        due_date = today + timedelta(days=days_late)
        planned = today - timedelta(days=2) if state == "planned_due" else (
            today if state == "planned_due_today" else today + timedelta(days=10)
            if state == "delayed" else today - timedelta(days=8)
        )
        actual = today - timedelta(days=5) if state in ("evidence_missing", "pending_review") else None
        evidence = "現場写真提出済・審査待ち" if state == "pending_review" else None
        contract_id, _, _, _ = create_contract(
            number, position, 27_500_000,
            project=(planned, actual, None, evidence, due_date, state,
                     "工程調整後に確認予定" if state == "delayed" else None),
        )
        project_id = db.execute(
            "SELECT id FROM construction_projects WHERE contract_id=?", (contract_id,)
        ).fetchone()["id"]
        construction_queue.append((project_id, number, state, due_date))

    for number in range(23, 29):
        project = None
        fee_state = None
        if number in (23, 24):
            project = (today - timedelta(days=10), today - timedelta(days=4),
                       today - timedelta(days=2), "確認証跡を審査済み", today - timedelta(days=3),
                       "confirmed", None)
            fee_state = "Confirmed"
        create_contract(number, amount=28_000_000, project=project, fee_state=fee_state,
                        contract_date_override=today - timedelta(days=2) if number == 28 else None)

    for index, overdue_days in enumerate([1, 2, 3, 5, 6, 9]):
        number = index * 4 + 1
        home = spread_households[number]
        db.execute(
            """INSERT INTO tasks(assignee_id,title,due_at,source,related_household_id,task_type,
               priority,related_type,related_id) VALUES(?,?,?,'sla_auto',?,'followup',?,'household',?)""",
            (home["advisor_id"] or users["manager"], f"DEMO follow-up {home['code']}",
             today - timedelta(days=overdue_days), home["id"],
             "high" if index == 0 else "normal", home["id"]),
        )
    for index, number in enumerate((29, 30, 31, 32)):
        home = spread_households[number]
        intro_id = introductions_by_household[number][0][0]
        db.execute(
            """INSERT INTO tasks(assignee_id,title,due_at,source,related_household_id,task_type,
               related_type,related_id) VALUES(?,?,?,'sla_auto',?,'partner_feedback','introduction',?)""",
            (users["manager"], f"DEMO partner feedback {home['code']}",
             today - timedelta(days=(2, 3, 5, 9)[index]), home["id"], intro_id),
        )
    for project_id, number, state, due in construction_queue:
        home = spread_households[number]
        db.execute(
            """INSERT INTO tasks(assignee_id,title,due_at,source,related_household_id,task_type,
               related_type,related_id) VALUES(?,?,?,'sla_auto',?,'construction_queue','construction_project',?)""",
            (users["manager"], f"DEMO construction queue {project_id}", due, home["id"], project_id),
        )
    for number in (1, 14, 45, 46, 47):
        home = spread_households[number]
        db.execute(
            """INSERT INTO tasks(assignee_id,title,due_at,source,related_household_id,task_type,
               related_type,related_id) VALUES(?,?,?,'sla_auto',?,'appointment','household',?)""",
            (home["advisor_id"] or users["manager"], f"DEMO appointment {home['code']}",
             today, home["id"], home["id"]),
        )
    home = spread_households[2]
    db.execute(
        """INSERT INTO tasks(assignee_id,title,due_at,source,related_household_id,task_type,
           related_type,related_id) VALUES(?,?,?,'sla_auto',?,'followup','household',?)""",
        (home["advisor_id"], f"DEMO follow-up {home['code']}", today, home["id"], home["id"]),
    )
    for number in (4, 17, 35, 44):
        home = spread_households[number]
        db.execute(
            """INSERT INTO tasks(assignee_id,title,due_at,source,related_household_id,task_type,
               related_type,related_id) VALUES(?,?,?,'sla_auto',?,'unassigned','household',?)""",
            (users["manager"], f"DEMO unassigned {home['code']}", today, home["id"], home["id"]),
        )
    for number in (15, 25, 40):
        home = spread_households[number]
        intro_id = introductions_by_household[number][0][0]
        db.execute(
            "UPDATE introductions SET advisor_id=NULL WHERE id=?", (intro_id,)
        )
        db.execute(
            """INSERT INTO tasks(assignee_id,title,due_at,source,related_household_id,task_type,
               related_type,related_id) VALUES(?,?,?,'sla_auto',?,'unassigned','introduction',?)""",
            (users["manager"], f"DEMO unassigned introduction {home['code']}",
             today, home["id"], intro_id),
        )
    for number, task_type in (
        *((i, "fee_approval") for i in range(14, 18)),
        *((i, "invoice_generation") for i in (23, 24)),
        *((i, "invoice_unpaid") for i in range(9, 14)),
        *((i, "dispute") for i in range(6, 9)),
    ):
        home = spread_households[number]
        intro_id = introductions_by_household[number][0][0]
        entitlement = db.execute(
            "SELECT id FROM fee_entitlements WHERE introduction_id=?", (intro_id,)
        ).fetchone()
        db.execute(
            """INSERT INTO tasks(assignee_id,title,due_at,source,related_household_id,task_type,
               related_type,related_id) VALUES(?,?,?,'sla_auto',?,?,?,?)""",
            (users["hq_finance"], f"DEMO {task_type} {home['code']}", today, home["id"],
             task_type, "introduction" if task_type == "dispute" else "fee_entitlement",
             intro_id if task_type == "dispute" else entitlement["id"]),
        )

    receipt_blob = demo_receipt_pdf()
    expense_examples = [
        ("DRAFT", 0, "交通費", 4800, "相談会場への移動費", None, None),
        ("SUBMITTED", 1, "消耗品費", 13200, "面談資料の印刷費", None, None),
        ("APPROVED", 2, "会議費", 37500, "店舗内の業務打合せ費", None, None),
        ("REJECTED", 3, "交通費", 8900, "訪問同行の移動費", "申請内容の補足資料を確認してください。", None),
        ("RECORDED", 4, "消耗品費", 129800, "デモ用の架空申請・備品購入", None, "DEMO-FICTION-ACC-001"),
        ("RECORDED", 5, "会議費", 25100, "デモ用の架空申請・打合せ費", None, None),
        ("DRAFT", 6, "会議費", 6800, "相談準備の会場費", None, None),
        ("SUBMITTED", 7, "交通費", 15600, "住宅会社訪問の移動費", None, None),
        ("APPROVED", 8, "消耗品費", 44800, "顧客説明用の資料費", None, None),
        ("REJECTED", 9, "会議費", 52000, "相談会の会場費", "利用日と申請内容の確認が必要です。", None),
    ]
    for index, (status, store_index, category, amount, description, rejection, accounting_id) in enumerate(expense_examples):
        applicant_id = advisors[store_index]
        expense_date = today - timedelta(days=14 - index)
        created_at = datetime.combine(expense_date + timedelta(days=1), datetime.min.time())
        applied_at = None if status == "DRAFT" else created_at
        reviewed_at = created_at + timedelta(days=1) if status in ("APPROVED", "REJECTED", "RECORDED") else None
        recorded_at = reviewed_at if status == "RECORDED" else None
        receipt_filename = "demo_receipt_fictional.pdf" if index in (0, 1) else None
        receipt_reference = (f"架空の外部伝票 DEMO-REF-{index + 1:03}" if status == "RECORDED"
                             and not accounting_id else None)
        db.execute(
            """INSERT INTO expenses(id,applicant_id,store_id,category,amount,description,expense_date,
               receipt_filename,receipt_mime,receipt_size,receipt_sha256,receipt_blob,status,
               rejection_reason,applied_at,tax_amount,tax_category,reviewed_by,reviewed_at,
               finance_recorded_by,finance_recorded_at,accounting_integration_id,recorded_reference,
               recorded_confirmed_at,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (str(uuid.uuid4()), applicant_id, store_index + 1, category, amount,
             f"デモ用の架空申請です。{description}", expense_date, receipt_filename,
             "application/pdf" if receipt_filename else None,
             len(receipt_blob) if receipt_filename else None,
             hashlib.sha256(receipt_blob).hexdigest() if receipt_filename else None,
             receipt_blob if receipt_filename else None, status, rejection, applied_at,
             round(amount / 11), "課税10%（税込）",
             users["manager"] if reviewed_at else None, reviewed_at,
             users["hq_finance"] if recorded_at else None, recorded_at,
             accounting_id, receipt_reference, recorded_at, created_at, recorded_at or created_at),
        )

    previous_period = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    current_period = today.strftime("%Y-%m")
    for period, status, prepared_at, closed_at, snapshot in (
        (previous_period, "CLOSED", now - timedelta(days=20), now - timedelta(days=19),
         {"scope": ["expenses", "fee_entitlements", "contracts", "construction_projects"],
          "reprocessing_count": 0, "reprocessing_reason": None,
          "demo_note": "架空デモの月次締めサンプル"}),
        (current_period, "PREPARED", now - timedelta(days=1), None,
         {"scope": ["expenses", "fee_entitlements", "contracts", "construction_projects"],
          "reprocessing_count": 0, "reprocessing_reason": None,
          "demo_note": "架空デモの準備済み月次締めサンプル"}),
    ):
        snapshot_json = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest()
        db.execute(
            """INSERT INTO month_closes(id,period,snapshot_version,status,snapshot_json,
               snapshot_sha256,prepared_by,prepared_at,closed_by,closed_at,version)
               VALUES(?,?,1,?,?,?,?,?,?,?,1)""",
            (str(uuid.uuid4()), period, status, snapshot_json, digest, users["hq_finance"],
             prepared_at, users["executive"] if closed_at else None, closed_at),
        )

    for task_owner in db.execute(
        """SELECT assignee_id,MIN(id) AS task_id FROM tasks
           WHERE done=0 AND cancelled=0 GROUP BY assignee_id"""
    ).fetchall():
        task = db.execute(
            """SELECT title,due_at,related_type,related_id,related_household_id
               FROM tasks WHERE id=?""", (task_owner["task_id"],),
        ).fetchone()
        create_notification(
            db, task_owner["assignee_id"], "TASK", "対応が必要なタスクがあります",
            f"{task['title']}（期限: {task['due_at']}）",
            task["related_type"], task["related_id"],
            title_zh="有待处理的任务", message_zh=f"{task['title']}（截止日期：{task['due_at']}）",
        )

    for role, user_id in users.items():
        count = db.execute(
            "SELECT COUNT(*) FROM activities WHERE user_id=? AND DATE(acted_at)=CURRENT_DATE", (user_id,)
        ).fetchone()[0]
        db.execute(
            "INSERT INTO daily_report_drafts(user_id,report_date,auto_summary,manual_note) VALUES(?,?,?,?)",
            (user_id, today, f"本日の活動 {count} 件。デモデータを確認してください。", ""),
        )
    calendar_now = datetime.combine(today, datetime.min.time())
    db.execute(
        """INSERT INTO calendar_events(id,owner_id,title,event_type,starts_at,ends_at,all_day,
           visibility,store_id,created_by,updated_by,created_at,updated_at)
           VALUES(?,?,?,'meeting',?,?,0,'company',NULL,?,?,?,?)""",
        (str(uuid.uuid4()), users["manager"], "店舗運営ミーティング",
         calendar_now + timedelta(days=1, hours=10), calendar_now + timedelta(days=1, hours=11),
         users["manager"], users["manager"], now, now),
    )
    db.execute(
        """INSERT INTO bulletin_posts(id,post_type,title,body,author_id,visibility,status,pinned,
           published_at,created_at,updated_at) VALUES(?,'notice',?,? ,?,'company','published',1,?,?,?)""",
        (str(uuid.uuid4()), "デモ運用のお知らせ",
         "この投稿は架空のデモデータです。顧客情報や本番情報は含まれていません。",
         users["executive"], now, now, now),
    )
    db.execute(
        """INSERT INTO bulletin_posts(id,post_type,title,body,author_id,visibility,status,pinned,
           published_at,created_at,updated_at) VALUES(?,'meeting',?,? ,?,'company','published',0,?,?,?)""",
        (str(uuid.uuid4()), "店舗運営ミーティング記録",
         "期限が近い紹介対応と次回アクションの設定状況を確認しました。",
         users["manager"], now, now, now),
    )
    advisor_report = db.execute(
        "SELECT id,report_date,auto_summary,manual_note FROM daily_report_drafts WHERE user_id=? ORDER BY id LIMIT 1",
        (users["advisor"],),
    ).fetchone()
    if advisor_report:
        db.execute(
            """INSERT INTO bulletin_posts(id,post_type,title,body,author_id,store_id,visibility,status,
               published_at,created_at,updated_at,daily_report_user_id,daily_report_date)
               VALUES(?,'daily_report',?,?,?,?,'store','published',?,?,?,?,?)""",
            (str(uuid.uuid4()), f"{advisor_report['report_date']} 日報",
             "\n\n".join(value for value in (advisor_report["auto_summary"], advisor_report["manual_note"]) if value),
             users["advisor"], 1, now, now, now, users["advisor"], advisor_report["report_date"]),
        )
    db.execute(
        "INSERT INTO seed_metadata(id,batch_key,seeded_at) VALUES(1,?,?)",
        (SEED_BATCH, now),
    )


for attempt in range(60):
    try:
        with connect() as db:
            seed(db)
        break
    except pymysql.MySQLError:
        if attempt == 59:
            raise
        time.sleep(2)


def role_guard(role, allowed):
    if role not in allowed:
        raise HTTPException(403, "この操作を行う権限がありません")


def require_household_access(db, role, user, household_id):
    household = db.execute(
        "SELECT id,store_id,advisor_id FROM households WHERE id=?", (household_id,)
    ).fetchone()
    if not household:
        raise HTTPException(404, "家庭が見つかりません")
    if role == "advisor" and household["advisor_id"] != user["id"]:
        raise HTTPException(403, "担当世帯以外は操作できません")
    if role == "manager" and household["store_id"] != user["store_id"]:
        raise HTTPException(403, "自店舗以外の世帯は操作できません")
    if role == "hr":
        raise HTTPException(403, "人事アカウントから業務データへアクセスできません")
    return household


def role_scope(role, user, household_alias="h"):
    if role == "advisor":
        return f"{household_alias}.advisor_id=?", (user["id"],)
    if role == "manager":
        return f"{household_alias}.store_id=?", (user["store_id"],)
    if role == "hr":
        return "1=0", ()
    return "1=1", ()


def get_households(db, role, user):
    scope, args = role_scope(role, user)
    households = [dict(row) for row in db.execute(
        f"""SELECT h.*,s.name AS store_name,u.name AS advisor_name FROM households h
            LEFT JOIN stores s ON s.id=h.store_id LEFT JOIN users u ON u.id=h.advisor_id
            WHERE {scope} ORDER BY h.id""", args,
    )]
    for household in households:
        household_id = household["id"]
        household["persons"] = [dict(row) for row in db.execute(
            "SELECT * FROM persons WHERE household_id=? ORDER BY id", (household_id,)
        )]
        touches = [dict(row) for row in db.execute(
            "SELECT * FROM touches WHERE household_id=? ORDER BY touch_at,id", (household_id,)
        )]
        household["touches"] = touches
        household["first_touch"] = touches[0] if touches else None
        household["latest_touch"] = touches[-1] if touches else None
        household["stage_events"] = [dict(row) for row in db.execute(
            """SELECT e.*,u.name AS changed_by_name FROM stage_events e
               LEFT JOIN users u ON u.id=e.changed_by WHERE household_id=? ORDER BY changed_at,id""",
            (household_id,),
        )]
        household["activities"] = [dict(row) for row in db.execute(
            """SELECT a.*,u.name AS user_name FROM activities a LEFT JOIN users u ON u.id=a.user_id
               WHERE household_id=? ORDER BY acted_at DESC,id DESC""", (household_id,)
        )]
        household["introductions"] = [dict(row) for row in db.execute(
            """SELECT i.*,p.name AS partner_name,ps.name AS staff_name,ps.branch_name,
               n.id AS negotiation_id,n.status AS negotiation_status,n.last_activity_at,
               c.id AS contract_id,c.contract_date,c.contract_amount,cp.id AS project_id,
               cp.planned_start_date,cp.actual_start_date,cp.confirmed_start_date,
               cp.confirmation_evidence,cp.confirmation_due_date,cp.confirmation_status,
               cp.delayed_note,fe.id AS entitlement_id,fe.calculated_amount,
               fe.state AS entitlement_state,fe.dispute_reason,fe.invoice_data_generated,
               fe.reference_amount,fr.version AS rule_version,fr.params AS rule_params,fr.base AS rule_base,
               rd.id AS dispute_id,rd.dispute_type,rd.evidence_level,rd.status AS dispute_status,
               rd.due_date AS dispute_due_date,rd.decision_note
               FROM introductions i JOIN partners p ON p.id=i.partner_id
               LEFT JOIN partner_staff ps ON ps.id=i.partner_staff_id
               LEFT JOIN negotiations n ON n.introduction_id=i.id
               LEFT JOIN contracts c ON c.negotiation_id=n.id
               LEFT JOIN construction_projects cp ON cp.contract_id=c.id
               LEFT JOIN fee_entitlements fe ON fe.introduction_id=i.id
               LEFT JOIN fee_rules fr ON fr.id=fe.fee_rule_id
               LEFT JOIN referral_disputes rd ON rd.fee_entitlement_id=fe.id
               WHERE i.household_id=? ORDER BY i.id""", (household_id,)
        )]
        household["consents"] = [dict(row) for row in db.execute(
            """SELECT c.*,p.name AS partner_name FROM consents c
               LEFT JOIN partners p ON p.id=c.partner_id
               WHERE c.household_id=? ORDER BY c.granted_at DESC""", (household_id,)
        )]
        household["disclosures"] = [dict(row) for row in db.execute(
            "SELECT * FROM data_disclosures WHERE household_id=? ORDER BY disclosed_at DESC", (household_id,)
        )]
    return households


@app.get("/api/bootstrap")
def bootstrap(x_demo_role: CurrentActor = Depends(require_actor)):
    with connect() as db:
        user = request_user(db, x_demo_role)
        role = str(x_demo_role)
        roles = [
            {"id": "executive", "name": "社長"}, {"id": "administrator", "name": "管理者"},
            {"id": "hq_staff", "name": "本社担当"}, {"id": "store_manager", "name": "店長"},
            {"id": "advisor", "name": "顧問"}, {"id": "finance", "name": "財務"},
            {"id": "hr", "name": "人事"}, {"id": "owner", "name": "オーナー"},
        ]
        identity = {
            "user": {"id": user["id"], "public_id": user["public_id"],
                     "employee_code": user["employee_code"], "name": user["display_name"],
                     "role": user["role"], "store_id": user["store_id"],
                     "must_change_password": bool(user["must_change_password"])},
            "role": role, "account_role": user["role"], "roles": roles,
            "permissions": {
                "advisor": ["households.own", "activities.create", "introductions.create"],
                "manager": ["households.store", "construction.confirm", "tasks.store"],
                "hq_finance": ["fees.read", "fees.approve", "invoice_data.manage"],
                "executive": ["dashboard.all", "management.all", "construction.confirm"],
                "hr": ["accounts.read", "accounts.manage"],
                "owner": [],
            }.get(role, ["accounts.read", "accounts.manage"] if user["role"] in
                  ("administrator", "hr") else ["dashboard.all", "management.all"]),
            "menus": {"hr": ["accounts"], "owner": ["owner-portal"]}.get(user["role"], [
                "dashboard", "properties", "applications", "rent", "repairs", "settlements",
                "funds", "owner-portal", "team", "management", "settings",
            ]),
            "enums": {"stages": STAGES, "roles": [item["id"] for item in roles]},
            "environment": {"demo": demo_mode_enabled(),
                            "public_sample": public_sample_mode_enabled()},
        }
        if public_sample_mode_enabled():
            identity.update(
                households=[], introductions=[], contracts=[], construction=[],
                fees=[], entitlements=[],
                preferences=read_preferences(db, user["id"], role),
            )
        return identity


@app.get("/api/households")
def household_index(x_demo_role: CurrentActor = Depends(require_actor)):
    if x_demo_role == "hr":
        raise HTTPException(403, "人事アカウントから業務データへアクセスできません")
    with connect() as db:
        user = request_user(db, x_demo_role)
        households = get_households(db, x_demo_role, user)
        scope, args = role_scope(x_demo_role, user)
        entitlements = [dict(row) for row in db.execute(
            f"""SELECT fe.*,fr.version AS rule_version,fr.type AS rule_type,fr.params,fr.base,
                h.id AS household_id,h.representative_name,h.household_code,p.name AS partner_name,
                c.contract_amount,rd.id AS dispute_id,rd.dispute_type,rd.evidence_level,rd.status AS dispute_status
                FROM fee_entitlements fe JOIN contracts c ON c.id=fe.contract_id
                JOIN introductions i ON i.id=fe.introduction_id JOIN households h ON h.id=i.household_id
                JOIN partners p ON p.id=i.partner_id JOIN fee_rules fr ON fr.id=fe.fee_rule_id
                LEFT JOIN referral_disputes rd ON rd.fee_entitlement_id=fe.id
                WHERE {scope} ORDER BY fe.id""", args,
        )]
        store_scope = "store_id=?" if x_demo_role in ("advisor", "manager") else "1=1"
        stores_scope = "id=?" if x_demo_role in ("advisor", "manager") else "1=1"
        store_args = (user["store_id"],) if x_demo_role in ("advisor", "manager") else ()
        audit_filter = "WHERE a.user_id=?" if x_demo_role in ("advisor", "manager") else ""
        audit_args = (user["id"],) if audit_filter else ()
        daily = db.execute(
            "SELECT * FROM daily_report_drafts WHERE user_id=? ORDER BY id DESC LIMIT 1", (user["id"],)
        ).fetchone()
        return {
            "user": {"id": user["id"], "name": user["name"], "role": x_demo_role, "store_id": user["store_id"]},
            "stores": [dict(row) for row in db.execute(f"SELECT * FROM stores WHERE {stores_scope} ORDER BY id", store_args)],
            "advisors": [dict(row) for row in db.execute(
                f"SELECT id,name,store_id FROM users WHERE role='advisor' AND {store_scope} ORDER BY id",
                store_args,
            )],
            "partners": [dict(row) for row in db.execute("SELECT * FROM partners WHERE active=1 ORDER BY name")],
            "partner_staff": [dict(row) for row in db.execute("SELECT * FROM partner_staff ORDER BY partner_id,id")],
            "households": households, "entitlements": entitlements,
            "audit_logs": [dict(row) for row in db.execute(
                f"""SELECT a.*,u.name AS user_name FROM audit_logs a LEFT JOIN users u ON u.id=a.user_id
                    {audit_filter} ORDER BY a.`at` DESC LIMIT 50""", audit_args,
            )],
            "daily_report": dict(daily) if daily else None,
            "seed_batch": SEED_BATCH,
        }


@app.get("/api/households/search")
def search_households(q: str, x_demo_role: CurrentActor = Depends(require_actor)):
    if x_demo_role == "hr":
        raise HTTPException(403, "人事アカウントから業務データへアクセスできません")
    normalized = normalize_kana(q).casefold().strip()
    terms = [term for term in re.split(r"\s+", normalized) if term]
    if not terms or len(normalized) > 128:
        raise HTTPException(422, "検索語は1〜128文字で入力してください")
    code_terms = {
        term for term in terms
        if re.fullmatch(r"[a-z][a-z0-9-]*", term)
        and re.search(r"[a-z]", term)
        and re.search(r"\d", term)
    }
    terms = [term if term in code_terms else
             (re.sub(r"[^0-9]", "", term) if re.search(r"\d", term) else term)
             for term in terms]
    searchable_text = """LOWER(CONCAT_WS(' ',h.household_code,h.representative_name,h.kana,
        pe.name,pe.kana,pe.phone))"""
    clauses = []
    args = []
    for term in terms:
        if term in code_terms:
            clauses.append("LOWER(h.household_code)=?")
            args.append(term)
            continue
        digits = re.sub(r"\D", "", term)
        clause = f"(LOCATE(?,{searchable_text})>0"
        args.append(term)
        if len(digits) >= 4:
            clause += " OR EXISTS(SELECT 1 FROM persons pp WHERE pp.household_id=h.id AND LOCATE(?,REGEXP_REPLACE(COALESCE(pp.phone,''),'[^0-9]',''))>0)"
            args.append(digits)
        clauses.append(clause + ")")
    with connect() as db:
        user = request_user(db, x_demo_role)
        scope, scope_args = role_scope(x_demo_role, user)
        rows = db.execute(
            f"""SELECT DISTINCT h.id FROM households h
                LEFT JOIN persons pe ON pe.household_id=h.id
                WHERE {scope} AND ({' AND '.join(clauses)})
                ORDER BY h.id LIMIT 101""",
            (*scope_args, *args),
        ).fetchall()
    return {"household_ids": [row["id"] for row in rows[:100]], "truncated": len(rows) > 100}


def request_user(db, role):
    if isinstance(role, CurrentActor):
        user = db.execute("SELECT * FROM users WHERE id=? AND account_status='ACTIVE'",
                          (role.user_id,)).fetchone()
    else:
        if role not in LEGACY_ROLE_ALIASES:
            raise HTTPException(400, "不明なデモロールです")
        user = db.execute("SELECT * FROM users WHERE role=? ORDER BY id LIMIT 1", (role,)).fetchone()
    if not user:
        raise HTTPException(401, "認証が必要です")
    return user


def dashboard_counter(key, label, count, target_page, filter_value, unit_type="items"):
    return {
        "key": key, "label": label, "unit_type": unit_type, "count": int(count),
        "target_page": target_page, "filter": filter_value,
    }


@app.get("/api/dashboard/summary")
def dashboard_summary(x_demo_role: CurrentActor = Depends(require_actor)):
    with connect() as db:
        user = request_user(db, x_demo_role)
        counters = []
        if x_demo_role == "hr":
            counters = []
        elif x_demo_role == "advisor":
            counters.extend([
                dashboard_counter("today_followups", "今日フォロー", db.execute(
                    """SELECT COUNT(*) AS count FROM tasks WHERE assignee_id=? AND done=0 AND cancelled=0
                       AND due_at=CURRENT_DATE AND task_type='followup'""", (user["id"],)
                ).fetchone()["count"], "households", "tasks:today_followups"),
                dashboard_counter("overdue", "期限超過", db.execute(
                    """SELECT COUNT(*) AS count FROM tasks WHERE assignee_id=? AND done=0 AND cancelled=0
                       AND due_at<CURRENT_DATE""", (user["id"],)
                ).fetchone()["count"], "households", "tasks:overdue"),
                dashboard_counter("appointments", "本日来店", db.execute(
                    """SELECT COUNT(*) AS count FROM tasks WHERE assignee_id=? AND done=0 AND cancelled=0
                       AND due_at=CURRENT_DATE AND task_type='appointment'""", (user["id"],)
                ).fetchone()["count"], "households", "appointments:today"),
            ])
        elif x_demo_role == "manager":
            counters.extend([
                dashboard_counter("overdue", "店内期限超過", db.execute(
                    """SELECT COUNT(DISTINCT t.id) AS count FROM tasks t LEFT JOIN households h
                       ON h.id=t.related_household_id WHERE h.store_id=? AND t.done=0
                       AND t.cancelled=0 AND t.due_at<CURRENT_DATE""", (user["store_id"],)
                ).fetchone()["count"], "households", "tasks:overdue"),
                dashboard_counter("unassigned", "担当未割当", db.execute(
                    """SELECT COUNT(DISTINCT h.id) AS count FROM households h
                       LEFT JOIN introductions i ON i.household_id=h.id
                       WHERE h.store_id=? AND (h.advisor_id IS NULL OR i.advisor_id IS NULL)""",
                    (user["store_id"],),
                ).fetchone()["count"], "introductions", "unassigned"),
                dashboard_counter("appointments", "本日来店", db.execute(
                    """SELECT COUNT(DISTINCT t.id) AS count FROM tasks t JOIN households h ON h.id=t.related_household_id
                       WHERE h.store_id=? AND t.done=0 AND t.cancelled=0 AND t.task_type='appointment'
                       AND t.due_at=CURRENT_DATE""", (user["store_id"],)
                ).fetchone()["count"], "households", "appointments:today"),
            ])
        elif x_demo_role == "hq_finance":
            counters.extend([
                dashboard_counter("fee_approval", "報酬承認待ち", db.execute(
                    "SELECT COUNT(*) AS count FROM fee_entitlements WHERE state='Pending'"
                ).fetchone()["count"], "revenue", "entitlements:Pending"),
                dashboard_counter("invoice_generation", "請求データ生成待ち", db.execute(
                    """SELECT COUNT(*) AS count FROM fee_entitlements WHERE state='Confirmed'
                       AND invoice_data_generated=0"""
                ).fetchone()["count"], "revenue", "entitlements:invoice_data_pending"),
                dashboard_counter("invoice_unpaid", "請求済・未入金", db.execute(
                    "SELECT COUNT(*) AS count FROM fee_entitlements WHERE state='Invoiced'"
                ).fetchone()["count"], "revenue", "entitlements:Invoiced"),
            ])
        else:
            counters.extend([
                dashboard_counter("critical_risk", "重大業務リスク", db.execute(
                    """SELECT COUNT(*) AS count FROM tasks WHERE done=0 AND cancelled=0 AND priority='high'
                       AND due_at<CURRENT_DATE"""
                ).fetchone()["count"], "households", "tasks:critical"),
                dashboard_counter("disputes", "紹介帰属争議", db.execute(
                    "SELECT COUNT(*) AS count FROM introductions WHERE status='帰属争議中'"
                ).fetchone()["count"], "introductions", "disputed"),
                dashboard_counter("construction_queue", "着工確認滞留", construction_confirmation_backlog(db),
                                  "revenue", "construction:pending"),
            ])
        return {"role": x_demo_role, "generated_at": now_jst().isoformat(timespec="seconds"),
                "counters": counters, "construction_confirmation_backlog":
                    construction_confirmation_backlog(db, user["store_id"] if x_demo_role == "manager" else None)}


@app.get("/api/dashboard/my-tasks")
def dashboard_my_tasks(x_demo_role: CurrentActor = Depends(require_actor)):
    with connect() as db:
        user = request_user(db, x_demo_role)
        if x_demo_role == "advisor":
            where = "t.assignee_id=? AND t.done=0 AND t.cancelled=0"
            args = (user["id"],)
        elif x_demo_role == "manager":
            where = """(h.store_id=? OR (t.assignee_id=? AND t.task_type='notification_fallback'))
                       AND t.done=0 AND t.cancelled=0"""
            args = (user["store_id"], user["id"])
        elif x_demo_role == "hq_finance":
            where = """(t.task_type IN ('fee_approval','invoice_generation','invoice_unpaid','dispute')
                       OR (t.assignee_id=? AND t.task_type='notification_fallback'))
                       AND t.done=0 AND t.cancelled=0"""
            args = (user["id"],)
        elif x_demo_role == "executive":
            where = """((t.priority='high' AND t.due_at<CURRENT_DATE)
                       OR t.task_type IN ('dispute','construction_queue')
                       OR (t.assignee_id=? AND t.task_type='notification_fallback'))
                       AND t.done=0 AND t.cancelled=0"""
            args = (user["id"],)
        else:
            where = "1=0"
            args = ()
        rows = db.execute(
            f"""SELECT t.id AS task_id,t.title,t.related_type,t.related_id,t.related_household_id AS household_id,
                t.due_at,t.priority,t.status,
                DATEDIFF(CURRENT_DATE,t.due_at) AS days_overdue,t.task_type
                FROM tasks t LEFT JOIN households h ON h.id=t.related_household_id
                WHERE {where} ORDER BY (t.due_at<CURRENT_DATE) DESC,
                FIELD(t.priority,'high','normal','low'),t.due_at,t.id""", args,
        )
        return {"role": x_demo_role, "items": [
            {"task_id": row["task_id"], "title": row["title"], "related_type": row["related_type"],
             "related_id": row["related_id"], "due_at": row["due_at"],
             "household_id": row["household_id"],
             "days_overdue": max(0, int(row["days_overdue"] or 0)), "priority": row["priority"],
             "status": row["status"], "task_type": row["task_type"]}
            for row in rows
        ]}


@app.get("/api/dashboard/trends")
def dashboard_trends(metric: str = "inquiries", period: str = "7d",
                     x_demo_role: CurrentActor = Depends(require_actor)):
    if metric not in ("inquiries", "visits", "introductions", "contracts", "construction"):
        raise HTTPException(422, "不明な指標です")
    if period not in ("7d", "30d", "90d", "180d", "365d"):
        raise HTTPException(422, "不明な期間です")
    with connect() as db:
        user = request_user(db, x_demo_role)
        scope, args = role_scope(x_demo_role, user)
        if metric == "inquiries":
            query = f"""SELECT DATE(h.created_at) AS bucket,COUNT(*) AS value FROM households h
                        WHERE {scope} AND h.created_at>=? GROUP BY DATE(h.created_at)"""
        elif metric == "visits":
            query = f"""SELECT DATE(t.acted_at) AS bucket,COUNT(*) AS value FROM activities t
                        JOIN households h ON h.id=t.household_id
                        WHERE {scope} AND t.type IN ('面談','訪問同行') AND t.acted_at>=?
                        GROUP BY DATE(t.acted_at)"""
        elif metric == "introductions":
            query = f"""SELECT DATE(i.introduced_at) AS bucket,COUNT(*) AS value FROM introductions i
                        JOIN households h ON h.id=i.household_id WHERE {scope} AND i.introduced_at>=?
                        GROUP BY DATE(i.introduced_at)"""
        elif metric == "contracts":
            query = f"""SELECT DATE(c.contract_date) AS bucket,COUNT(*) AS value FROM contracts c
                        JOIN negotiations n ON n.id=c.negotiation_id
                        JOIN introductions i ON i.id=n.introduction_id JOIN households h ON h.id=i.household_id
                        WHERE {scope} AND c.contract_date>=? GROUP BY DATE(c.contract_date)"""
        else:
            query = f"""SELECT DATE(cp.confirmed_start_date) AS bucket,COUNT(*) AS value
                        FROM construction_projects cp JOIN contracts c ON c.id=cp.contract_id
                        JOIN negotiations n ON n.id=c.negotiation_id
                        JOIN introductions i ON i.id=n.introduction_id JOIN households h ON h.id=i.household_id
                        WHERE {scope} AND cp.confirmed_start_date>=? GROUP BY DATE(cp.confirmed_start_date)"""
        days = int(period[:-1])
        current_start = now_jst().date() - timedelta(days=days - 1)
        previous_start = current_start - timedelta(days=days)
        results = db.execute(query, (*args, previous_start)).fetchall()
        by_date = {row["bucket"].isoformat(): int(row["value"]) for row in results}
        current = [{"date": (current_start + timedelta(days=index)).isoformat(),
                    "value": by_date.get((current_start + timedelta(days=index)).isoformat(), 0)}
                   for index in range(days)]
        previous = sum(value for key, value in by_date.items() if key < current_start.isoformat())
        current_total = sum(point["value"] for point in current)
        if days >= 90:
            weeks = []
            for week in range((days + 6) // 7):
                start = current_start + timedelta(days=week * 7)
                end = min(start + timedelta(days=6), now_jst().date())
                weeks.append({"start": start.isoformat(), "value": sum(
                    value for key, value in by_date.items() if start.isoformat() <= key <= end.isoformat()
                )})
            current = weeks
        return {"metric": metric, "period": period, "current": current,
                "current_total": current_total, "previous_total": previous}


@app.get("/api/management/overview")
def management_overview(x_demo_role: CurrentActor = Depends(require_actor)):
    role_guard(x_demo_role, ("manager", "hq_finance", "executive"))
    with connect() as db:
        user = request_user(db, x_demo_role)
        store_filter = " AND h.store_id=?" if x_demo_role == "manager" else ""
        store_args = (user["store_id"],) if store_filter else ()
        store_clause = " WHERE s.id=?" if x_demo_role == "manager" else ""
        store_clause_args = (user["store_id"],) if store_clause else ()
        stores = db.execute(
            f"""SELECT s.id,s.name,s.opened_at,COUNT(DISTINCT h.id) AS households,
               COUNT(DISTINCT CASE WHEN e.to_stage IN ('紹介済','訪問・商談中') THEN h.id END) AS introductions,
               COUNT(DISTINCT CASE WHEN c.id IS NOT NULL THEN h.id END) AS contracts
               FROM stores s LEFT JOIN households h ON h.store_id=s.id
               LEFT JOIN stage_events e ON e.household_id=h.id
               LEFT JOIN introductions i ON i.household_id=h.id
               LEFT JOIN negotiations n ON n.introduction_id=i.id
               LEFT JOIN contracts c ON c.negotiation_id=n.id
               {store_clause} GROUP BY s.id ORDER BY s.id""", store_clause_args,
        ).fetchall()
        funnel_stages = [
               "反響", "新規予約", "初回相談済", "FP診断済", "紹介済",
               "訪問・商談中", "契約", "着工",
        ]
        funnel_start = now_jst().date() - timedelta(days=89)
        funnel_end = now_jst().date()
        funnel_rows = db.execute(
               f"""WITH cohort AS (
                       SELECT h.id,h.created_at AS intake_at FROM households h
                       WHERE h.created_at>=? AND h.created_at<?{store_filter}
                   )
                   SELECT e.to_stage,COUNT(DISTINCT h.id) AS count FROM cohort c
                   JOIN households h ON h.id=c.id
                   JOIN stage_events e ON e.household_id=h.id AND e.changed_at>=c.intake_at
                   WHERE 1=1{store_filter} GROUP BY e.to_stage""",
               (funnel_start, funnel_end + timedelta(days=1), *store_args, *store_args),
        ).fetchall()
        funnel_counts = {row["to_stage"]: int(row["count"]) for row in funnel_rows}
        funnel_counts["反響"] = int(db.execute(
            f"SELECT COUNT(DISTINCT h.id) AS count FROM households h WHERE h.created_at>=? AND h.created_at<?{store_filter}",
            (funnel_start, funnel_end + timedelta(days=1), *store_args),
        ).fetchone()["count"])
        funnel_counts["着工"] = int(db.execute(
            f"""SELECT COUNT(DISTINCT h.id) AS count FROM construction_projects cp
                JOIN contracts c ON c.id=cp.contract_id JOIN negotiations n ON n.id=c.negotiation_id
                JOIN introductions i ON i.id=n.introduction_id JOIN households h ON h.id=i.household_id
                WHERE cp.confirmed_start_date>=? AND cp.confirmed_start_date<=? AND cp.confirmed_start_date>=DATE(h.created_at){store_filter}""",
            (funnel_start, funnel_end, *store_args),
        ).fetchone()["count"])
        funnel = [
            {"stage": stage_name, "count": funnel_counts.get(stage_name, 0), "reference_value": True}
            for stage_name in funnel_stages
        ]
        dimensions = []
        if x_demo_role in ("hq_finance", "executive"):
            for row in db.execute(
                """SELECT h.store_id,COUNT(DISTINCT h.id) AS sample_size,
                   SUM(CASE WHEN h.representative_name<>'' AND h.area_pref<>'' AND
                     h.budget_band<>'' AND h.land_status<>'' THEN 1 ELSE 0 END) AS complete_households,
                   (SELECT COUNT(*) FROM tasks t JOIN households th ON th.id=t.related_household_id
                     WHERE th.store_id=h.store_id AND t.task_type='followup' AND t.cancelled=0) AS followup_total,
                   (SELECT COALESCE(SUM(t.done),0) FROM tasks t JOIN households th
                     ON th.id=t.related_household_id WHERE th.store_id=h.store_id
                     AND t.task_type='followup' AND t.cancelled=0) AS followup_complete,
                   COUNT(DISTINCT CASE WHEN EXISTS(SELECT 1 FROM activities a WHERE a.household_id=h.id
                     AND a.next_action IS NOT NULL AND a.next_action_due IS NOT NULL) THEN h.id END) AS next_action_set,
                   (SELECT COUNT(DISTINCT d.user_id) FROM daily_report_drafts d JOIN users u
                     ON u.id=d.user_id WHERE u.store_id=h.store_id AND d.report_date=CURRENT_DATE) AS report_submitted,
                   (SELECT COUNT(*) FROM users u WHERE u.store_id=h.store_id AND u.role='advisor') AS advisor_count,
                   COUNT(DISTINCT CASE WHEN EXISTS(SELECT 1 FROM activities a WHERE a.household_id=h.id)
                     THEN h.id END) AS responded
                   FROM households h GROUP BY h.store_id ORDER BY h.store_id"""
            ):
                sample_size = max(1, row["sample_size"])
                dimensions.append({
                    "store_id": row["store_id"], "sample_size": row["sample_size"],
                    "followup_rate": round(row["followup_complete"] / max(1, row["followup_total"]), 2),
                    "followup_sample_size": row["followup_total"],
                    "data_completeness": round(row["complete_households"] / sample_size, 2),
                    "next_action_rate": round(row["next_action_set"] / sample_size, 2),
                    "report_submission_rate": round(row["report_submitted"] / max(1, row["advisor_count"]), 2),
                    "response_rate": round(row["responded"] / sample_size, 2),
                })
        sla_days = {row["reminder_type"]: row["days_before"] for row in db.execute(
            "SELECT reminder_type,days_before FROM sla_settings"
        )}
        reminders = [
            {"key": "introduction_validity", "label": "紹介有効期間", "target_page": "introductions",
             "filter": "validity:due", "items": db.execute(
                f"""SELECT i.id,h.representative_name,i.valid_until AS due_at FROM introductions i
                    JOIN households h ON h.id=i.household_id WHERE i.valid_until BETWEEN CURRENT_DATE
                    AND DATE_ADD(CURRENT_DATE,INTERVAL ? DAY){store_filter}
                    ORDER BY i.valid_until LIMIT 20""", (sla_days["introduction_validity"],) + store_args).fetchall()},
            {"key": "construction_evidence", "label": "着工証拠提出期限", "target_page": "revenue",
             "filter": "construction:evidence_missing", "items": db.execute(
                f"""SELECT cp.id,h.representative_name,cp.confirmation_due_date AS due_at
                    FROM construction_projects cp JOIN contracts c ON c.id=cp.contract_id
                    JOIN negotiations n ON n.id=c.negotiation_id JOIN introductions i ON i.id=n.introduction_id
                    JOIN households h ON h.id=i.household_id WHERE cp.confirmation_status='evidence_missing'
                    AND cp.confirmation_due_date<=DATE_ADD(CURRENT_DATE,INTERVAL ? DAY)
                    {store_filter} ORDER BY cp.confirmation_due_date LIMIT 20""",
                (sla_days["construction_evidence"],) + store_args).fetchall()},
            {"key": "dispute_resolution", "label": "争議処理期限", "target_page": "revenue",
             "filter": "disputed", "items": db.execute(
                f"""SELECT d.id,h.representative_name,d.due_date AS due_at FROM referral_disputes d
                    JOIN fee_entitlements fe ON fe.id=d.fee_entitlement_id
                    JOIN introductions i ON i.id=fe.introduction_id JOIN households h ON h.id=i.household_id
                    WHERE d.status IN ('Open','UnderReview')
                    AND (d.due_date IS NULL OR d.due_date<=DATE_ADD(CURRENT_DATE,INTERVAL ? DAY)){store_filter}
                    ORDER BY d.due_date LIMIT 20""",
                (sla_days["dispute_resolution"],) + store_args).fetchall()},
            {"key": "agreement_renewal", "label": "提携契約更新期限", "target_page": "management",
             "filter": "agreements:expiring", "items": db.execute(
                """SELECT pa.id,p.name AS representative_name,pa.effective_to AS due_at
                   FROM partner_agreements pa JOIN partners p ON p.id=pa.partner_id
                   WHERE pa.effective_to BETWEEN CURRENT_DATE AND DATE_ADD(CURRENT_DATE,INTERVAL ? DAY)
                   ORDER BY pa.effective_to LIMIT 20""",
                (sla_days["agreement_renewal"],)).fetchall() if not store_filter else []},
            {"key": "fee_rule_validity", "label": "FeeRule適用期限", "target_page": "management",
             "filter": "fee_rules:expiring", "items": db.execute(
                """SELECT fr.id,fr.version AS representative_name,fr.effective_to AS due_at
                   FROM fee_rules fr WHERE fr.effective_to BETWEEN CURRENT_DATE
                   AND DATE_ADD(CURRENT_DATE,INTERVAL ? DAY) ORDER BY fr.effective_to LIMIT 20""",
                (sla_days["fee_rule_validity"],)).fetchall() if not store_filter else []},
        ]
        channels = [dict(row) for row in db.execute(
            f"""SELECT t.channel,COUNT(*) AS touches,COUNT(DISTINCT t.household_id) AS households,
               COUNT(DISTINCT CASE WHEN c.id IS NOT NULL THEN t.household_id END) AS contracts
               FROM touches t JOIN households h ON h.id=t.household_id
               LEFT JOIN introductions i ON i.household_id=h.id LEFT JOIN negotiations n ON n.introduction_id=i.id
               LEFT JOIN contracts c ON c.negotiation_id=n.id WHERE 1=1{store_filter}
               GROUP BY t.channel ORDER BY touches DESC""", store_args,
        )]
        cohort_rows = db.execute(
            f"""SELECT DATE_FORMAT(h.created_at,'%%Y-%%m') AS cohort,
               COUNT(DISTINCT h.id) AS households,
               COUNT(DISTINCT CASE WHEN EXISTS(SELECT 1 FROM stage_events e WHERE e.household_id=h.id
                 AND e.to_stage='新規予約' AND e.changed_at>=h.created_at
                 AND e.changed_at<?) THEN h.id END) AS reservation_households,
               COUNT(DISTINCT CASE WHEN EXISTS(SELECT 1 FROM stage_events e WHERE e.household_id=h.id
                 AND e.to_stage='紹介済' AND e.changed_at>=h.created_at
                 AND e.changed_at<?) THEN h.id END) AS introduction_households,
               COUNT(DISTINCT CASE WHEN EXISTS(SELECT 1 FROM stage_events e WHERE e.household_id=h.id
                 AND e.to_stage='契約' AND e.changed_at>=h.created_at
                 AND e.changed_at<?) THEN h.id END) AS contract_households,
               COUNT(DISTINCT CASE WHEN EXISTS(SELECT 1 FROM stage_events a JOIN stage_events b ON b.household_id=a.household_id
                 WHERE a.household_id=h.id AND a.to_stage='新規予約' AND b.to_stage='紹介済'
                 AND a.changed_at>=h.created_at AND a.changed_at<?
                 AND b.changed_at>=h.created_at AND b.changed_at<?) THEN h.id END) AS reservation_introduction_households,
               COUNT(DISTINCT CASE WHEN EXISTS(SELECT 1 FROM stage_events a JOIN stage_events b ON b.household_id=a.household_id
                 WHERE a.household_id=h.id AND a.to_stage='紹介済' AND b.to_stage='契約'
                 AND a.changed_at>=h.created_at AND a.changed_at<?
                 AND b.changed_at>=h.created_at AND b.changed_at<?) THEN h.id END) AS introduction_contract_households
               FROM households h WHERE 1=1{store_filter}
               GROUP BY cohort ORDER BY cohort""", (now_jst(),) * 7 + store_args,
        ).fetchall()
        cohorts = []
        for row in cohort_rows:
            cohort = dict(row)
            cohort["inquiries"] = cohort["households"]
            cohort["introductions"] = cohort["introduction_households"]
            cohort["contracts"] = cohort["contract_households"]
            reservation = cohort["reservation_households"]
            introductions_count = cohort["introduction_households"]
            cohort["inquiry_to_reservation"] = {
                "numerator": reservation, "denominator": cohort["households"],
                "rate": reservation / cohort["households"] if cohort["households"] else None,
            }
            cohort["reservation_to_introduction"] = {
                "numerator": cohort["reservation_introduction_households"],
                "denominator": reservation,
                "rate": cohort["reservation_introduction_households"] / reservation if reservation else None,
            }
            cohort["introduction_to_contract"] = {
                "numerator": cohort["introduction_contract_households"], "denominator": introductions_count,
                "rate": cohort["introduction_contract_households"] / introductions_count if introductions_count else None,
            }
            cohorts.append(cohort)
        partner_quality = [dict(row) for row in db.execute(
            f"""SELECT p.id,p.name,COUNT(DISTINCT i.id) AS introductions,
               COUNT(DISTINCT CASE WHEN fe.state='Disputed' THEN fe.id END) AS disputes,
               COUNT(DISTINCT CASE WHEN fe.state='Paid' THEN fe.id END) AS paid,
               COALESCE(SUM(CASE WHEN fe.state='Paid' THEN fe.calculated_amount ELSE 0 END),0) AS paid_amount
               FROM partners p LEFT JOIN introductions i ON i.partner_id=p.id
               LEFT JOIN households h ON h.id=i.household_id
               LEFT JOIN fee_entitlements fe ON fe.introduction_id=i.id WHERE 1=1{store_filter}
               GROUP BY p.id ORDER BY p.id""", store_args,
        )]
        store_results = []
        for row in stores:
            item = dict(row)
            opened = item["opened_at"]
            if opened:
                item["tenure_months"] = max(0, (now_jst().date().year - opened.year) * 12 + now_jst().date().month - opened.month)
            else:
                item["tenure_months"] = None
            item["case_volume_band"] = f"{(item['households'] // 5) * 5}–{(item['households'] // 5) * 5 + 4}"
            store_results.append(item)
        exception_specs = [
            ("overdue_followups", "households", "tasks:overdue",
             f"""SELECT t.id AS record_id,h.id AS household_id,h.representative_name,t.title,t.due_at
                 FROM tasks t JOIN households h ON h.id=t.related_household_id
                 WHERE t.task_type='followup' AND t.done=0 AND t.cancelled=0
                 AND t.due_at<CURRENT_DATE{store_filter} ORDER BY t.due_at,t.id""", store_args),
            ("partner_feedback", "introductions", "tasks:partner_feedback",
             f"""SELECT t.id AS record_id,h.id AS household_id,h.representative_name,t.title,t.due_at
                 FROM tasks t JOIN introductions i ON i.id=t.related_id
                 JOIN households h ON h.id=i.household_id WHERE t.task_type='partner_feedback'
                 AND t.done=0 AND t.cancelled=0 AND t.due_at<CURRENT_DATE{store_filter}
                 ORDER BY t.due_at,t.id""", store_args),
            ("unassigned_households", "households", "unassigned",
             f"""SELECT h.id AS record_id,h.id AS household_id,h.representative_name,
                 NULL AS title,NULL AS due_at FROM households h
                 WHERE h.advisor_id IS NULL{store_filter} ORDER BY h.id""", store_args),
            ("unassigned_introductions", "introductions", "unassigned",
             f"""SELECT i.id AS record_id,h.id AS household_id,h.representative_name,
                 p.name AS title,NULL AS due_at FROM introductions i
                 JOIN households h ON h.id=i.household_id JOIN partners p ON p.id=i.partner_id
                 WHERE i.advisor_id IS NULL{store_filter} ORDER BY i.id""", store_args),
            ("construction_confirmation", "revenue", "construction:pending",
             f"""SELECT cp.id AS record_id,h.id AS household_id,h.representative_name,
                 cp.confirmation_status AS title,cp.confirmation_due_date AS due_at
                 FROM construction_projects cp JOIN contracts c ON c.id=cp.contract_id
                 JOIN negotiations n ON n.id=c.negotiation_id
                 JOIN introductions i ON i.id=n.introduction_id
                 JOIN households h ON h.id=i.household_id
                 WHERE cp.planned_start_date<CURRENT_DATE AND cp.confirmed_start_date IS NULL
                 {store_filter} ORDER BY cp.confirmation_due_date,cp.id""", store_args),
            ("open_disputes", "introductions", "disputed",
             f"""SELECT d.id AS record_id,h.id AS household_id,h.representative_name,
                 d.dispute_type AS title,d.due_date AS due_at FROM referral_disputes d
                 JOIN fee_entitlements fe ON fe.id=d.fee_entitlement_id
                 JOIN introductions i ON i.id=fe.introduction_id
                 JOIN households h ON h.id=i.household_id
                 WHERE d.status IN ('Open','UnderReview'){store_filter}
                 ORDER BY d.due_date,d.id""", store_args),
            ("invoice_unpaid", "revenue", "state:Invoiced",
             f"""SELECT fe.id AS record_id,h.id AS household_id,h.representative_name,
                 fe.state AS title,fe.calculated_at AS due_at FROM fee_entitlements fe
                 JOIN introductions i ON i.id=fe.introduction_id
                 JOIN households h ON h.id=i.household_id
                 WHERE fe.state='Invoiced'{store_filter} ORDER BY fe.calculated_at,fe.id""", store_args),
        ]
        exception_cards = []
        for key, target_page, filter_value, query, query_args in exception_specs:
            rows = [dict(row) for row in db.execute(query, query_args)]
            exception_cards.append({
                "key": key, "count": len(rows), "target_page": target_page,
                "filter": filter_value, "items": rows[:20],
            })
        return {
            "stores": store_results,
            "funnel": funnel,
            "construction_confirmation_backlog": construction_confirmation_backlog(
                db, user["store_id"] if x_demo_role == "manager" else None),
            "exception_cards": exception_cards,
            "operations_dimensions": dimensions,
            "reminders": [{**item, "items": [dict(row) for row in item["items"]]} for item in reminders],
            "attribution": channels, "cohorts": cohorts, "partner_quality": partner_quality,
        }


class ManagementReportInput(BaseModel):
    report_type: str


@app.post("/api/management/reports")
def create_management_report(payload: ManagementReportInput,
                             actor: CurrentActor = Depends(require_actor)):
    role_guard(actor, ("manager", "hq_finance", "executive"))
    report_type = payload.report_type
    overview = management_overview(actor)
    if report_type == "operations":
        store_names = {item["id"]: item["name"] for item in overview["stores"]}
        headers = ["店舗 / 门店", "対象数 / 样本数", "フォロー実行率 / 跟进执行率",
                   "データ完全性 / 数据完整性", "次回アクション設定率 / 下次行动设置率",
                   "日報提出率 / 日报提交率", "顧客対応品質 / 客户响应质量"]
        rows = [[store_names.get(item["store_id"], ""), item["sample_size"],
                 item["followup_rate"], item["data_completeness"], item["next_action_rate"],
                 item["report_submission_rate"], item["response_rate"]]
                for item in overview["operations_dimensions"]]
        title = "店舗運営状況 / 门店运营情况"
    elif report_type == "funnel":
        headers = ["ステージ / 阶段", "世帯数 / 家庭数"]
        rows = [[item["stage"], item["count"]]
                for item in overview["funnel"]]
        title = "相談から着工確認までのファネル / 从咨询到开工确认的漏斗"
    elif report_type == "attribution":
        headers = ["チャネル / 渠道", "接点数 / 触点数", "世帯数 / 家庭数", "契約数 / 签约数"]
        rows = [[item["channel"], item["touches"], item["households"], item["contracts"]]
                for item in overview["attribution"]]
        title = "流入経路レポート / 来源渠道报告"
    elif report_type == "partner_quality":
        headers = ["住宅会社 / 住宅公司", "紹介数 / 介绍数", "争議数 / 争议数",
                   "入金済件数 / 已入金件数", "入金額 / 入金金额"]
        rows = [[item["name"], item["introductions"], item["disputes"],
                 item["paid"], item["paid_amount"]]
                for item in overview["partner_quality"]]
        title = "住宅会社別報酬処理品質 / 按住宅公司划分的报酬处理质量"
    else:
        raise HTTPException(422, "不明なレポートです")
    now = now_jst()
    with connect() as db:
        user = request_user(db, actor)
        actor_name = user.get("display_name") or user["name"]
        max_bytes = config_value(db, "export.max_pdf_mb") * 1024 * 1024
        render_settings = (
            config_value(db, "pdf.render_timeout_seconds"),
            config_value(db, "pdf.render_concurrency"),
            config_value(db, "pdf.render_max_pending"),
        )
    try:
        content = build_pdf_isolated(
            headers, rows, "management_report", now.isoformat(timespec="seconds"),
            actor_name, render_settings[0], render_settings[1], render_settings[2],
            context={"title": title},
        )
    except RuntimeError as error:
        LOGGER.warning("Management PDF report render failed: %s", error)
        if str(error) == "PDF_RENDER_QUEUE_FULL":
            raise HTTPException(503, "PDF出力が混雑しています。時間をおいて再度お試しください") from error
        raise HTTPException(500, "業務レポートPDFの生成に失敗しました") from error
    except TimeoutError as error:
        raise HTTPException(504, "業務レポートPDFの生成がタイムアウトしました") from error
    if len(content) > max_bytes:
        raise HTTPException(413, "出力ファイルが設定サイズ上限を超えています")
    content_hash = hashlib.sha256(content).hexdigest()
    with connect() as db:
        audit(
            db, actor.user_id, "management.report_generated", "management_report",
            report_type, f"rows={len(rows)}; sha256={content_hash}",
        )
    return Response(
        content=content, media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="sumaiboard_{report_type}_{now:%Y%m%d}.pdf"',
                 "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )


def read_preferences(db, user_id, role):
    row = db.execute("SELECT * FROM user_preferences WHERE user_id=?", (user_id,)).fetchone()
    return {
        "dashboard_widgets": json.loads(row["dashboard_widgets"]) if row else (
            ["tasks", "report"] if role == "advisor" else ["tasks", "overview", "trend"]
        ),
        "notification_preferences": json.loads(row["notification_preferences"]) if row else {"in_app": True, "email": False},
    }


@app.get("/api/preferences")
def get_preferences(x_demo_role: CurrentActor = Depends(require_actor)):
    with connect() as db:
        user = request_user(db, x_demo_role)
        return read_preferences(db, user["id"], x_demo_role)


class PreferencesInput(BaseModel):
    dashboard_widgets: list[str]
    notification_preferences: dict


@app.put("/api/preferences")
def put_preferences(payload: PreferencesInput, x_demo_role: CurrentActor = Depends(require_actor)):
    allowed_widgets = {"tasks", "overview", "trend", "report"}
    if len(payload.dashboard_widgets) > 4 or not set(payload.dashboard_widgets).issubset(allowed_widgets):
        raise HTTPException(422, "ダッシュボード設定が正しくありません")
    if (set(payload.notification_preferences) - {"in_app", "email"} or
            any(type(value) is not bool for value in payload.notification_preferences.values())):
        raise HTTPException(422, "通知設定が正しくありません")
    with connect() as db:
        user = request_user(db, x_demo_role)
        db.execute(
            """INSERT INTO user_preferences(user_id,dashboard_widgets,notification_preferences,updated_at)
               VALUES(?,?,?,?) ON DUPLICATE KEY UPDATE dashboard_widgets=VALUES(dashboard_widgets),
               notification_preferences=VALUES(notification_preferences),updated_at=VALUES(updated_at)""",
            (user["id"], json.dumps(payload.dashboard_widgets),
             json.dumps(payload.notification_preferences), datetime.now().isoformat(timespec="seconds")),
        )
        return {"ok": True}


class ActivityInput(BaseModel):
    household_id: int
    type: str
    body: str
    next_action: Optional[str] = None
    next_action_due: Optional[str] = None


@app.post("/api/activities")
def create_activity(payload: ActivityInput, x_demo_role: CurrentActor = Depends(require_actor)):
    with connect() as db:
        user = request_user(db, x_demo_role)
        require_household_access(db, x_demo_role, user, payload.household_id)
        assert_month_period_open(db, now_jst().date(), "activities")
        db.execute(
            """INSERT INTO activities(household_id,user_id,type,body,acted_at,next_action,next_action_due)
               VALUES(?,?,?,?,?,?,?)""",
            (payload.household_id, user["id"], payload.type, payload.body,
             datetime.now().isoformat(timespec="seconds"), payload.next_action, payload.next_action_due),
        )
        if payload.next_action and payload.next_action_due:
            overdue_task = db.execute(
                """SELECT id FROM tasks WHERE assignee_id=? AND related_household_id=?
                   AND task_type='followup' AND done=0 AND cancelled=0 AND due_at<CURRENT_DATE
                   ORDER BY due_at,id LIMIT 1""", (user["id"], payload.household_id),
            ).fetchone()
            if overdue_task:
                db.execute("UPDATE tasks SET done=1,status='done' WHERE id=?", (overdue_task["id"],))
        audit(db, user["id"], "activity.created", "household", payload.household_id, payload.type)
        db.commit()
    return {"ok": True}


def parse_local_datetime(value, field_name):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as error:
        raise HTTPException(422, f"{field_name}の日時が正しくありません") from error
    if parsed.tzinfo:
        parsed = parsed.astimezone(JST).replace(tzinfo=None)
    return parsed


class CalendarEventInput(BaseModel):
    title: str
    event_type: str
    starts_at: str
    ends_at: Optional[str] = None
    all_day: bool = False
    visibility: str = "private"
    version: Optional[int] = None


def validate_calendar_event(payload, actor, user):
    title = payload.title.strip()
    if not 1 <= len(title) <= 255:
        raise HTTPException(422, "予定のタイトルは1〜255文字で入力してください")
    if payload.event_type not in ("meeting", "business_trip", "personal"):
        raise HTTPException(422, "予定の種類が正しくありません")
    if payload.visibility not in ("private", "store", "company"):
        raise HTTPException(422, "予定の公開範囲が正しくありません")
    if payload.visibility == "store" and not user["store_id"]:
        raise HTTPException(422, "所属店舗が必要です")
    if payload.visibility == "company" and actor not in ("manager", "hq_finance", "executive"):
        raise HTTPException(403, "全社公開の予定を作成する権限がありません")
    starts_at = parse_local_datetime(payload.starts_at, "開始")
    ends_at = parse_local_datetime(payload.ends_at, "終了") if payload.ends_at else None
    if ends_at and ends_at <= starts_at:
        raise HTTPException(422, "終了日時は開始日時より後にしてください")
    if ends_at and ends_at - starts_at > timedelta(days=1):
        raise HTTPException(422, "予定は24時間以内で登録してください")
    return title, starts_at, ends_at


@app.get("/api/calendar")
def calendar_index(start: str, end: str, actor: CurrentActor = Depends(require_actor)):
    if actor == "hr":
        raise HTTPException(403, "人事アカウントから業務予定へアクセスできません")
    try:
        start_date, end_date = date.fromisoformat(start), date.fromisoformat(end)
    except ValueError as error:
        raise HTTPException(422, "表示期間を正しく指定してください") from error
    if end_date <= start_date or (end_date - start_date).days > 31:
        raise HTTPException(422, "表示期間は1〜31日で指定してください")
    range_start = datetime.combine(start_date, datetime.min.time())
    range_end = datetime.combine(end_date + timedelta(days=1), datetime.min.time())
    with connect() as db:
        user = request_user(db, actor)
        if actor == "advisor":
            visibility_sql = "(ce.owner_id=? OR ce.visibility='company' OR (ce.visibility='store' AND ce.store_id=?))"
            visibility_args = (user["id"], user["store_id"])
            user_sql, user_args = "u.id=?", (user["id"],)
            task_sql, task_args = "t.assignee_id=?", (user["id"],)
        elif actor == "manager":
            visibility_sql = "(ce.owner_id=? OR ce.visibility='company' OR (ce.visibility='store' AND ce.store_id=?))"
            visibility_args = (user["id"], user["store_id"])
            user_sql, user_args = "u.store_id=?", (user["store_id"],)
            task_sql, task_args = "(t.assignee_id=? OR h.store_id=?)", (user["id"], user["store_id"])
        elif actor == "hq_finance" and getattr(actor, "account_role", "") == "finance":
            visibility_sql = "(ce.owner_id=? OR ce.visibility='company')"
            visibility_args = (user["id"],)
            user_sql, user_args = "u.role IN ('finance','executive')", ()
            task_sql = "(t.assignee_id=? OR t.task_type IN ('fee_approval','invoice_generation','invoice_unpaid'))"
            task_args = (user["id"],)
        else:
            visibility_sql = "(ce.owner_id=? OR ce.visibility IN ('company','store'))"
            visibility_args = (user["id"],)
            user_sql, user_args = "u.role NOT IN ('hr')", ()
            task_sql, task_args = "1=1", ()
        events = [dict(row) for row in db.execute(
            f"""SELECT ce.id,ce.owner_id,COALESCE(u.display_name,u.name) AS owner_name,
                ce.title,ce.event_type,ce.starts_at,ce.ends_at,ce.all_day,ce.visibility,
                ce.store_id,ce.version,'manual' AS source_type,NULL AS source_id
                FROM calendar_events ce JOIN users u ON u.id=ce.owner_id
                WHERE {visibility_sql} AND ce.starts_at<? AND COALESCE(ce.ends_at,ce.starts_at)>=?
                ORDER BY ce.starts_at LIMIT 300""",
            (*visibility_args, range_end, range_start),
        )]
        task_rows = db.execute(
            f"""SELECT t.id,t.title,t.task_type,t.due_at,t.related_type,t.related_id,
                t.related_household_id,h.store_id,t.assignee_id,
                COALESCE(u.display_name,u.name) AS owner_name
                FROM tasks t LEFT JOIN households h ON h.id=t.related_household_id
                JOIN users u ON u.id=t.assignee_id
                WHERE {task_sql} AND t.done=0 AND t.cancelled=0 AND t.due_at>=? AND t.due_at<?
                ORDER BY t.due_at,t.id LIMIT 300""",
            (*task_args, start_date, end_date + timedelta(days=1)),
        ).fetchall()
        for row in task_rows:
            event_date = row["due_at"]
            event_type = "appointment" if row["task_type"] == "appointment" else "task_deadline"
            events.append({
                "id": f"task-{row['id']}", "owner_id": row["assignee_id"],
                "owner_name": row["owner_name"], "title": row["title"],
                "event_type": event_type, "starts_at": datetime.combine(
                    event_date, datetime.min.time()
                ), "ends_at": None, "all_day": True, "visibility": "authorized",
                "store_id": row["store_id"], "version": None, "source_type": row["related_type"],
                "source_id": row["related_id"], "household_id": row["related_household_id"],
                "task_id": row["id"],
            })
        employees = [dict(row) for row in db.execute(
            f"""SELECT u.id,COALESCE(u.display_name,u.name) AS name,u.role,u.store_id,s.name AS store_name
                FROM users u LEFT JOIN stores s ON s.id=u.store_id
                WHERE {user_sql} AND u.account_status='ACTIVE' ORDER BY u.store_id,u.display_name,u.id""",
            user_args,
        )]
        return {
            "range_start": start_date.isoformat(), "range_end": end_date.isoformat(),
            "timezone": "Asia/Tokyo", "events": events, "employees": employees,
        }


@app.post("/api/calendar")
def create_calendar_event(payload: CalendarEventInput, actor: CurrentActor = Depends(require_actor)):
    if actor == "hr":
        raise HTTPException(403, "予定を作成する権限がありません")
    with connect() as db:
        user = request_user(db, actor)
        title, starts_at, ends_at = validate_calendar_event(payload, actor, user)
        event_id, now = str(uuid.uuid4()), now_jst()
        store_id = user["store_id"] if payload.visibility == "store" else None
        db.execute(
            """INSERT INTO calendar_events(id,owner_id,title,event_type,starts_at,ends_at,all_day,
               visibility,store_id,created_by,updated_by,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (event_id, user["id"], title, payload.event_type, starts_at, ends_at,
             int(payload.all_day), payload.visibility, store_id, user["id"], user["id"], now, now),
        )
        audit(db, user["id"], "calendar_event.created", "calendar_event", event_id,
              f"type={payload.event_type}; visibility={payload.visibility}")
    return {"ok": True, "id": event_id}


@app.put("/api/calendar/{event_id}")
def update_calendar_event(event_id: str, payload: CalendarEventInput,
                          actor: CurrentActor = Depends(require_actor)):
    if actor == "hr":
        raise HTTPException(403, "予定を変更する権限がありません")
    with connect() as db:
        user = request_user(db, actor)
        current = db.execute(
            "SELECT id,version FROM calendar_events WHERE id=? AND owner_id=? FOR UPDATE",
            (event_id, user["id"]),
        ).fetchone()
        if not current:
            raise HTTPException(404, "予定が見つかりません")
        if payload.version is None or payload.version != current["version"]:
            raise HTTPException(409, "予定が更新されています。再読み込みしてください")
        title, starts_at, ends_at = validate_calendar_event(payload, actor, user)
        now = now_jst()
        store_id = user["store_id"] if payload.visibility == "store" else None
        db.execute(
            """UPDATE calendar_events SET title=?,event_type=?,starts_at=?,ends_at=?,all_day=?,
               visibility=?,store_id=?,updated_by=?,updated_at=?,version=version+1
               WHERE id=? AND version=?""",
            (title, payload.event_type, starts_at, ends_at, int(payload.all_day), payload.visibility,
             store_id, user["id"], now, event_id, payload.version),
        )
        audit(db, user["id"], "calendar_event.updated", "calendar_event", event_id,
              f"version={payload.version + 1}")
    return {"ok": True, "version": payload.version + 1}


class NegotiationActionInput(BaseModel):
    next_action: Optional[str] = None
    next_action_due: Optional[str] = None
    owner_id: Optional[int] = None
    risk_level: str = "none"
    version: int


@app.get("/api/negotiation-queue")
def negotiation_queue(actor: CurrentActor = Depends(require_actor)):
    if actor == "hr":
        raise HTTPException(403, "商談キューへアクセスする権限がありません")
    with connect() as db:
        user = request_user(db, actor)
        scope, args = role_scope(actor, user)
        rows = [dict(row) for row in db.execute(
            f"""SELECT n.id AS negotiation_id,n.introduction_id,n.status AS stage,
                n.next_action,n.next_action_due,n.risk_level,n.version,n.last_activity_at,
                i.advisor_id,h.id AS household_id,h.household_code,h.representative_name,
                h.store_id,s.name AS store_name,COALESCE(owner.display_name,owner.name) AS owner_name,
                n.next_action_owner_id AS owner_id,p.name AS partner_name
                FROM negotiations n JOIN introductions i ON i.id=n.introduction_id
                JOIN households h ON h.id=i.household_id
                LEFT JOIN stores s ON s.id=h.store_id
                LEFT JOIN users owner ON owner.id=n.next_action_owner_id
                JOIN partners p ON p.id=i.partner_id
                WHERE {scope} AND n.status NOT IN ('契約','見送り')
                ORDER BY CASE WHEN n.next_action_due<CURRENT_DATE THEN 0
                              WHEN n.next_action_due=CURRENT_DATE THEN 1
                              WHEN n.next_action_due IS NULL THEN 3 ELSE 2 END,
                         n.next_action_due,h.id,n.id LIMIT 500""", args,
        )]
        today = now_jst().date()
        for row in rows:
            due = row["next_action_due"]
            row["risk_level"] = (
                "high" if due and due < today else
                "watch" if row["risk_level"] == "watch" or
                (due and due <= today + timedelta(days=3)) else row["risk_level"]
            )
        return {"items": rows}


@app.put("/api/negotiation-queue/{negotiation_id}")
def update_negotiation_action(negotiation_id: int, payload: NegotiationActionInput,
                              actor: CurrentActor = Depends(require_actor)):
    role_guard(actor, ("advisor", "manager", "hq_finance", "executive"))
    action = payload.next_action.strip() if payload.next_action else ""
    if len(action) > 255 or bool(action) != bool(payload.next_action_due):
        raise HTTPException(422, "次の行動と期限を両方入力してください")
    if payload.risk_level not in ("none", "watch", "high"):
        raise HTTPException(422, "リスク区分が正しくありません")
    try:
        due_date = date.fromisoformat(payload.next_action_due) if payload.next_action_due else None
    except ValueError as error:
        raise HTTPException(422, "期限の日付が正しくありません") from error
    with connect() as db:
        user = request_user(db, actor)
        row = db.execute(
            """SELECT n.id,n.version,h.id AS household_id,h.store_id
               FROM negotiations n JOIN introductions i ON i.id=n.introduction_id
               JOIN households h ON h.id=i.household_id
               WHERE n.id=? FOR UPDATE""", (negotiation_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "商談が見つかりません")
        require_household_access(db, actor, user, row["household_id"])
        if payload.version != row["version"]:
            raise HTTPException(409, "商談が更新されています。再読み込みしてください")
        owner_id = payload.owner_id or user["id"]
        owner = db.execute(
            "SELECT id FROM users WHERE id=? AND role='advisor' AND store_id=? AND account_status='ACTIVE'",
            (owner_id, row["store_id"]),
        ).fetchone()
        if action and not owner:
            raise HTTPException(422, "担当者は同じ店舗の有効な顧問から選択してください")
        now = now_jst()
        db.execute(
            """UPDATE negotiations SET next_action=?,next_action_due=?,next_action_owner_id=?,
               risk_level=?,last_activity_at=?,version=version+1 WHERE id=? AND version=?""",
            (action or None, due_date, owner_id if action else None, payload.risk_level,
             now, negotiation_id, payload.version),
        )
        linked_task = db.execute(
            """SELECT id FROM tasks WHERE related_type='negotiation' AND related_id=?
               AND done=0 AND cancelled=0 ORDER BY id LIMIT 1 FOR UPDATE""",
            (negotiation_id,),
        ).fetchone()
        if action:
            task_priority = "high" if payload.risk_level == "high" else "normal"
            if linked_task:
                db.execute(
                    """UPDATE tasks SET assignee_id=?,title=?,due_at=?,related_household_id=?,
                       priority=?,status='open',done=0 WHERE id=?""",
                    (owner_id, action, due_date, row["household_id"], task_priority,
                     linked_task["id"]),
                )
            else:
                db.execute(
                    """INSERT INTO tasks(assignee_id,title,due_at,source,related_household_id,
                       task_type,priority,related_type,related_id,status)
                       VALUES(?,?,?,'negotiation_queue',?,'negotiation_action',?,'negotiation',?,'open')""",
                    (owner_id, action, due_date, row["household_id"], task_priority,
                     negotiation_id),
                )
        elif linked_task:
            db.execute("UPDATE tasks SET done=1,status='done' WHERE id=?", (linked_task["id"],))
        audit(db, user["id"], "negotiation.next_action.updated", "negotiation", negotiation_id,
              f"owner_id={owner_id if action else ''}; due={due_date or ''}; risk={payload.risk_level}")
    return {"ok": True, "version": payload.version + 1}


def bulletin_scope(actor, user, alias="p"):
    if actor == "advisor":
        return (
            f"({alias}.author_id=? OR {alias}.visibility='company' OR "
            f"({alias}.visibility='store' AND {alias}.store_id=?))",
            (user["id"], user["store_id"]),
        )
    if actor == "manager":
        return (
            f"({alias}.author_id=? OR {alias}.visibility='company' OR "
            f"({alias}.visibility='store' AND {alias}.store_id=?))",
            (user["id"], user["store_id"]),
        )
    if actor == "hr":
        return "1=0", ()
    return (
        f"({alias}.author_id=? OR {alias}.visibility IN ('company','store'))",
        (user["id"],),
    )


def accessible_bulletin_post(db, actor, user, post_id):
    scope, args = bulletin_scope(actor, user)
    post = db.execute(
        f"""SELECT p.*,COALESCE(u.display_name,u.name) AS author_name,s.name AS store_name
            FROM bulletin_posts p JOIN users u ON u.id=p.author_id
            LEFT JOIN stores s ON s.id=p.store_id
            WHERE p.id=? AND {scope}""",
        (post_id, *args),
    ).fetchone()
    if not post:
        raise HTTPException(404, "掲示板の投稿が見つかりません")
    return post


@app.get("/api/bulletin")
def bulletin_index(category: Optional[str] = None, q: Optional[str] = None,
                  month: Optional[str] = None, actor: CurrentActor = Depends(require_actor)):
    if actor == "hr":
        raise HTTPException(403, "掲示板へアクセスする権限がありません")
    if category and category not in ("daily_report", "meeting", "notice", "shared"):
        raise HTTPException(422, "投稿分類が正しくありません")
    search = (q or "").strip()
    if len(search) > 100:
        raise HTTPException(422, "検索語は100文字以内で入力してください")
    month_start = month_end = None
    if month:
        try:
            month_start = datetime.strptime(month, "%Y-%m").date().replace(day=1)
            month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        except ValueError as error:
            raise HTTPException(422, "年月を YYYY-MM 形式で指定してください") from error
    with connect() as db:
        user = request_user(db, actor)
        scope, args = bulletin_scope(actor, user)
        where = [scope, "(p.status='published' OR p.author_id=?)"]
        params = [*args, user["id"]]
        if category:
            where.append("p.post_type=?")
            params.append(category)
        if search:
            normalized = unicodedata.normalize("NFKC", search).casefold()
            where.append("LOCATE(?,LOWER(CONCAT_WS(' ',p.title,p.body)))>0")
            params.append(normalized)
        if month_start:
            where.append("p.published_at>=? AND p.published_at<?")
            params.extend((month_start, month_end))
        rows = [dict(row) for row in db.execute(
            f"""SELECT p.id,p.post_type,p.title,p.body,p.author_id,
                COALESCE(u.display_name,u.name) AS author_name,p.department,p.store_id,s.name AS store_name,
                p.visibility,p.status,p.pinned,p.published_at,p.created_at,p.updated_at
                FROM bulletin_posts p JOIN users u ON u.id=p.author_id
                LEFT JOIN stores s ON s.id=p.store_id
                WHERE {' AND '.join(where)} ORDER BY p.pinned DESC,p.published_at DESC,p.created_at DESC
                LIMIT 100""", params,
        )]
        if rows:
            ids = [row["id"] for row in rows]
            placeholders = ",".join("?" for _ in ids)
            comments = db.execute(
                f"""SELECT c.id,c.post_id,c.author_id,COALESCE(u.display_name,u.name) AS author_name,
                    c.body,c.created_at FROM bulletin_comments c JOIN users u ON u.id=c.author_id
                    WHERE c.post_id IN ({placeholders}) ORDER BY c.created_at,c.id""", ids,
            ).fetchall()
            grouped = {}
            for comment in comments:
                grouped.setdefault(comment["post_id"], []).append(dict(comment))
            for row in rows:
                row["comments"] = grouped.get(row["id"], [])
        return {"items": rows}


class BulletinPostInput(BaseModel):
    post_type: str
    title: str = ""
    body: str = ""
    visibility: str = "private"
    status: str = "published"
    department: Optional[str] = None
    pinned: bool = False
    report_date: Optional[str] = None


def validate_bulletin_access(actor, user, payload):
    if payload.post_type not in ("daily_report", "meeting", "notice", "shared"):
        raise HTTPException(422, "投稿分類が正しくありません")
    if payload.visibility not in ("private", "store", "company"):
        raise HTTPException(422, "公開範囲が正しくありません")
    if payload.status not in ("draft", "published"):
        raise HTTPException(422, "投稿状態が正しくありません")
    if payload.visibility == "store" and not user["store_id"]:
        raise HTTPException(422, "所属店舗が必要です")
    if payload.visibility == "company" and actor not in ("manager", "hq_finance", "executive"):
        raise HTTPException(403, "全社公開の投稿を作成する権限がありません")
    if payload.pinned and actor not in ("manager", "hq_finance", "executive"):
        raise HTTPException(403, "投稿を固定する権限がありません")
    if payload.post_type in ("meeting", "notice") and actor not in (
            "manager", "hq_finance", "executive"):
        raise HTTPException(403, "この分類の投稿を作成する権限がありません")


def daily_report_post_body(db, user_id, report_date):
    report = db.execute(
        """SELECT auto_summary,manual_note FROM daily_report_drafts
           WHERE user_id=? AND report_date=? ORDER BY id DESC LIMIT 1""",
        (user_id, report_date),
    ).fetchone()
    if not report:
        raise HTTPException(404, "対象日の日報ドラフトが見つかりません")
    return "\n\n".join(value for value in (report["auto_summary"], report["manual_note"]) if value).strip()


@app.post("/api/bulletin")
def create_bulletin_post(payload: BulletinPostInput, actor: CurrentActor = Depends(require_actor)):
    if actor == "hr":
        raise HTTPException(403, "投稿する権限がありません")
    with connect() as db:
        user = request_user(db, actor)
        validate_bulletin_access(actor, user, payload)
        if payload.post_type == "daily_report":
            try:
                report_date = date.fromisoformat(payload.report_date or now_jst().date().isoformat())
            except ValueError as error:
                raise HTTPException(422, "日報の日付が正しくありません") from error
            title = payload.title.strip() or f"{report_date.isoformat()} 日報"
            body = daily_report_post_body(db, user["id"], report_date)
            existing = db.execute(
                "SELECT id FROM bulletin_posts WHERE daily_report_user_id=? AND daily_report_date=?",
                (user["id"], report_date),
            ).fetchone()
            now = now_jst()
            if existing:
                db.execute(
                    """UPDATE bulletin_posts SET title=?,body=?,visibility=?,store_id=?,status=?,
                       published_at=?,updated_at=? WHERE id=?""",
                    (title, body, payload.visibility,
                     user["store_id"] if payload.visibility == "store" else None,
                     payload.status, now if payload.status == "published" else None, now, existing["id"]),
                )
                post_id = existing["id"]
                action = "bulletin.daily_report.updated"
            else:
                post_id = str(uuid.uuid4())
                db.execute(
                    """INSERT INTO bulletin_posts(id,post_type,title,body,author_id,department,store_id,
                       visibility,status,pinned,published_at,created_at,updated_at,daily_report_user_id,
                       daily_report_date) VALUES(?,'daily_report',?,?,?,NULL,?,?,?,0,?,?,?, ?,?)""",
                    (post_id, title, body, user["id"],
                     user["store_id"] if payload.visibility == "store" else None,
                     payload.visibility, payload.status,
                     now if payload.status == "published" else None, now, now, user["id"], report_date),
                )
                action = "bulletin.daily_report.published"
        else:
            title, body = payload.title.strip(), payload.body.strip()
            if not title or len(title) > 255 or not body or len(body) > 20000:
                raise HTTPException(422, "タイトルと本文を入力してください（本文は20,000文字以内）")
            now, post_id = now_jst(), str(uuid.uuid4())
            db.execute(
                """INSERT INTO bulletin_posts(id,post_type,title,body,author_id,department,store_id,
                   visibility,status,pinned,published_at,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (post_id, payload.post_type, title, body, user["id"],
                 payload.department.strip()[:120] if payload.department else None,
                 user["store_id"] if payload.visibility == "store" else None,
                 payload.visibility, payload.status, int(payload.pinned),
                 now if payload.status == "published" else None, now, now),
            )
            action = "bulletin.post.created"
        audit(db, user["id"], action, "bulletin_post", post_id,
              f"type={payload.post_type}; visibility={payload.visibility}; status={payload.status}")
    return {"ok": True, "id": post_id}


@app.put("/api/bulletin/{post_id}")
def update_bulletin_post(post_id: str, payload: BulletinPostInput,
                         actor: CurrentActor = Depends(require_actor)):
    if actor == "hr":
        raise HTTPException(403, "投稿を変更する権限がありません")
    with connect() as db:
        user = request_user(db, actor)
        post = accessible_bulletin_post(db, actor, user, post_id)
        if post["author_id"] != user["id"] or post["status"] == "archived":
            raise HTTPException(403, "投稿を変更する権限がありません")
        validate_bulletin_access(actor, user, payload)
        title, body = payload.title.strip(), payload.body.strip()
        if not title or len(title) > 255 or not body or len(body) > 20000:
            raise HTTPException(422, "タイトルと本文を入力してください（本文は20,000文字以内）")
        now = now_jst()
        db.execute(
            """UPDATE bulletin_posts SET title=?,body=?,department=?,visibility=?,store_id=?,
               pinned=?,status=?,published_at=IF(?='published',COALESCE(published_at,?),NULL),
               updated_at=? WHERE id=?""",
            (title, body, payload.department.strip()[:120] if payload.department else None,
             payload.visibility, user["store_id"] if payload.visibility == "store" else None,
             int(payload.pinned), payload.status, payload.status, now, now, post_id),
        )
        audit(db, user["id"], "bulletin.post.updated", "bulletin_post", post_id, "post updated")
    return {"ok": True}


@app.post("/api/bulletin/{post_id}/archive")
def archive_bulletin_post(post_id: str, actor: CurrentActor = Depends(require_actor)):
    if actor == "hr":
        raise HTTPException(403, "投稿をアーカイブする権限がありません")
    with connect() as db:
        user = request_user(db, actor)
        post = accessible_bulletin_post(db, actor, user, post_id)
        if post["author_id"] != user["id"] and actor not in (
                "manager", "hq_finance", "executive"):
            raise HTTPException(403, "投稿をアーカイブする権限がありません")
        db.execute(
            "UPDATE bulletin_posts SET status='archived',updated_at=? WHERE id=?",
            (now_jst(), post_id),
        )
        audit(db, user["id"], "bulletin.post.archived", "bulletin_post", post_id, "post archived")
    return {"ok": True}


@app.post("/api/bulletin/{post_id}/comments")
def create_bulletin_comment(post_id: str, payload: dict,
                            actor: CurrentActor = Depends(require_actor)):
    if actor == "hr":
        raise HTTPException(403, "コメントする権限がありません")
    body = payload.get("body")
    if not isinstance(body, str) or not body.strip() or len(body.strip()) > 4000:
        raise HTTPException(422, "コメントは1〜4,000文字で入力してください")
    with connect() as db:
        user = request_user(db, actor)
        post = accessible_bulletin_post(db, actor, user, post_id)
        if post["status"] != "published":
            raise HTTPException(409, "公開中の投稿にのみコメントできます")
        comment_id = db.execute(
            "INSERT INTO bulletin_comments(post_id,author_id,body,created_at) VALUES(?,?,?,?)",
            (post_id, user["id"], body.strip(), now_jst()),
        ).lastrowid
        audit(db, user["id"], "bulletin.comment.created", "bulletin_post", post_id,
              f"comment_id={comment_id}")
    return {"ok": True, "id": comment_id}


class IntroductionInput(BaseModel):
    household_id: int
    partner_id: int
    partner_staff_id: int


@app.post("/api/introductions")
def create_introduction(payload: IntroductionInput, x_demo_role: CurrentActor = Depends(require_actor)):
    if x_demo_role not in ("advisor", "manager", "hq_finance"):
        raise HTTPException(403, "権限がありません")
    with connect() as db:
        user = request_user(db, x_demo_role)
        household = require_household_access(db, x_demo_role, user, payload.household_id)
        assert_month_period_open(db, now_jst().date(), "introductions")
        staff = db.execute("SELECT id FROM partner_staff WHERE id=? AND partner_id=?",
                           (payload.partner_staff_id, payload.partner_id)).fetchone()
        if not household or not staff:
            raise HTTPException(404, "家庭または住宅会社担当者が見つかりません")
        now = datetime.now().isoformat(timespec="seconds")
        intro_id = db.execute(
            """INSERT INTO introductions(household_id,partner_id,partner_staff_id,introduced_at,status)
               VALUES(?,?,?,?,'紹介済')""",
            (payload.household_id, payload.partner_id, payload.partner_staff_id, now),
        ).lastrowid
        db.execute("INSERT INTO negotiations(introduction_id,status,last_activity_at) VALUES(?,'訪問予定',?)", (intro_id, now))
        latest = db.execute("SELECT to_stage FROM stage_events WHERE household_id=? ORDER BY changed_at DESC LIMIT 1",
                            (payload.household_id,)).fetchone()
        if not latest or latest["to_stage"] != "紹介済":
            db.execute(
                "INSERT INTO stage_events(household_id,from_stage,to_stage,changed_by,changed_at) VALUES(?,?,?, ?,?)",
                (payload.household_id, latest["to_stage"] if latest else None, "紹介済",
                 user["id"], now),
            )
        user_id = user["id"]
        audit(db, user_id, "introduction.created", "introduction", intro_id, f"partner={payload.partner_id}")
        db.commit()
    return {"ok": True, "introduction_id": intro_id}


REFERRAL_CONSENT_PURPOSE = "住宅会社への住宅紹介状作成"
REFERRAL_CONSENT_FIELDS = {
    "household_code", "area_pref", "budget_band", "land_status", "family_summary",
}
REFERRAL_TEMPLATE_VERSION = "referral-letter-v1"


class ReferralConsentInput(BaseModel):
    method: str
    evidence_reference: str
    confirmed: bool


class ConsentRevocationInput(BaseModel):
    reason: str


@app.post("/api/introductions/{introduction_id}/referral-consent")
def grant_referral_consent(introduction_id: int, payload: ReferralConsentInput,
                           actor: CurrentActor = Depends(require_actor)):
    role_guard(actor, ("advisor", "manager", "hq_finance", "executive"))
    methods = {"signed_form", "web_form", "recorded_call"}
    evidence_reference = payload.evidence_reference.strip()
    if not payload.confirmed or payload.method not in methods:
        raise HTTPException(422, "本人の同意確認と有効な同意方法が必要です")
    if not 3 <= len(evidence_reference) <= 255:
        raise HTTPException(422, "同意証跡の参照番号は3〜255文字で入力してください")
    now = now_jst()
    consent_id = None
    with connect() as db:
        user = request_user(db, actor)
        intro = db.execute(
            "SELECT id,household_id,partner_id FROM introductions WHERE id=?",
            (introduction_id,),
        ).fetchone()
        if not intro:
            raise HTTPException(404, "紹介記録が見つかりません")
        require_household_access(db, actor, user, intro["household_id"])
        active = db.execute(
            """SELECT id FROM consents WHERE household_id=? AND partner_id=? AND purpose=?
               AND scope='L3' AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at>?)""",
            (intro["household_id"], intro["partner_id"], REFERRAL_CONSENT_PURPOSE, now),
        ).fetchone()
        if active:
            raise HTTPException(409, "有効な紹介状作成同意が既に登録されています")
        consent_id = db.execute(
            """INSERT INTO consents(household_id,purpose,scope,granted_at,consent_method,
               content_version,allowed_fields_json,partner_id,expires_at,evidence_reference)
               VALUES(?,?, 'L3',?,?,?,?,?,?,?)""",
            (intro["household_id"], REFERRAL_CONSENT_PURPOSE, now, payload.method,
             "referral-consent-v1",
             json.dumps(sorted(REFERRAL_CONSENT_FIELDS), ensure_ascii=False),
             intro["partner_id"],
             now + timedelta(days=config_value(db, "pdf.referral_validity_days")),
             evidence_reference),
        ).lastrowid
        audit(
            db, actor.user_id, "referral_consent.granted", "consent", consent_id,
            f"introduction_id={introduction_id}; partner_id={intro['partner_id']}; method={payload.method}",
        )
    return {"ok": True, "consent_id": consent_id}


@app.post("/api/consents/{consent_id}/revoke")
def revoke_consent(consent_id: int, payload: ConsentRevocationInput,
                   actor: CurrentActor = Depends(require_actor)):
    role_guard(actor, ("advisor", "manager", "hq_finance", "executive"))
    reason = payload.reason.strip()
    if not 5 <= len(reason) <= 500:
        raise HTTPException(422, "同意取消理由は5〜500文字で入力してください")
    now = now_jst()
    with connect() as db:
        user = request_user(db, actor)
        consent = db.execute(
            "SELECT id,household_id,revoked_at,purpose FROM consents WHERE id=?",
            (consent_id,),
        ).fetchone()
        if not consent:
            raise HTTPException(404, "同意記録が見つかりません")
        require_household_access(db, actor, user, consent["household_id"])
        if consent["purpose"] != REFERRAL_CONSENT_PURPOSE:
            raise HTTPException(409, "紹介状作成目的以外の同意はこの操作で取消できません")
        if consent["revoked_at"]:
            raise HTTPException(409, "この同意は既に取消されています")
        db.execute("UPDATE consents SET revoked_at=? WHERE id=?", (now, consent_id))
        audit(db, actor.user_id, "referral_consent.revoked", "consent", consent_id, reason)
    return {"ok": True, "revoked_at": now}


def record_referral_generation_failure(actor, introduction_id, reason, result="FAILED"):
    generation_id = str(uuid.uuid4())
    with connect() as db:
        event_id = audit(
            db, actor.user_id, "referral_document.generation_failed", "introduction",
            introduction_id, reason,
        )
        db.execute(
            """INSERT INTO referral_document_generations(id,document_id,introduction_id,
               generated_by,requested_at,result,failure_reason,audit_event_id)
               VALUES(?,NULL,?,?,?,?,?,?)""",
            (generation_id, introduction_id, actor.user_id, now_jst(), result, reason, event_id),
        )


@app.get("/api/introductions/{introduction_id}/referral-documents")
def list_referral_documents(introduction_id: int,
                            actor: CurrentActor = Depends(require_actor)):
    role_guard(actor, ("advisor", "manager", "hq_finance", "executive"))
    with connect() as db:
        user = request_user(db, actor)
        intro = db.execute(
            "SELECT id,household_id,partner_id FROM introductions WHERE id=?", (introduction_id,)
        ).fetchone()
        if not intro:
            raise HTTPException(404, "紹介記録が見つかりません")
        require_household_access(db, actor, user, intro["household_id"])
        documents = [dict(row) for row in db.execute(
            """SELECT d.id,d.document_number,d.introduction_id,d.partner_id,d.recipient_name,
               d.issued_on,d.status,d.template_version,d.generated_at,d.expires_at,d.sha256,
               d.consent_id,d.issuing_store_id,d.advisor_id,d.generated_by,d.audit_event_id,
               f.status AS file_status,f.size_bytes,c.revoked_at AS consent_revoked_at,
               c.expires_at AS consent_expires_at
               FROM referral_documents d JOIN referral_document_files f ON f.id=d.file_id
               JOIN consents c ON c.id=d.consent_id
               WHERE d.introduction_id=? ORDER BY d.generated_at DESC""", (introduction_id,)
        )]
        generations = [dict(row) for row in db.execute(
            """SELECT id,document_id,requested_at,result,failure_reason
               FROM referral_document_generations WHERE introduction_id=?
               ORDER BY requested_at DESC""", (introduction_id,)
        )]
        consent = db.execute(
            """SELECT id,granted_at,expires_at,revoked_at,consent_method,evidence_reference
               FROM consents WHERE household_id=? AND partner_id=? AND purpose=? AND scope='L3'
               ORDER BY granted_at DESC,id DESC LIMIT 1""",
            (intro["household_id"], intro["partner_id"], REFERRAL_CONSENT_PURPOSE),
        ).fetchone()
        consent = dict(consent) if consent else None
        if consent:
            consent["active"] = (
                consent["revoked_at"] is None
                and (consent["expires_at"] is None or consent["expires_at"] > now_jst())
            )
        now = now_jst()
        for document in documents:
            if document["consent_revoked_at"] or (
                    document["consent_expires_at"] and document["consent_expires_at"] <= now):
                document["availability"] = "CONSENT_INACTIVE"
                document["availability_reason"] = "同意が取り消されたか、有効期限が切れています"
            elif document["expires_at"] <= now:
                document["availability"] = "EXPIRED"
                document["availability_reason"] = "有効期限が切れています"
            elif document["file_status"] != "AVAILABLE":
                document["availability"] = "UNAVAILABLE"
                document["availability_reason"] = "ファイルが保管されていません"
            else:
                document["availability"] = "AVAILABLE"
                document["availability_reason"] = None
    return {"documents": documents, "generations": generations, "consent": consent}


@app.post("/api/introductions/{introduction_id}/referral-documents")
def generate_referral_document(introduction_id: int,
                               actor: CurrentActor = Depends(require_actor)):
    role_guard(actor, ("advisor", "manager", "hq_finance", "executive"))
    now = now_jst()
    rejection = None
    context = None
    consent_id = None
    expires_at = None
    with connect() as db:
        user = request_user(db, actor)
        intro = db.execute(
            """SELECT i.id,i.household_id,i.partner_id,i.partner_staff_id,i.introduced_at,
               h.household_code,h.store_id,h.advisor_id,h.area_pref,h.budget_band,h.land_status,
               p.name AS partner_name,ps.name AS staff_name,ps.branch_name,
               s.name AS store_name,COALESCE(ad.display_name,ad.name) AS advisor_name
               FROM introductions i JOIN households h ON h.id=i.household_id
               JOIN partners p ON p.id=i.partner_id
               LEFT JOIN partner_staff ps ON ps.id=i.partner_staff_id
               LEFT JOIN stores s ON s.id=h.store_id
               LEFT JOIN users ad ON ad.id=COALESCE(i.advisor_id,h.advisor_id)
               WHERE i.id=?""", (introduction_id,),
        ).fetchone()
        if not intro:
            raise HTTPException(404, "紹介記録が見つかりません")
        require_household_access(db, actor, user, intro["household_id"])
        consent = db.execute(
            """SELECT id,granted_at,consent_method,content_version,allowed_fields_json
               FROM consents WHERE household_id=? AND partner_id=? AND purpose=? AND scope='L3'
               AND revoked_at IS NULL AND granted_at<=? AND (expires_at IS NULL OR expires_at>?)
               ORDER BY granted_at DESC,id DESC LIMIT 1""",
            (intro["household_id"], intro["partner_id"], REFERRAL_CONSENT_PURPOSE, now, now),
        ).fetchone()
        allowed_fields = []
        if consent and consent["allowed_fields_json"]:
            raw_fields = consent["allowed_fields_json"]
            allowed_fields = json.loads(raw_fields) if isinstance(raw_fields, str) else raw_fields
        if (not consent or not consent["consent_method"] or not consent["content_version"]
                or not REFERRAL_CONSENT_FIELDS.issubset(set(allowed_fields))):
            rejection = "有効な住宅会社別・紹介状作成目的のL3同意がありません"
        else:
            consent_id = consent["id"]
            document_id = str(uuid.uuid4())
            document_number = f"MB-RL-{now:%Y%m%d}-{document_id[:8].upper()}"
            family_rows = db.execute(
                "SELECT relation FROM persons WHERE household_id=? ORDER BY id",
                (intro["household_id"],),
            ).fetchall()
            relation_counts = {}
            for person in family_rows:
                relation = person["relation"] or "家族"
                relation_counts[relation] = relation_counts.get(relation, 0) + 1
            family_summary = "、".join(
                f"{relation} {count}名" for relation, count in relation_counts.items()
            )
            context = {
                "document_number": document_number,
                "recipient_name": " ".join(
                    part for part in (intro["partner_name"], intro["branch_name"], intro["staff_name"])
                    if part
                ),
                "issued_on": now.date().isoformat(),
                "introduced_at": str(intro["introduced_at"]),
                "household_code": intro["household_code"],
                "area_pref": intro["area_pref"],
                "budget_band": intro["budget_band"],
                "land_status": intro["land_status"],
                "family_summary": family_summary,
                "advisor_name": intro["advisor_name"] or "",
                "store_name": intro["store_name"] or "",
                "template_version": REFERRAL_TEMPLATE_VERSION,
            }
            expiry_days = config_value(db, "pdf.referral_validity_days")
            expires_at = now + timedelta(days=expiry_days)
            actor_name = user.get("display_name") or user["name"]
            render_settings = (
                config_value(db, "pdf.render_timeout_seconds"),
                config_value(db, "pdf.render_concurrency"),
                config_value(db, "pdf.render_max_pending"),
            )
    if rejection:
        record_referral_generation_failure(actor, introduction_id, "CONSENT_REQUIRED", "REJECTED")
        raise HTTPException(409, rejection)

    try:
        content = build_pdf_isolated(
            [], [], "referral_letter", now.isoformat(timespec="seconds"), actor_name,
            render_settings[0], render_settings[1], render_settings[2], context=context,
        )
    except RuntimeError as error:
        failure = "PDF_RENDER_QUEUE_FULL" if str(error) == "PDF_RENDER_QUEUE_FULL" else "PDF_RENDER_FAILED"
        record_referral_generation_failure(actor, introduction_id, failure)
        if failure == "PDF_RENDER_QUEUE_FULL":
            raise HTTPException(503, "PDF出力が混雑しています。時間をおいて再度お試しください") from error
        raise HTTPException(500, "紹介状PDFの生成に失敗しました") from error
    except TimeoutError as error:
        record_referral_generation_failure(actor, introduction_id, "PDF_RENDER_TIMEOUT")
        raise HTTPException(504, "紹介状PDFの生成がタイムアウトしました") from error

    file_id = str(uuid.uuid4())
    generation_id = str(uuid.uuid4())
    storage_key = f"{file_id}.pdf"
    final_path = REFERRAL_STORAGE_DIR / storage_key
    temp_path = REFERRAL_STORAGE_DIR / f"{file_id}.tmp"
    content_hash = hashlib.sha256(content).hexdigest()
    try:
        REFERRAL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        temp_path.write_bytes(content)
        temp_path.replace(final_path)
        with connect() as db:
            current_consent = db.execute(
                """SELECT id,consent_method,content_version,allowed_fields_json
                   FROM consents WHERE id=? AND household_id=? AND partner_id=?
                   AND purpose=? AND scope='L3' AND revoked_at IS NULL AND granted_at<=?
                   AND (expires_at IS NULL OR expires_at>?) FOR UPDATE""",
                (consent_id, intro["household_id"],
                 intro["partner_id"], REFERRAL_CONSENT_PURPOSE, now, now),
            ).fetchone()
            current_fields = []
            if current_consent and current_consent["allowed_fields_json"]:
                raw_fields = current_consent["allowed_fields_json"]
                current_fields = json.loads(raw_fields) if isinstance(raw_fields, str) else raw_fields
            if (not current_consent or not current_consent["consent_method"]
                    or not current_consent["content_version"]
                    or not REFERRAL_CONSENT_FIELDS.issubset(set(current_fields))):
                event_id = audit(
                    db, actor.user_id, "referral_document.generation_failed", "introduction",
                    introduction_id, "CONSENT_REVOKED_DURING_GENERATION",
                )
                db.execute(
                    """INSERT INTO referral_document_generations(id,document_id,introduction_id,
                       generated_by,requested_at,result,failure_reason,audit_event_id)
                       VALUES(?,NULL,?,?,?,?,?,?)""",
                    (generation_id, introduction_id, actor.user_id, now, "REJECTED",
                     "CONSENT_REVOKED_DURING_GENERATION", event_id),
                )
                rejection = "PDF生成中に同意が無効になりました。再度ご確認ください"
            else:
                event_id = audit(
                    db, actor.user_id, "referral_document.generated", "referral_document",
                    document_id, f"introduction_id={introduction_id}; consent_id={consent_id}; sha256={content_hash}",
                )
                db.execute(
                    """INSERT INTO referral_document_files(id,storage_key,size_bytes,sha256,status,created_at)
                       VALUES(?,?,?,?, 'AVAILABLE',?)""",
                    (file_id, storage_key, len(content), content_hash, now),
                )
                db.execute(
                    """INSERT INTO referral_documents(id,document_number,introduction_id,household_id,
                       partner_id,partner_staff_id,recipient_name,issuing_store_id,advisor_id,issued_on,
                       consent_id,status,template_version,generated_at,expires_at,sha256,file_id,
                       storage_reference,generated_by,generation_result,audit_event_id,created_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (document_id, context["document_number"], introduction_id, intro["household_id"],
                     intro["partner_id"], intro["partner_staff_id"], context["recipient_name"],
                     intro["store_id"], intro["advisor_id"], now.date(), consent_id, "ACTIVE",
                     REFERRAL_TEMPLATE_VERSION, now, expires_at, content_hash, file_id,
                     f"private://referral-documents/{storage_key}", actor.user_id, "SUCCESS",
                     event_id, now),
                )
                db.execute(
                    """INSERT INTO referral_document_generations(id,document_id,introduction_id,
                       generated_by,requested_at,result,audit_event_id)
                       VALUES(?,?,?,?,?,'SUCCESS',?)""",
                    (generation_id, document_id, introduction_id, actor.user_id, now, event_id),
                )
                disclosure_id = db.execute(
                    """INSERT INTO data_disclosures(household_id,disclosed_to,scope,disclosed_by,
                       disclosed_at,consent_id) VALUES(?,?,'L3',?,?,?)""",
                    (intro["household_id"],
                     f"partner:{intro['partner_id']}:{intro['partner_name']}",
                     actor.user_id, now, consent_id),
                ).lastrowid
                audit(
                    db, actor.user_id, "data_disclosure.created", "data_disclosure",
                    disclosure_id, f"document_id={document_id}; consent_id={consent_id}; scope=L3",
                )
                db.execute(
                    "UPDATE introductions SET referral_letter_id=? WHERE id=?",
                    (document_id, introduction_id),
                )
    except Exception:
        temp_path.unlink(missing_ok=True)
        final_path.unlink(missing_ok=True)
        raise
    if rejection:
        final_path.unlink(missing_ok=True)
        raise HTTPException(409, rejection)
    return {"ok": True, "document_id": document_id, "document_number": context["document_number"]}


@app.get("/api/referral-documents/{document_id}")
def get_referral_document(document_id: str, actor: CurrentActor = Depends(require_actor)):
    role_guard(actor, ("advisor", "manager", "hq_finance", "executive"))
    with connect() as db:
        user = request_user(db, actor)
        row = db.execute(
            """SELECT d.id,d.document_number,d.introduction_id,d.household_id,d.partner_id,
               d.recipient_name,d.issued_on,d.status,d.template_version,d.generated_at,d.expires_at,
               d.sha256,d.file_id,d.consent_id,d.issuing_store_id,d.advisor_id,d.generated_by,
               d.audit_event_id,f.status AS file_status,f.size_bytes,
               c.revoked_at AS consent_revoked_at,c.expires_at AS consent_expires_at
               FROM referral_documents d JOIN referral_document_files f ON f.id=d.file_id
               JOIN consents c ON c.id=d.consent_id
               WHERE d.id=?""", (document_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "紹介状が見つかりません")
        require_household_access(db, actor, user, row["household_id"])
        result = dict(row)
        consent_inactive = row["consent_revoked_at"] or (
            row["consent_expires_at"] and row["consent_expires_at"] <= now_jst()
        )
        result["availability"] = (
            "CONSENT_INACTIVE" if consent_inactive else
            "EXPIRED" if row["expires_at"] <= now_jst() else
            "AVAILABLE" if row["file_status"] == "AVAILABLE" else "UNAVAILABLE"
        )
        result["availability_reason"] = (
            "同意が取り消されたか、有効期限が切れています" if result["availability"] == "CONSENT_INACTIVE" else
            "有効期限が切れています" if result["availability"] == "EXPIRED" else
            "ファイルが保管されていません" if result["availability"] == "UNAVAILABLE" else None
        )
        result.pop("file_id")
        result.pop("file_status")
    return result


@app.get("/api/referral-documents/{document_id}/file")
def retrieve_referral_document(document_id: str, download: bool = False,
                               actor: CurrentActor = Depends(require_actor)):
    role_guard(actor, ("advisor", "manager", "hq_finance", "executive"))
    integrity_error = None
    access_error = None
    with connect() as db:
        user = request_user(db, actor)
        row = db.execute(
            """SELECT d.document_number,d.household_id,d.expires_at,d.sha256,f.storage_key,
               f.size_bytes,f.status AS file_status,c.revoked_at AS consent_revoked_at,
               c.expires_at AS consent_expires_at FROM referral_documents d
               JOIN referral_document_files f ON f.id=d.file_id
               JOIN consents c ON c.id=d.consent_id WHERE d.id=?""",
            (document_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "紹介状が見つかりません")
        require_household_access(db, actor, user, row["household_id"])
        if row["consent_revoked_at"] or (
                row["consent_expires_at"] and row["consent_expires_at"] <= now_jst()):
            audit(db, actor.user_id, "referral_document.access_denied", "referral_document",
                  document_id, "CONSENT_INACTIVE")
            access_error = "同意が取り消されたか、有効期限が切れているため利用できません"
        elif row["expires_at"] <= now_jst():
            raise HTTPException(410, "紹介状の有効期限が切れています")
        elif row["file_status"] != "AVAILABLE":
            raise HTTPException(410, "紹介状ファイルは利用できません")
        elif Path(row["storage_key"]).name != row["storage_key"]:
            raise HTTPException(500, "紹介状ファイルの保管情報が不正です")
        else:
            file_path = REFERRAL_STORAGE_DIR / row["storage_key"]
            try:
                content = file_path.read_bytes()
            except FileNotFoundError as error:
                raise HTTPException(410, "紹介状ファイルが見つかりません") from error
            if len(content) != row["size_bytes"] or not hmac.compare_digest(
                    hashlib.sha256(content).hexdigest(), row["sha256"]):
                db.execute(
                    "UPDATE referral_document_files SET status='QUARANTINED' WHERE storage_key=?",
                    (row["storage_key"],),
                )
                audit(db, actor.user_id, "referral_document.integrity_failed", "referral_document",
                      document_id, "FILE_HASH_OR_SIZE_MISMATCH")
                integrity_error = True
            else:
                audit(
                    db, actor.user_id,
                    "referral_document.downloaded" if download else "referral_document.previewed",
                    "referral_document", document_id, f"sha256={row['sha256']}",
                )
    if access_error:
        raise HTTPException(410, access_error)
    if integrity_error:
        raise HTTPException(410, "紹介状ファイルの整合性を確認できません")
    safe_name = f"{row['document_number']}.pdf"
    disposition = "attachment" if download else "inline"
    return Response(
        content=content, media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{safe_name}"',
                 "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )


@app.post("/api/referral-documents/cleanup")
def cleanup_referral_document_files(actor: CurrentActor = Depends(require_actor)):
    role_guard(actor, ("hq_finance", "executive"))
    now = now_jst()
    removed = 0
    with connect() as db:
        expired = db.execute(
            """SELECT f.id,f.storage_key,d.id AS document_id FROM referral_document_files f
               JOIN referral_documents d ON d.file_id=f.id
               WHERE f.status='AVAILABLE' AND d.expires_at<=?""", (now,),
        ).fetchall()
        for row in expired:
            file_path = REFERRAL_STORAGE_DIR / Path(row["storage_key"]).name
            file_path.unlink(missing_ok=True)
            db.execute(
                """UPDATE referral_document_files SET status='EXPIRED',deleted_at=?,
                   deletion_reason='RETENTION_EXPIRED' WHERE id=?""", (now, row["id"]),
            )
            audit(db, actor.user_id, "referral_document.file_expired", "referral_document",
                  row["document_id"], "RETENTION_EXPIRED")
            removed += 1
    return {"ok": True, "removed_files": removed}


class ConfirmInput(BaseModel):
    confirmed_start_date: str
    evidence: str


@app.post("/api/construction/{project_id}/confirm")
def confirm_construction(project_id: int, payload: ConfirmInput,
                         x_demo_role: CurrentActor = Depends(require_actor)):
    role_guard(x_demo_role, ("manager", "hq_finance", "executive"))
    with connect() as db:
        project = db.execute(
            """SELECT cp.*,c.contract_amount,i.id AS introduction_id,i.partner_id,h.id AS household_id,h.store_id
               FROM construction_projects cp JOIN contracts c ON c.id=cp.contract_id
               JOIN negotiations n ON n.id=c.negotiation_id
               JOIN introductions i ON i.id=n.introduction_id
               JOIN households h ON h.id=i.household_id WHERE cp.id=? FOR UPDATE""", (project_id,)
        ).fetchone()
        if not project:
            raise HTTPException(404, "着工プロジェクトが見つかりません")
        if project["confirmed_start_date"]:
            raise HTTPException(409, "この着工はすでに確認済みです")
        if x_demo_role == "manager":
            manager = request_user(db, x_demo_role)
            if project["store_id"] != manager["store_id"]:
                raise HTTPException(403, "自店舗以外の着工案件は処理できません")
        if not project["actual_start_date"]:
            raise HTTPException(409, "実際着工日が未登録です")
        if not payload.evidence.strip():
            raise HTTPException(422, "確認証跡を入力してください")
        assert_month_period_open(db, payload.confirmed_start_date, "construction_projects")
        rule = db.execute(
            """SELECT fr.* FROM partner_agreements pa JOIN fee_rules fr ON fr.id=pa.fee_rule_id
               WHERE pa.partner_id=? AND pa.status='active' AND pa.effective_from<=?
               AND (pa.effective_to IS NULL OR pa.effective_to>=?) ORDER BY pa.effective_from DESC LIMIT 1""",
            (project["partner_id"], now_jst().date().isoformat(), now_jst().date().isoformat()),
        ).fetchone()
        if not rule:
            raise HTTPException(409, "適用可能な報酬ルールがありません")
        params = json.loads(rule["params"])
        params = rule["params"]
        if isinstance(params, str):
            params = json.loads(params)
        if rule["type"] == "rate":
            amount = round(project["contract_amount"] * float(params["rate"]))
        elif rule["type"] == "fixed":
            amount = int(params["amount"])
        else:
            tiers = params["tiers"]
            amount = next((int(t["amount"]) for t in tiers if project["contract_amount"] <= t["up_to"]), int(tiers[-1]["amount"]))
        user_id = request_user(db, x_demo_role)["id"]
        existing_start_event = db.execute(
            "SELECT id FROM stage_events WHERE household_id=? AND to_stage='着工' LIMIT 1",
            (project["household_id"],),
        ).fetchone()
        db.execute("UPDATE construction_projects SET confirmed_start_date=?,confirmation_evidence=? WHERE id=?",
                   (payload.confirmed_start_date, payload.evidence.strip(), project_id))
        if not existing_start_event:
            previous_stage = db.execute(
                "SELECT to_stage FROM stage_events WHERE household_id=? ORDER BY changed_at DESC,id DESC LIMIT 1",
                (project["household_id"],),
            ).fetchone()
            db.execute(
                "INSERT INTO stage_events(household_id,from_stage,to_stage,changed_by,changed_at) VALUES(?,?,?,?,?)",
                (project["household_id"], previous_stage["to_stage"] if previous_stage else None,
                 "着工", user_id, now_jst()),
            )
        db.execute(
            """UPDATE tasks SET done=1,status='done' WHERE related_type='construction_project'
               AND related_id=? AND task_type='construction_queue'""", (project_id,)
        )
        existing = db.execute("SELECT id FROM fee_entitlements WHERE contract_id=?", (project["contract_id"],)).fetchone()
        if not existing:
            intro_status = db.execute("SELECT status FROM introductions WHERE id=?", (project["introduction_id"],)).fetchone()["status"]
            state = "Disputed" if intro_status == "帰属争议中" else "Confirmed"
            db.execute(
                """INSERT INTO fee_entitlements(contract_id,introduction_id,fee_rule_id,base_amount,
                   calculated_amount,state,dispute_reason,calculated_at,confirmed_by) VALUES(?,?,?,?,?,?,?,?,?)""",
                (project["contract_id"], project["introduction_id"], rule["id"], project["contract_amount"],
                 amount, state, "紹介帰属の確認中" if state == "Disputed" else None,
                 datetime.now().isoformat(timespec="seconds"), user_id),
            )
        audit(db, user_id, "construction.confirmed", "construction_project", project_id,
              f"evidence={payload.evidence.strip()}; fee={amount}")
        db.commit()
    return {"ok": True, "calculated_amount": amount, "rule_version": rule["version"]}


class EntitlementAction(BaseModel):
    action: str


@app.post("/api/entitlements/{entitlement_id}/action")
def entitlement_action(entitlement_id: int, payload: EntitlementAction,
                       x_demo_role: CurrentActor = Depends(require_actor)):
    role_guard(x_demo_role, ("hq_finance",))
    transitions = {"approve": ("Pending", "Confirmed"), "invoice": ("Confirmed", "Invoiced"),
                   "paid": ("Invoiced", "Paid")}
    if payload.action not in transitions:
        raise HTTPException(422, "不明な状態変更です")
    with connect() as db:
        entitlement = db.execute("SELECT * FROM fee_entitlements WHERE id=?", (entitlement_id,)).fetchone()
        if not entitlement:
            raise HTTPException(404, "報酬権利が見つかりません")
        source, target = transitions[payload.action]
        if entitlement["state"] != source:
            raise HTTPException(409, f"{source} 状態の報酬のみ処理できます")
        assert_month_period_open(db, entitlement["calculated_at"], "fee_entitlements")
        user_id = request_user(db, x_demo_role)["id"]
        db.execute(
            "UPDATE fee_entitlements SET state=?,invoice_data_generated=IF(?='Invoiced',1,invoice_data_generated) WHERE id=?",
            (target, target, entitlement_id),
        )
        task_type = {"approve": "fee_approval", "invoice": "invoice_generation", "paid": "invoice_unpaid"}[payload.action]
        db.execute(
            "UPDATE tasks SET done=1,status='done' WHERE related_type='fee_entitlement' AND related_id=? AND task_type=?",
            (entitlement_id, task_type),
        )
        audit(db, user_id, f"entitlement.{payload.action}", "fee_entitlement", entitlement_id, target)
        db.commit()
    return {"ok": True, "state": target}


class DisputeInput(BaseModel):
    reason: str
    evidence_level: str


@app.post("/api/introductions/{introduction_id}/dispute")
def raise_dispute(introduction_id: int, payload: DisputeInput,
                  x_demo_role: CurrentActor = Depends(require_actor)):
    with connect() as db:
        user = request_user(db, x_demo_role)
        intro = db.execute("SELECT id,household_id FROM introductions WHERE id=?", (introduction_id,)).fetchone()
        if not intro:
            raise HTTPException(404, "紹介記録が見つかりません")
        require_household_access(db, x_demo_role, user, intro["household_id"])
        if not payload.reason.strip():
            raise HTTPException(422, "争議理由を入力してください")
        entitlement = db.execute("SELECT * FROM fee_entitlements WHERE introduction_id=?", (introduction_id,)).fetchone()
        if entitlement and entitlement["state"] in ("Invoiced", "Paid"):
            raise HTTPException(409, "請求後の金額は争議状態に変更できません。調整記録が必要です")
        if entitlement:
            db.execute("UPDATE fee_entitlements SET state='Disputed',dispute_reason=? WHERE id=?",
                       (payload.reason.strip(), entitlement["id"]))
            db.execute(
                """INSERT INTO referral_disputes(fee_entitlement_id,raised_by,reason,evidence_level,status)
                   VALUES(?,?,?,?,'Open')""",
                (entitlement["id"], user["id"], payload.reason.strip(), payload.evidence_level),
            )
        db.execute("UPDATE introductions SET status='帰属争议中',existing_customer_flag=1,evidence_note=? WHERE id=?",
                   (payload.reason.strip(), introduction_id))
        audit(db, user["id"], "referral_dispute.raised", "introduction", introduction_id, payload.evidence_level)
        db.commit()
    return {"ok": True}


class DisputeDecisionInput(BaseModel):
    decision: str
    decision_note: str


@app.post("/api/referral-disputes/{dispute_id}/decision")
def decide_referral_dispute(dispute_id: int, payload: DisputeDecisionInput,
                            x_demo_role: CurrentActor = Depends(require_actor)):
    role_guard(x_demo_role, ("hq_finance",))
    if payload.decision not in ("confirm", "write_off", "reassessment"):
        raise HTTPException(422, "不明な裁定です")
    note = payload.decision_note.strip()
    if len(note) < 5:
        raise HTTPException(422, "裁定理由を5文字以上で入力してください")
    with connect() as db:
        user = request_user(db, x_demo_role)
        dispute = db.execute(
            """SELECT d.*,fe.introduction_id FROM referral_disputes d
               JOIN fee_entitlements fe ON fe.id=d.fee_entitlement_id WHERE d.id=?""",
            (dispute_id,),
        ).fetchone()
        if not dispute:
            raise HTTPException(404, "争議記録が見つかりません")
        if dispute["status"] in ("Decided", "WrittenOff"):
            raise HTTPException(409, "裁定済みの争議です")
        target_status = "Reassessment" if payload.decision == "reassessment" else "Decided"
        db.execute(
            """UPDATE referral_disputes SET status=?,decided_by=?,decided_at=?,decision_note=?
               WHERE id=?""",
            (target_status, user["id"], datetime.now().isoformat(timespec="seconds"), note, dispute_id),
        )
        if payload.decision == "confirm":
            db.execute(
                "UPDATE fee_entitlements SET state='Confirmed',dispute_reason=NULL WHERE id=?",
                (dispute["fee_entitlement_id"],),
            )
            db.execute(
                "UPDATE introductions SET status='受付確認済' WHERE id=?", (dispute["introduction_id"],)
            )
        elif payload.decision == "write_off":
            db.execute(
                "UPDATE fee_entitlements SET state='WrittenOff' WHERE id=?", (dispute["fee_entitlement_id"],)
            )
            db.execute("UPDATE introductions SET status='見送り' WHERE id=?", (dispute["introduction_id"],))
        if payload.decision != "reassessment":
            db.execute(
                """UPDATE tasks SET done=1,status='done' WHERE related_type='introduction'
                   AND related_id=? AND task_type='dispute'""", (dispute["introduction_id"],)
            )
        audit(db, user["id"], "referral_dispute.decided", "referral_dispute", dispute_id,
              f"decision={payload.decision}; {note}")
        db.commit()
    return {"ok": True, "status": target_status}


CORRECTABLE_HOUSEHOLD_FIELDS = {
    "representative_name": 120, "area_pref": 255, "budget_band": 120, "land_status": 40,
}


class DataCorrectionInput(BaseModel):
    field_name: str
    requested_value: str
    reason: str


class DataCorrectionDecisionInput(BaseModel):
    version: int
    action: str
    note: str = ""


class DataDisclosureInput(BaseModel):
    partner_id: int
    scope: str
    consent_id: int


@app.post("/api/households/{household_id}/disclosures")
def create_data_disclosure(household_id: int, payload: DataDisclosureInput,
                           actor: CurrentActor = Depends(require_actor)):
    role_guard(actor, ("advisor", "manager", "hq_finance", "executive"))
    if payload.scope not in ("L2", "L3"):
        raise HTTPException(422, "第三者提供ではL2またはL3の範囲のみ指定できます")
    with connect() as db:
        user = request_user(db, actor)
        require_household_access(db, actor, user, household_id)
        partner = db.execute(
            "SELECT id,name FROM partners WHERE id=? AND active=1", (payload.partner_id,)
        ).fetchone()
        if not partner:
            raise HTTPException(404, "有効な住宅会社が見つかりません")
        consent = db.execute(
            """SELECT id FROM consents WHERE id=? AND household_id=? AND scope=?
               AND revoked_at IS NULL""",
            (payload.consent_id, household_id, payload.scope),
        ).fetchone()
        if not consent:
            raise HTTPException(409, "同じ範囲の有効な同意が必要です")
        disclosed_at = now_jst()
        disclosure_id = db.execute(
            """INSERT INTO data_disclosures(household_id,disclosed_to,scope,disclosed_by,
               disclosed_at,consent_id) VALUES(?,?,?,?,?,?)""",
            (household_id, f"partner:{partner['id']}:{partner['name']}", payload.scope,
             user["id"], disclosed_at, consent["id"]),
        ).lastrowid
        audit(db, user["id"], "data_disclosure.created", "data_disclosure", disclosure_id,
              f"household_id={household_id}; partner_id={partner['id']}; scope={payload.scope}; consent_id={consent['id']}")
    return {"ok": True, "id": disclosure_id, "scope": payload.scope}


@app.post("/api/households/{household_id}/data-corrections")
def create_data_correction(household_id: int, payload: DataCorrectionInput,
                           actor: CurrentActor = Depends(require_actor)):
    role_guard(actor, ("advisor", "manager", "hq_finance", "executive"))
    if payload.field_name not in CORRECTABLE_HOUSEHOLD_FIELDS:
        raise HTTPException(422, "修正できない項目です")
    value = payload.requested_value.strip()
    reason = payload.reason.strip()
    if not value or len(value) > CORRECTABLE_HOUSEHOLD_FIELDS[payload.field_name]:
        raise HTTPException(422, "修正値の長さが正しくありません")
    if not 10 <= len(reason) <= 500:
        raise HTTPException(422, "修正理由は10〜500文字で入力してください")
    if payload.field_name == "land_status" and value not in ("有", "無", "検討中"):
        raise HTTPException(422, "土地状況の値が正しくありません")
    request_id = str(uuid.uuid4())
    now = now_jst()
    with connect() as db:
        user = request_user(db, actor)
        household = require_household_access(db, actor, user, household_id)
        current = db.execute(
            f"SELECT `{payload.field_name}` AS value FROM households WHERE id=?", (household_id,)
        ).fetchone()["value"]
        if (current or "") == value:
            raise HTTPException(409, "現在値と修正値が同じです")
        db.execute(
            """INSERT INTO data_correction_requests(id,household_id,field_name,before_value,
               requested_value,reason,requested_by,requested_at,status,version)
               VALUES(?,?,?,?,?,?,?,?,'PENDING',1)""",
            (request_id, household_id, payload.field_name, current, value, reason, user["id"], now),
        )
        audit(db, user["id"], "data_correction.requested", "data_correction", request_id,
              f"household_id={household_id}; field={payload.field_name}; reason={reason}")
        approvers = db.execute(
            """SELECT id FROM users WHERE account_status='ACTIVE' AND id<>? AND
               ((role='store_manager' AND store_id=?) OR role IN ('finance','executive','administrator'))""",
            (user["id"], household["store_id"]),
        ).fetchall()
        for approver in approvers:
            create_notification(
                db, approver["id"], "DATA_CORRECTION", "顧客データ修正の確認待ち",
                f"{household_id} の {payload.field_name} 修正依頼を確認してください。",
                "data_correction", request_id, title_zh="客户数据修正待审核",
                message_zh=f"请审核家庭 {household_id} 的 {payload.field_name} 修正申请。",
            )
    return {"ok": True, "id": request_id, "status": "PENDING", "version": 1}


@app.get("/api/data-corrections")
def data_correction_list(status: str = "PENDING", actor: CurrentActor = Depends(require_actor)):
    if status not in ("PENDING", "APPROVED", "REJECTED", "ALL"):
        raise HTTPException(422, "不明な修正依頼状態です")
    with connect() as db:
        user = request_user(db, actor)
        scope, args = role_scope(actor, user)
        status_filter = "" if status == "ALL" else "AND d.status=?"
        query_args = args if status == "ALL" else (*args, status)
        rows = db.execute(
            f"""SELECT d.id,d.household_id,h.household_code,h.representative_name,d.field_name,
                       d.before_value,d.requested_value,d.reason,d.requested_by,ru.display_name AS requester_name,
                       d.requested_at,d.status,d.decided_by,d.decided_at,d.decision_note,d.version
                FROM data_correction_requests d JOIN households h ON h.id=d.household_id
                JOIN users ru ON ru.id=d.requested_by WHERE {scope} {status_filter}
                ORDER BY (d.status='PENDING') DESC,d.requested_at DESC LIMIT 200""",
            query_args,
        ).fetchall()
    return {"items": [dict(row) for row in rows]}


@app.post("/api/data-corrections/{request_id}/decision")
def decide_data_correction(request_id: str, payload: DataCorrectionDecisionInput,
                           actor: CurrentActor = Depends(require_actor)):
    if payload.action not in ("approve", "reject"):
        raise HTTPException(422, "不明な修正処理です")
    if actor not in ("manager", "hq_finance", "executive"):
        raise HTTPException(403, "修正依頼を判断する権限がありません")
    note = payload.note.strip()
    if len(note) > 500:
        raise HTTPException(422, "処理メモは500文字以内で入力してください")
    if payload.action == "reject" and not 10 <= len(note) <= 500:
        raise HTTPException(422, "差し戻し理由は10〜500文字で入力してください")
    now = now_jst()
    with connect() as db:
        request = db.execute(
            """SELECT d.*,h.store_id,h.household_code,h.`representative_name`,h.`area_pref`,
               h.`budget_band`,h.`land_status`
               FROM data_correction_requests d JOIN households h ON h.id=d.household_id
               WHERE d.id=? FOR UPDATE""", (request_id,),
        ).fetchone()
        if not request:
            raise HTTPException(404, "修正依頼が見つかりません")
        if request["status"] != "PENDING":
            raise HTTPException(409, "未処理の修正依頼ではありません")
        if request["version"] != payload.version:
            raise HTTPException(409, "修正依頼が更新されています。再読み込みしてください")
        if request["requested_by"] == actor.user_id:
            raise HTTPException(403, "申請者自身は修正依頼を判断できません")
        if actor == "manager" and actor.store_id != request["store_id"]:
            raise HTTPException(403, "他店舗の修正依頼は判断できません")
        field_name = request["field_name"]
        if field_name not in CORRECTABLE_HOUSEHOLD_FIELDS:
            raise HTTPException(409, "修正対象項目が許可リストにありません")
        if (request[field_name] or "") != (request["before_value"] or ""):
            raise HTTPException(409, "現在の顧客データが申請時点から変更されています")
        target_status = "APPROVED" if payload.action == "approve" else "REJECTED"
        audit_action = "approved" if payload.action == "approve" else "rejected"
        if payload.action == "approve":
            db.execute(
                f"UPDATE households SET `{field_name}`=? WHERE id=?",
                (request["requested_value"], request["household_id"]),
            )
        db.execute(
            """UPDATE data_correction_requests SET status=?,decided_by=?,decided_at=?,
               decision_note=?,version=version+1 WHERE id=? AND version=?""",
            (target_status, actor.user_id, now, note or None, request_id, payload.version),
        )
        audit(db, actor.user_id, f"data_correction.{audit_action}", "data_correction", request_id,
              f"household_id={request['household_id']}; field={field_name}; status={target_status}; note={note}")
        create_notification(
            db, request["requested_by"], "DATA_CORRECTION",
            "顧客データ修正依頼を処理しました",
            f"{request['household_code']} の {field_name} 修正依頼: {target_status}",
            "data_correction", request_id, title_zh="客户数据修正已处理",
            message_zh=f"{request['household_code']} 的 {field_name} 修正申请：{target_status}",
        )
    return {"ok": True, "status": target_status, "version": payload.version + 1}


class StageInput(BaseModel):
    to_stage: str


@app.post("/api/households/{household_id}/stage")
def change_stage(household_id: int, payload: StageInput,
                 x_demo_role: CurrentActor = Depends(require_actor)):
    if payload.to_stage not in STAGES:
        raise HTTPException(422, "不明なステージです")
    with connect() as db:
        user = request_user(db, x_demo_role)
        require_household_access(db, x_demo_role, user, household_id)
        current = db.execute("SELECT to_stage FROM stage_events WHERE household_id=? ORDER BY changed_at DESC LIMIT 1",
                             (household_id,)).fetchone()
        if not current:
            raise HTTPException(404, "家庭が見つかりません")
        assert_month_period_open(db, now_jst().date(), "stage_events")
        db.execute(
            """INSERT INTO stage_events(household_id,from_stage,to_stage,changed_by,changed_at)
               VALUES(?,?,?,?,?)""",
            (household_id, current["to_stage"], payload.to_stage, user["id"],
             datetime.now().isoformat(timespec="seconds")),
        )
        audit(db, user["id"], "stage.changed", "household", household_id, payload.to_stage)
        db.commit()
    return {"ok": True}


class ReportInput(BaseModel):
    manual_note: str = ""


class SystemConfigInput(BaseModel):
    value: object
    reason: str


@app.get("/api/system-config")
def get_system_config(x_demo_role: CurrentActor = Depends(require_actor)):
    role_guard(x_demo_role, ("hq_finance",))
    with connect() as db:
        rows = db.execute(
            """SELECT c.config_key,c.value_json,c.updated_at,u.name AS updated_by_name
               FROM system_configs c LEFT JOIN users u ON u.id=c.updated_by ORDER BY c.config_key"""
        )
        return {"items": [
            {
                "key": row["config_key"],
                "value": json.loads(row["value_json"]) if isinstance(row["value_json"], str) else row["value_json"],
                "updated_at": row["updated_at"],
                "updated_by": row["updated_by_name"],
            }
            for row in rows
        ]}


@app.put("/api/system-config/{config_key}")
def update_system_config(config_key: str, payload: SystemConfigInput,
                         x_demo_role: CurrentActor = Depends(require_actor)):
    role_guard(x_demo_role, ("hq_finance",))
    if config_key not in SYSTEM_CONFIG_DEFAULTS:
        raise HTTPException(404, "不明な設定項目です")
    if not valid_config_value(config_key, payload.value):
        raise HTTPException(422, "設定値の形式または範囲が正しくありません")
    reason = payload.reason.strip()
    if not 10 <= len(reason) <= 500:
        raise HTTPException(422, "変更理由は10〜500文字で入力してください")
    with connect() as db:
        user = request_user(db, x_demo_role)
        current = db.execute(
            "SELECT value_json FROM system_configs WHERE config_key=? FOR UPDATE", (config_key,)
        ).fetchone()
        if not current:
            raise HTTPException(404, "設定項目が見つかりません")
        previous_value = current["value_json"]
        if isinstance(previous_value, str):
            previous_value = json.loads(previous_value)
        db.execute(
            "UPDATE system_configs SET value_json=?,updated_at=?,updated_by=? WHERE config_key=?",
            (json.dumps(payload.value, ensure_ascii=False, sort_keys=True),
             datetime.now().isoformat(timespec="seconds"), user["id"], config_key),
        )
        if any(config_key == item[1] for item in SLA_CONFIG):
            sync_sla_settings(db)
        audit(db, user["id"], "system_config.updated", "system_config", None,
              f"key={config_key}; before={json.dumps(previous_value, ensure_ascii=False, sort_keys=True)}; "
              f"after={json.dumps(payload.value, ensure_ascii=False, sort_keys=True)}; reason={reason}")
    return {"ok": True}


@app.put("/api/report")
def save_report(payload: ReportInput, x_demo_role: CurrentActor = Depends(require_actor)):
    with connect() as db:
        user = request_user(db, x_demo_role)
        today = now_jst().date().isoformat()
        count = db.execute("SELECT COUNT(*) FROM activities WHERE user_id=? AND DATE(acted_at)=CURRENT_DATE",
                           (user["id"],)).fetchone()[0]
        summary = f"本日の活動 {count} 件。面談・紹介状況を確認してください。"
        existing = db.execute("SELECT id FROM daily_report_drafts WHERE user_id=? AND report_date=?",
                              (user["id"], today)).fetchone()
        if existing:
            db.execute("UPDATE daily_report_drafts SET auto_summary=?,manual_note=? WHERE id=?",
                       (summary, payload.manual_note, existing["id"]))
        else:
            db.execute("INSERT INTO daily_report_drafts(user_id,report_date,auto_summary,manual_note) VALUES(?,?,?,?)",
                       (user["id"], today, summary, payload.manual_note))
        if user["role"] == "advisor" and user["store_id"]:
            managers = db.execute(
                """SELECT id FROM users WHERE role='store_manager' AND store_id=?
                   AND account_status='ACTIVE' AND id<>?""",
                (user["store_id"], user["id"]),
            ).fetchall()
            for manager in managers:
                create_notification(
                    db, manager["id"], "DAILY_REPORT", "日報草稿が保存されました",
                    f"{user['display_name'] or user['name']} が {today} の日報草稿を保存しました。",
                    "daily_report", user["id"], title_zh="日报草稿已保存",
                    message_zh=f"{user['display_name'] or user['name']} 已保存 {today} 的日报草稿。",
                )
        audit(db, user["id"], "daily_report.saved", "daily_report", user["id"],
              f"report_date={today}")
        db.commit()
    return {"ok": True}


def require_reset_mode():
    if not sample_or_demo_enabled():
        raise HTTPException(403, "デモモードは無効です")


@app.post("/api/reset", dependencies=[Depends(require_reset_mode)])
def reset_demo(request: Request, x_demo_role: CurrentActor = Depends(require_actor)):
    role_guard(x_demo_role, ("hq_finance",))
    guard = request.state.sample_guard
    with connect() as db:
        rental.check_rental_reset_scope(db)
        referral_storage_keys = [
            row["storage_key"] for row in db.execute(
                "SELECT storage_key FROM referral_document_files"
            ).fetchall()
        ]

    # MySQL commits DDL implicitly. Rebuild from scratch on a fresh
    # connection if an earlier attempt failed partway through.
    for attempt in range(2):
        try:
            with connect() as db:
                session_token = request.cookies.get(SESSION_COOKIE)
                if public_sample_mode_enabled():
                    db.execute("DELETE FROM auth_sessions")
                elif session_token:
                    db.execute("DELETE FROM auth_sessions WHERE token_hash<>?", (token_digest(session_token),))
                db.execute("DELETE FROM password_reset_tokens")
                db.execute("DELETE FROM auth_login_attempts")
                db.execute("DELETE FROM password_history")
                db.execute("DELETE FROM notification_deliveries")
                db.execute("DELETE FROM notifications")
                if attempt == 0:
                    audit(db, x_demo_role.user_id, "DEMO_DATA_RESET", "seed", None, f"batch={SEED_BATCH}")
                for table in TABLES:
                    db.execute(f"DROP TABLE IF EXISTS `{table}`")
                for storage_key in referral_storage_keys:
                    if Path(storage_key).name == storage_key:
                        (REFERRAL_STORAGE_DIR / storage_key).unlink(missing_ok=True)
                seed(db)
        except Exception:
            logging.exception("Demo reset attempt %d failed", attempt + 1)
            if attempt == 1:
                guard.reset_failed = True
                raise HTTPException(500, "サンプルデータのリセットに失敗しました")
        else:
            guard.reset_failed = False
            return {"ok": True}


@app.get("/api/notifications")
def notification_list(limit: int = 50, actor: CurrentActor = Depends(require_actor)):
    if not 1 <= limit <= 100:
        raise HTTPException(422, "取得件数は1から100まで指定してください")
    with connect() as db:
        unread_count = db.execute(
            "SELECT COUNT(*) AS count FROM notifications WHERE user_id=? AND status='UNREAD'",
            (actor.user_id,),
        ).fetchone()["count"]
        rows = db.execute(
            """SELECT id,notification_type,system_event_code,title,title_zh,message,message_zh,
                      related_record_type,related_record_id,status,created_at,read_at
               FROM notifications WHERE user_id=? AND status!='ARCHIVED'
               ORDER BY created_at DESC,id DESC LIMIT ?""",
            (actor.user_id, limit),
        ).fetchall()
    return {"unread_count": unread_count, "items": [dict(row) for row in rows]}


@app.put("/api/notifications/{notification_id}/read")
def mark_notification_read(notification_id: str, actor: CurrentActor = Depends(require_actor)):
    with connect() as db:
        row = db.execute(
            "SELECT id,status FROM notifications WHERE id=? AND user_id=? FOR UPDATE",
            (notification_id, actor.user_id),
        ).fetchone()
        if not row:
            raise HTTPException(404, "通知が見つかりません")
        if row["status"] == "UNREAD":
            db.execute(
                "UPDATE notifications SET status='READ',read_at=? WHERE id=? AND user_id=?",
                (now_jst(), notification_id, actor.user_id),
            )
    return {"ok": True}


@app.put("/api/notifications/{notification_id}/archive")
def archive_notification(notification_id: str, actor: CurrentActor = Depends(require_actor)):
    with connect() as db:
        cursor = db.execute(
            "UPDATE notifications SET status='ARCHIVED' WHERE id=? AND user_id=? AND status='READ'",
            (notification_id, actor.user_id),
        )
        if cursor.rowcount == 0:
            exists = db.execute(
                "SELECT id FROM notifications WHERE id=? AND user_id=?",
                (notification_id, actor.user_id),
            ).fetchone()
            if not exists:
                raise HTTPException(404, "通知が見つかりません")
            raise HTTPException(409, "未読通知は既読にしてからアーカイブしてください")
    return {"ok": True}


class ExpenseInput(BaseModel):
    category: str
    amount: int
    description: str
    expense_date: date
    version: Optional[int] = None


class ExpenseDecisionInput(BaseModel):
    version: int
    reason: Optional[str] = None


class ExportJobInput(BaseModel):
    resource: str
    include_personal_data: bool = False
    format: str = "csv"


def csv_cell(value):
    if not isinstance(value, str):
        return value
    if value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def build_csv(headers, rows):
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow([csv_cell(value) for value in headers])
    for row in rows:
        writer.writerow([csv_cell(value) for value in row])
    return ("\ufeff" + output.getvalue()).encode("utf-8")


def household_visibility_clause(actor, alias="h"):
    account_role = getattr(actor, "account_role", "")
    if account_role in ("administrator", "executive", "finance", "hq_staff"):
        return "1=1", []
    if account_role == "store_manager" and actor.store_id:
        return f"{alias}.store_id=?", [actor.store_id]
    if account_role == "advisor":
        return f"{alias}.advisor_id=?", [actor.user_id]
    raise HTTPException(403, "世帯データを閲覧する権限がありません")


def export_rows(db, actor, resource, include_personal_data, limit):
    account_role = getattr(actor, "account_role", "")
    if include_personal_data and account_role not in ("administrator", "executive"):
        raise HTTPException(403, "個人情報を含む出力には管理権限が必要です")
    if resource == "households":
        scope, args = household_visibility_clause(actor)
        rows = db.execute(
            f"""SELECT h.id AS record_id,h.household_code,h.representative_name,s.name AS store_name,
                       u.display_name AS advisor_name,h.area_pref,h.budget_band,h.land_status,
                       h.status,h.created_at
                FROM households h LEFT JOIN stores s ON s.id=h.store_id
                LEFT JOIN users u ON u.id=h.advisor_id
                WHERE {scope} ORDER BY h.id LIMIT ?""",
            (*args, limit),
        ).fetchall()
        headers = ["household_code", "representative_name", "store", "advisor",
                   "area_pref", "budget_band", "land_status", "status", "created_at"]
        record_ids = [row["record_id"] for row in rows]
        data = [[row["household_code"],
                 row["representative_name"] if include_personal_data else row["household_code"],
                 row["store_name"], row["advisor_name"] if include_personal_data else "",
                 row["area_pref"], row["budget_band"], row["land_status"], row["status"],
                 row["created_at"]] for row in rows]
    elif resource == "introductions":
        scope, args = household_visibility_clause(actor)
        rows = db.execute(
            f"""SELECT i.id,h.household_code,p.name AS partner_name,i.status,
                       n.status AS negotiation_status,i.introduced_at,c.contract_date,c.contract_amount
                FROM introductions i JOIN households h ON h.id=i.household_id
                JOIN partners p ON p.id=i.partner_id
                LEFT JOIN negotiations n ON n.introduction_id=i.id
                LEFT JOIN contracts c ON c.negotiation_id=n.id
                WHERE {scope} ORDER BY i.id LIMIT ?""",
            (*args, limit),
        ).fetchall()
        headers = ["introduction_id", "household_code", "partner", "introduction_status",
                   "negotiation_status", "introduced_at", "contract_date", "contract_amount"]
        record_ids = [row["id"] for row in rows]
        data = [[row["id"], row["household_code"], row["partner_name"], row["status"],
                 row["negotiation_status"], row["introduced_at"], row["contract_date"],
                 row["contract_amount"]] for row in rows]
    elif resource == "expenses":
        scope, args = expense_visibility_clause(actor)
        rows = db.execute(
            f"""SELECT e.id,e.applicant_id,u.display_name AS applicant_name,e.store_id,e.category,e.amount,
                       e.tax_amount,e.tax_category,e.expense_date,e.applied_at,e.status,e.reviewed_by,
                       e.reviewed_at,e.rejection_reason,e.receipt_filename,
                       e.accounting_integration_id,e.recorded_reference,e.recorded_confirmed_at,
                       e.created_at
                FROM expenses e JOIN users u ON u.id=e.applicant_id
                WHERE {scope} ORDER BY e.created_at,e.id LIMIT ?""",
            (*args, limit),
        ).fetchall()
        headers = ["expense_id", "applicant_id", "store_id", "category", "description", "expense_date",
                   "applied_at", "amount_including_tax", "consumption_tax_amount", "tax_category",
                   "status", "reviewer_id", "reviewed_at", "rejection_reason", "receipt_attached",
                   "accounting_integration_id", "recorded_reference", "recorded_confirmed_at",
                   "created_at"]
        record_ids = [row["id"] for row in rows]
        data = [[row["id"], row["applicant_id"],
                 row["store_id"], row["category"], row["description"], row["expense_date"],
                 row["applied_at"], row["amount"], row["tax_amount"], row["tax_category"],
                 row["status"], row["reviewed_by"], row["reviewed_at"], row["rejection_reason"],
                 bool(row["receipt_filename"]), row["accounting_integration_id"],
                 row["recorded_reference"], row["recorded_confirmed_at"], row["created_at"]]
                for row in rows]
    elif resource in ("fee_entitlements", "invoice_data"):
        if account_role not in ("finance", "executive", "administrator", "hq_staff"):
            raise HTTPException(403, "報酬・請求データを出力する権限がありません")
        invoice_only = resource == "invoice_data"
        conditions = ["fe.state!='Disputed'"]
        if invoice_only:
            conditions.extend(["fe.invoice_data_generated=1", "fe.state='Invoiced'"])
        rows = db.execute(
            f"""SELECT fe.id,h.household_code,p.name AS partner_name,fe.state,
                       fr.version AS fee_rule_version,fe.base_amount,fe.calculated_amount,
                       fe.invoice_data_generated,fe.calculated_at
                FROM fee_entitlements fe JOIN introductions i ON i.id=fe.introduction_id
                JOIN households h ON h.id=i.household_id JOIN partners p ON p.id=i.partner_id
                JOIN fee_rules fr ON fr.id=fe.fee_rule_id
                WHERE {' AND '.join(conditions)} ORDER BY fe.id LIMIT ?""",
            (limit,),
        ).fetchall()
        headers = ["fee_entitlement_id", "household_code", "partner", "state",
                   "fee_rule_version", "base_amount", "calculated_amount",
                   "invoice_data_generated", "calculated_at"]
        record_ids = [row["id"] for row in rows]
        data = [[row["id"], row["household_code"], row["partner_name"], row["state"],
                 row["fee_rule_version"], row["base_amount"], row["calculated_amount"],
                 row["invoice_data_generated"], row["calculated_at"]] for row in rows]
    else:
        raise HTTPException(422, "出力対象を選択してください")
    return headers, data, record_ids


def expense_visibility_clause(actor):
    account_role = getattr(actor, "account_role", "")
    if account_role in ("administrator", "executive", "finance", "hq_staff"):
        return "1=1", []
    if account_role == "store_manager" and actor.store_id:
        return "e.store_id=?", [actor.store_id]
    if account_role == "advisor":
        return "e.applicant_id=?", [actor.user_id]
    raise HTTPException(403, "経費データを閲覧する権限がありません")


def expense_row(db, actor, expense_id, for_update=False):
    visibility, args = expense_visibility_clause(actor)
    suffix = " FOR UPDATE" if for_update else ""
    row = db.execute(
        f"SELECT e.* FROM expenses e WHERE e.id=? AND {visibility}{suffix}",
        (expense_id, *args),
    ).fetchone()
    if not row:
        raise HTTPException(404, "経費申請が見つかりません")
    return row


def validate_expense_input(db, payload):
    categories = config_value(db, "expense.allowed_categories")
    if payload.category not in categories:
        raise HTTPException(422, "設定された経費区分を選択してください")
    if payload.amount <= 0 or payload.amount > 100000000:
        raise HTTPException(422, "金額は1円から1億円まで指定してください")
    description = payload.description.strip()
    if not description or len(description) > 2000:
        raise HTTPException(422, "内容は1文字以上2000文字以内で入力してください")
    if payload.expense_date > now_jst().date():
        raise HTTPException(422, "未来日付の経費は登録できません")
    return description


def expense_notification(db, user_id, title, message, title_zh, message_zh, expense_id,
                         notification_type="EXPENSE"):
    create_notification(db, user_id, notification_type, title, message, "expense", expense_id,
                        title_zh=title_zh, message_zh=message_zh)


@app.get("/api/expenses")
def expense_list(actor: CurrentActor = Depends(require_actor)):
    visibility, args = expense_visibility_clause(actor)
    with connect() as db:
        allowed_categories = config_value(db, "expense.allowed_categories")
        max_receipt_mb = config_value(db, "expense.max_receipt_mb")
        approval_thresholds = config_value(db, "expense.approval_thresholds_yen")
        rows = db.execute(
            f"""SELECT e.id,e.applicant_id,u.display_name AS applicant_name,e.store_id,e.category,
                       e.amount,e.tax_amount,e.tax_category,e.description,e.expense_date,e.applied_at,
                       e.receipt_filename,e.receipt_size,e.status,e.rejection_reason,e.version,
                       e.reviewed_by,e.reviewed_at,e.finance_recorded_by,e.finance_recorded_at,
                       e.accounting_integration_id,e.recorded_reference,e.recorded_confirmed_at,
                       e.created_at,e.updated_at
                FROM expenses e JOIN users u ON u.id=e.applicant_id
                WHERE {visibility} ORDER BY e.created_at DESC,e.id DESC""",
            args,
        ).fetchall()
    return {"items": [dict(row) for row in rows], "allowed_categories": allowed_categories,
            "max_receipt_mb": max_receipt_mb, "approval_thresholds_yen": approval_thresholds}


@app.post("/api/expenses")
def create_expense(payload: ExpenseInput, actor: CurrentActor = Depends(require_actor)):
    account_role = getattr(actor, "account_role", "")
    if account_role not in ("advisor", "store_manager", "finance", "executive", "administrator"):
        raise HTTPException(403, "経費申請を作成する権限がありません")
    now = now_jst()
    expense_id = str(uuid.uuid4())
    with connect() as db:
        description = validate_expense_input(db, payload)
        assert_month_period_open(db, payload.expense_date, "expenses")
        db.execute(
            """INSERT INTO expenses(id,applicant_id,store_id,category,amount,description,expense_date,
               status,version,created_at,updated_at) VALUES(?,?,?,?,?,?,?,'DRAFT',1,?,?)""",
            (expense_id, actor.user_id, actor.store_id, payload.category, payload.amount,
             description, payload.expense_date, now, now),
        )
        audit(db, actor.user_id, "expense.created", "expense", expense_id,
              f"category={payload.category}; amount={payload.amount}")
    return {"ok": True, "id": expense_id, "status": "DRAFT", "version": 1}


@app.put("/api/expenses/{expense_id}")
def update_expense(expense_id: str, payload: ExpenseInput,
                   actor: CurrentActor = Depends(require_actor)):
    now = now_jst()
    with connect() as db:
        row = expense_row(db, actor, expense_id, for_update=True)
        if row["applicant_id"] != actor.user_id or row["status"] not in ("DRAFT", "REJECTED"):
            raise HTTPException(403, "この経費申請は編集できません")
        if payload.version != row["version"]:
            raise HTTPException(409, "経費申請が更新されています。再読み込みしてください")
        assert_month_period_open(db, row["expense_date"], "expenses")
        assert_month_period_open(db, payload.expense_date, "expenses")
        description = validate_expense_input(db, payload)
        db.execute(
            """UPDATE expenses SET category=?,amount=?,description=?,expense_date=?,
               status='DRAFT',rejection_reason=NULL,reviewed_by=NULL,reviewed_at=NULL,
               version=version+1,updated_at=? WHERE id=? AND version=?""",
            (payload.category, payload.amount, description, payload.expense_date,
             now, expense_id, payload.version),
        )
        audit(db, actor.user_id, "expense.updated", "expense", expense_id,
              f"category={payload.category}; amount={payload.amount}; version={payload.version + 1}")
    return {"ok": True, "status": "DRAFT", "version": payload.version + 1}


@app.post("/api/expenses/{expense_id}/receipt")
async def upload_expense_receipt(expense_id: str, version: int = Form(...),
                                 receipt: UploadFile = File(...),
                                 actor: CurrentActor = Depends(require_actor)):
    with connect() as db:
        row = expense_row(db, actor, expense_id, for_update=True)
        if row["applicant_id"] != actor.user_id or row["status"] not in ("DRAFT", "REJECTED"):
            raise HTTPException(403, "この経費申請には証憑を追加できません")
        assert_month_period_open(db, row["expense_date"], "expenses")
        if version != row["version"]:
            raise HTTPException(409, "経費申請が更新されています。再読み込みしてください")
        max_bytes = config_value(db, "expense.max_receipt_mb") * 1024 * 1024
        allowed = set(config_value(db, "attachment.allowed_extensions")) & {"pdf", "jpg", "jpeg", "png"}
    filename = Path(receipt.filename or "").name
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in allowed:
        raise HTTPException(422, "証憑はPDFまたは画像ファイルを指定してください")
    content = await receipt.read(max_bytes + 1)
    if not content or len(content) > max_bytes:
        raise HTTPException(413, "証憑ファイルが空か、設定されたサイズ上限を超えています")
    signatures = {
        "pdf": (content.startswith(b"%PDF-"), "application/pdf"),
        "jpg": (content.startswith(b"\xff\xd8\xff"), "image/jpeg"),
        "jpeg": (content.startswith(b"\xff\xd8\xff"), "image/jpeg"),
        "png": (content.startswith(b"\x89PNG\r\n\x1a\n"), "image/png"),
    }
    valid, mime = signatures[extension]
    if not valid:
        raise HTTPException(422, "ファイル内容が拡張子と一致しません")
    safe_filename = f"receipt_{expense_id}.{extension}"
    now = now_jst()
    with connect() as db:
        row = expense_row(db, actor, expense_id, for_update=True)
        if row["version"] != version or row["applicant_id"] != actor.user_id:
            raise HTTPException(409, "経費申請が更新されています。再読み込みしてください")
        db.execute(
            """UPDATE expenses SET receipt_filename=?,receipt_mime=?,receipt_size=?,receipt_sha256=?,
               receipt_blob=?,version=version+1,updated_at=? WHERE id=? AND version=?""",
            (safe_filename, mime, len(content), hashlib.sha256(content).hexdigest(),
             content, now, expense_id, version),
        )
        audit(db, actor.user_id, "expense.receipt_uploaded", "expense", expense_id,
              f"size={len(content)}; sha256={hashlib.sha256(content).hexdigest()}")
    return {"ok": True, "version": version + 1, "receipt_size": len(content)}


@app.get("/api/expenses/{expense_id}/receipt")
def download_expense_receipt(expense_id: str, actor: CurrentActor = Depends(require_actor)):
    with connect() as db:
        row = expense_row(db, actor, expense_id)
        if not row["receipt_blob"]:
            raise HTTPException(404, "証憑が登録されていません")
    return Response(
        content=row["receipt_blob"], media_type=row["receipt_mime"],
        headers={"Content-Disposition": f'attachment; filename="{row["receipt_filename"]}"',
                 "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )


@app.post("/api/expenses/{expense_id}/submit")
def submit_expense(expense_id: str, payload: ExpenseDecisionInput,
                   actor: CurrentActor = Depends(require_actor)):
    now = now_jst()
    with connect() as db:
        row = expense_row(db, actor, expense_id, for_update=True)
        if row["applicant_id"] != actor.user_id or row["status"] not in ("DRAFT", "REJECTED"):
            raise HTTPException(403, "この経費申請は提出できません")
        if row["version"] != payload.version:
            raise HTTPException(409, "経費申請が更新されています。再読み込みしてください")
        if not row["receipt_blob"]:
            raise HTTPException(422, "提出前に証憑を添付してください")
        assert_month_period_open(db, row["expense_date"], "expenses")
        db.execute(
            """UPDATE expenses SET status='SUBMITTED',rejection_reason=NULL,version=version+1,
               updated_at=? WHERE id=? AND version=?""",
            (now, expense_id, payload.version),
        )
        thresholds = config_value(db, "expense.approval_thresholds_yen")
        approver_role = ("store_manager" if row["amount"] <= thresholds[0] else
                         "finance" if row["amount"] <= thresholds[1] else "executive")
        if approver_role == "store_manager":
            approvers = db.execute(
                "SELECT id FROM users WHERE role='store_manager' AND store_id<=>? AND account_status='ACTIVE'",
                (row["store_id"],),
            ).fetchall()
            if not approvers:
                approvers = db.execute(
                    "SELECT id FROM users WHERE role IN ('finance','executive') AND account_status='ACTIVE'"
                ).fetchall()
        elif approver_role == "finance":
            approvers = db.execute(
                "SELECT id FROM users WHERE role IN ('finance','executive') AND account_status='ACTIVE'"
            ).fetchall()
        else:
            approvers = db.execute(
                "SELECT id FROM users WHERE role IN ('executive','administrator') AND account_status='ACTIVE'"
            ).fetchall()
        for approver in approvers:
            expense_notification(db, approver["id"], "経費申請の承認待ち",
                                 f"経費申請 {expense_id} の確認が必要です。",
                                 "费用申请待审批", f"请审核费用申请 {expense_id}。",
                                 expense_id, "APPROVAL")
        audit(db, actor.user_id, "expense.submitted", "expense", expense_id,
              f"amount={row['amount']}; version={payload.version + 1}")
    return {"ok": True, "status": "SUBMITTED", "version": payload.version + 1}


def decide_expense(expense_id, payload, actor, approve):
    account_role = getattr(actor, "account_role", "")
    if account_role not in ("finance", "executive", "administrator", "store_manager"):
        raise HTTPException(403, "経費承認の権限がありません")
    now = now_jst()
    with connect() as db:
        row = expense_row(db, actor, expense_id, for_update=True)
        if row["status"] != "SUBMITTED":
            raise HTTPException(409, "提出済みの経費申請ではありません")
        assert_month_period_open(db, row["expense_date"], "expenses")
        if row["applicant_id"] == actor.user_id:
            raise HTTPException(403, "自分の経費申請は承認できません")
        if row["version"] != payload.version:
            raise HTTPException(409, "経費申請が更新されています。再読み込みしてください")
        thresholds = config_value(db, "expense.approval_thresholds_yen")
        if row["amount"] > thresholds[1] and account_role not in ("executive", "administrator"):
            raise HTTPException(403, "この金額の承認には社長または管理者の承認が必要です")
        if row["amount"] > thresholds[0] and account_role not in (
                "finance", "executive", "administrator"):
            raise HTTPException(403, "この金額の承認には本社・経理の承認が必要です")
        if account_role == "store_manager" and actor.store_id != row["store_id"]:
            raise HTTPException(403, "他店舗の経費は承認できません")
        reason = (payload.reason or "").strip()
        if not approve and not reason:
            raise HTTPException(422, "差戻し理由を入力してください")
        status = "APPROVED" if approve else "REJECTED"
        db.execute(
            """UPDATE expenses SET status=?,rejection_reason=?,reviewed_by=?,reviewed_at=?,
               version=version+1,updated_at=? WHERE id=? AND version=?""",
            (status, None if approve else reason, actor.user_id, now, now, expense_id, payload.version),
        )
        if approve:
            title_ja, message_ja = "経費申請が承認されました", f"経費申請 {expense_id} が承認されました。"
            title_zh, message_zh = "费用申请已批准", f"费用申请 {expense_id} 已批准。"
            action = "expense.approved"
        else:
            title_ja, message_ja = "経費申請が差し戻されました", f"差戻し理由: {reason}"
            title_zh, message_zh = "费用申请已退回", f"退回原因：{reason}"
            action = "expense.rejected"
        expense_notification(db, row["applicant_id"], title_ja, message_ja,
                             title_zh, message_zh, expense_id)
        audit(db, actor.user_id, action, "expense", expense_id,
              f"status={status}; version={payload.version + 1}; reason={reason}")
    return {"ok": True, "status": status, "version": payload.version + 1}


@app.post("/api/expenses/{expense_id}/approve")
def approve_expense(expense_id: str, payload: ExpenseDecisionInput,
                    actor: CurrentActor = Depends(require_actor)):
    return decide_expense(expense_id, payload, actor, True)


@app.post("/api/expenses/{expense_id}/reject")
def reject_expense(expense_id: str, payload: ExpenseDecisionInput,
                   actor: CurrentActor = Depends(require_actor)):
    return decide_expense(expense_id, payload, actor, False)


@app.post("/api/expenses/{expense_id}/record")
def record_expense(expense_id: str, payload: ExpenseDecisionInput,
                   actor: CurrentActor = Depends(require_actor)):
    if getattr(actor, "account_role", "") not in ("finance", "executive", "administrator"):
        raise HTTPException(403, "経理記録の権限がありません")
    now = now_jst()
    with connect() as db:
        row = expense_row(db, actor, expense_id, for_update=True)
        if row["status"] != "APPROVED":
            raise HTTPException(409, "承認済みの経費申請ではありません")
        assert_month_period_open(db, row["expense_date"], "expenses")
        if row["version"] != payload.version:
            raise HTTPException(409, "経費申請が更新されています。再読み込みしてください")
        db.execute(
            """UPDATE expenses SET status='RECORDED',finance_recorded_by=?,finance_recorded_at=?,
               version=version+1,updated_at=? WHERE id=? AND version=?""",
            (actor.user_id, now, now, expense_id, payload.version),
        )
        audit(db, actor.user_id, "expense.recorded", "expense", expense_id,
              f"version={payload.version + 1}")
    return {"ok": True, "status": "RECORDED", "version": payload.version + 1}


@app.post("/api/export-jobs")
def create_export_job(payload: ExportJobInput, actor: CurrentActor = Depends(require_actor)):
    if payload.format not in ("csv", "pdf"):
        raise HTTPException(422, "CSVまたはPDFを指定してください")
    now = now_jst()
    job_id = str(uuid.uuid4())
    with connect() as db:
        max_rows = config_value(db, "export.max_rows")
        max_bytes = config_value(db, "export.max_pdf_mb" if payload.format == "pdf"
                                 else "export.max_csv_mb") * 1024 * 1024
        expiry_hours = config_value(db, "export.expiry_hours")
        db.execute(
            "UPDATE export_jobs SET status='EXPIRED',content='' WHERE status='READY' AND expires_at<=?",
            (now,),
        )
        headers, rows, record_ids = export_rows(
            db, actor, payload.resource, payload.include_personal_data, max_rows + 1
        )
        if len(rows) > max_rows:
            raise HTTPException(413, "出力件数が設定上限を超えています。条件を絞ってください")
        actor_row = db.execute(
            "SELECT COALESCE(display_name,name) AS display_name FROM users WHERE id=?",
            (actor.user_id,),
        ).fetchone()
        template_version = PDF_TEMPLATE_VERSION if payload.format == "pdf" else "csv-v1"
        if payload.format == "pdf":
            try:
                content = build_pdf_isolated(
                    headers, rows, payload.resource, now.isoformat(timespec="seconds"),
                    actor_row["display_name"] if actor_row else str(actor.user_id),
                    config_value(db, "pdf.render_timeout_seconds"),
                    config_value(db, "pdf.render_concurrency"),
                    config_value(db, "pdf.render_max_pending"),
                )
            except RuntimeError as error:
                LOGGER.warning("PDF export was rejected or failed: %s", error)
                if str(error) == "PDF_RENDER_QUEUE_FULL":
                    raise HTTPException(503, "PDF出力が混雑しています。時間をおいて再度お試しください") from error
                raise HTTPException(500, "PDFの生成に失敗しました") from error
            except TimeoutError as error:
                LOGGER.warning("PDF export timed out.")
                raise HTTPException(504, "PDFの生成がタイムアウトしました") from error
        else:
            content = build_csv(headers, rows)
        if len(content) > max_bytes:
            raise HTTPException(413, "出力ファイルが設定サイズ上限を超えています")
        filename = f"sumaiboard_{payload.resource}_{now:%Y%m%d%H%M%S}.{payload.format}"
        expires_at = now + timedelta(hours=expiry_hours)
        content_hash = hashlib.sha256(content).hexdigest()
        db.execute(
            """INSERT INTO export_jobs(id,user_id,resource,format,template_version,created_role,
               scope_store_id,include_personal_data,record_ids_json,filename,row_count,content_sha256,
               content,status,created_at,expires_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,'READY',?,?)""",
            (job_id, actor.user_id, payload.resource, payload.format, template_version,
             actor.account_role, actor.store_id, payload.include_personal_data,
             json.dumps(record_ids, ensure_ascii=False), filename, len(rows), content_hash,
             content, now, expires_at),
        )
        audit(db, actor.user_id, "export.created", "export_job", job_id,
              f"resource={payload.resource}; format={payload.format}; template={template_version}; "
              f"rows={len(rows)}; sha256={content_hash}")
        create_notification(
            db, actor.user_id, "EXPORT", f"{payload.format.upper()}出力を作成しました",
            f"{filename}（{len(rows)} 件）は {expires_at:%Y-%m-%d %H:%M} までダウンロードできます。",
            "export_job", job_id, title_zh=f"{payload.format.upper()} 导出已生成",
            message_zh=f"{filename}（{len(rows)} 条）可下载至 {expires_at:%Y-%m-%d %H:%M}。",
        )
    return {"id": job_id, "resource": payload.resource, "format": payload.format,
            "template_version": template_version, "filename": filename,
            "row_count": len(rows), "sha256": content_hash,
            "expires_at": expires_at.isoformat(timespec="seconds")}


@app.get("/api/export-jobs")
def export_job_list(actor: CurrentActor = Depends(require_actor)):
    with connect() as db:
        rows = db.execute(
            """SELECT id,resource,format,template_version,filename,row_count,content_sha256,
                      status,created_at,expires_at
               FROM export_jobs WHERE user_id=? ORDER BY created_at DESC LIMIT 100""",
            (actor.user_id,),
        ).fetchall()
    return {"items": [dict(row) for row in rows]}


@app.get("/api/export-jobs/{job_id}/download")
def download_export_job(job_id: str, actor: CurrentActor = Depends(require_actor)):
    expired = False
    corrupt = False
    with connect() as db:
        row = db.execute(
            """SELECT resource,format,template_version,created_role,scope_store_id,
                      include_personal_data,record_ids_json,filename,content,content_sha256,status,expires_at
               FROM export_jobs WHERE id=? AND user_id=? FOR UPDATE""",
            (job_id, actor.user_id),
        ).fetchone()
        if not row:
            raise HTTPException(404, "出力ファイルが見つかりません")
        if row["status"] != "READY" or row["expires_at"] <= now_jst():
            db.execute("UPDATE export_jobs SET status='EXPIRED',content='' WHERE id=?", (job_id,))
            expired = True
        else:
            if (row["created_role"] and
                    (row["created_role"] != actor.account_role or row["scope_store_id"] != actor.store_id)):
                raise HTTPException(403, "現在の権限範囲では出力ファイルをダウンロードできません")
            try:
                headers, current_rows, current_record_ids = export_rows(
                    db, actor, row["resource"], bool(row["include_personal_data"]),
                    config_value(db, "export.max_rows") + 1,
                )
            except HTTPException as error:
                if error.status_code == 403:
                    raise HTTPException(403, "現在の権限範囲では出力ファイルをダウンロードできません") from error
                raise
            current_ids = {str(item) for item in current_record_ids}
            original_ids = {str(item) for item in json.loads(row["record_ids_json"] or "[]")}
            if not original_ids.issubset(current_ids):
                raise HTTPException(403, "出力対象の閲覧権限が変更されたためダウンロードできません")
            content = bytes(row["content"])
            actual_hash = hashlib.sha256(content).hexdigest()
            if not hmac.compare_digest(actual_hash, row["content_sha256"]):
                db.execute("UPDATE export_jobs SET status='CORRUPT' WHERE id=?", (job_id,))
                audit(db, actor.user_id, "export.integrity_failed", "export_job", job_id,
                      f"resource={row['resource']}; expected_sha256={row['content_sha256']}; "
                      f"actual_sha256={actual_hash}")
                admins = db.execute(
                    """SELECT id FROM users WHERE role IN ('administrator','executive')
                       AND account_status='ACTIVE'"""
                ).fetchall()
                for admin in admins:
                    create_notification(
                        db, admin["id"], "SECURITY", "出力ファイルの整合性異常",
                        f"出力ジョブ {job_id} のハッシュ検証に失敗しました。",
                        "export_job", job_id, title_zh="导出文件完整性异常",
                        message_zh=f"导出任务 {job_id} 的哈希校验失败。",
                    )
                corrupt = True
            else:
                filename = row["filename"]
                db.execute("UPDATE export_jobs SET downloaded_at=? WHERE id=?",
                           (now_jst(), job_id))
                audit(db, actor.user_id, f"export.downloaded.{row['format']}",
                      "export_job", job_id,
                      f"resource={row['resource']}; template={row['template_version']}; "
                      f"sha256={actual_hash}")
    if expired:
        raise HTTPException(410, "出力ファイルの有効期限が切れています")
    if corrupt:
        raise HTTPException(409, "出力ファイルの整合性を確認できないためダウンロードできません")
    return Response(
        content=content,
        media_type="application/pdf" if filename.endswith(".pdf") else "text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
                 "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


class MonthClosePrepareInput(BaseModel):
    period: str


class MonthCloseVersionInput(BaseModel):
    version: int


class MonthCloseReopenInput(BaseModel):
    version: int
    reason: str


def require_month_close_access(actor, roles):
    if getattr(actor, "account_role", "") not in roles:
        raise HTTPException(403, "月次締めを操作する権限がありません")


def month_close_summary(row):
    return {
        "id": row["id"], "period": row["period"], "snapshot_version": row["snapshot_version"],
        "status": row["status"], "snapshot_sha256": row["snapshot_sha256"],
        "prepared_by": row["prepared_by"], "prepared_at": row["prepared_at"],
        "closed_by": row["closed_by"], "closed_at": row["closed_at"],
        "reopen_requested_by": row["reopen_requested_by"],
        "reopen_reason": row["reopen_reason"], "reopen_requested_at": row["reopen_requested_at"],
        "reopen_approved_by": row["reopen_approved_by"], "reopened_at": row["reopened_at"],
        "version": row["version"],
    }


@app.get("/api/month-closes")
def month_close_list(period: Optional[str] = None, actor: CurrentActor = Depends(require_actor)):
    require_month_close_access(actor, ("finance", "executive", "administrator", "hq_staff"))
    if period and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", period):
        raise HTTPException(422, "対象月はYYYY-MM形式で指定してください")
    with connect() as db:
        if period:
            rows = db.execute(
                """SELECT id,period,snapshot_version,status,snapshot_sha256,prepared_by,prepared_at,
                   closed_by,closed_at,reopen_requested_by,reopen_reason,reopen_requested_at,
                   reopen_approved_by,reopened_at,version FROM month_closes
                   WHERE period=? ORDER BY snapshot_version DESC""", (period,),
            ).fetchall()
        else:
            rows = db.execute(
                """SELECT id,period,snapshot_version,status,snapshot_sha256,prepared_by,prepared_at,
                   closed_by,closed_at,reopen_requested_by,reopen_reason,reopen_requested_at,
                   reopen_approved_by,reopened_at,version FROM month_closes
                   ORDER BY period DESC,snapshot_version DESC LIMIT 100"""
            ).fetchall()
    return {"items": [month_close_summary(row) for row in rows]}


@app.get("/api/month-closes/{close_id}/detail")
def month_close_detail(close_id: str, actor: CurrentActor = Depends(require_actor)):
    require_month_close_access(actor, ("finance", "executive", "administrator", "hq_staff"))
    with connect() as db:
        row = db.execute("SELECT * FROM month_closes WHERE id=?", (close_id,)).fetchone()
        if not row:
            raise HTTPException(404, "月次締めスナップショットが見つかりません")
    result = month_close_summary(row)
    snapshot = row["snapshot_json"]
    result["snapshot"] = json.loads(snapshot) if isinstance(snapshot, str) else snapshot
    return result


@app.get("/api/month-closes/lock-matrix")
def month_close_lock_matrix(period: str, actor: CurrentActor = Depends(require_actor)):
    require_month_close_access(actor, ("finance", "executive", "administrator", "hq_staff"))
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", period):
        raise HTTPException(422, "対象月はYYYY-MM形式で指定してください")
    with connect() as db:
        resources = config_value(db, "month_close.locked_resources")
        close = db.execute(
            """SELECT id,snapshot_version,status FROM month_closes WHERE period=?
               AND status IN ('CLOSED','REOPEN_REQUESTED') ORDER BY snapshot_version DESC LIMIT 1""",
            (period,),
        ).fetchone()
    return {
        "period": period, "locked_by_close_id": close["id"] if close else None,
        "snapshot_version": close["snapshot_version"] if close else None,
        "items": [{"resource": resource, "locked": bool(close)} for resource in resources],
    }


@app.post("/api/month-closes/prepare")
def prepare_month_close(payload: MonthClosePrepareInput, actor: CurrentActor = Depends(require_actor)):
    require_month_close_access(actor, ("finance", "administrator", "hq_staff"))
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", payload.period):
        raise HTTPException(422, "対象月はYYYY-MM形式で指定してください")
    now = now_jst()
    close_id = str(uuid.uuid4())
    with connect() as db:
        db.execute("INSERT IGNORE INTO month_close_period_locks(period) VALUES(?)", (payload.period,))
        db.execute("SELECT period FROM month_close_period_locks WHERE period=? FOR UPDATE", (payload.period,))
        previous = db.execute(
            """SELECT snapshot_version,status FROM month_closes WHERE period=?
               ORDER BY snapshot_version DESC LIMIT 1 FOR UPDATE""", (payload.period,),
        ).fetchone()
        if previous and previous["status"] != "REOPENED":
            raise HTTPException(409, "前回の月次締めが完了していないか、再オープンされていません")
        snapshot_version = previous["snapshot_version"] + 1 if previous else 1
        snapshot = build_month_snapshot(db, payload.period)
        snapshot_json = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest()
        db.execute(
            """INSERT INTO month_closes(id,period,snapshot_version,status,snapshot_json,snapshot_sha256,
               prepared_by,prepared_at,version) VALUES(?,?,?,'PREPARED',?,?,?,?,1)""",
            (close_id, payload.period, snapshot_version, snapshot_json, digest, actor.user_id, now),
        )
        audit(db, actor.user_id, "month_close.prepared", "month_close", close_id,
              f"period={payload.period}; version={snapshot_version}; sha256={digest}")
        approvers = db.execute(
            """SELECT id FROM users WHERE role IN ('executive','administrator') AND account_status='ACTIVE'"""
        ).fetchall()
        for approver in approvers:
            create_notification(
                db, approver["id"], "MONTHLY_CLOSE", "月次締めの確認待ち",
                f"{payload.period} のスナップショットを確認して締めてください。",
                "month_close", close_id, title_zh="月度结账待确认",
                message_zh=f"{payload.period} 的快照已准备，请审核并完成结账。",
            )
    return {"id": close_id, "period": payload.period, "snapshot_version": snapshot_version,
            "status": "PREPARED", "snapshot_sha256": digest, "snapshot": snapshot}


@app.post("/api/month-closes/{close_id}/close")
def close_month(close_id: str, payload: MonthCloseVersionInput,
                actor: CurrentActor = Depends(require_actor)):
    require_month_close_access(actor, ("executive", "administrator"))
    now = now_jst()
    with connect() as db:
        row = db.execute("SELECT * FROM month_closes WHERE id=? FOR UPDATE", (close_id,)).fetchone()
        if not row:
            raise HTTPException(404, "月次締めスナップショットが見つかりません")
        if row["status"] != "PREPARED":
            raise HTTPException(409, "準備済みの月次締めではありません")
        if row["version"] != payload.version:
            raise HTTPException(409, "月次締めが更新されています。再読み込みしてください")
        if row["prepared_by"] == actor.user_id:
            raise HTTPException(403, "準備者とは別の承認者が締め処理を行ってください")
        db.execute(
            """UPDATE month_closes SET status='CLOSED',closed_by=?,closed_at=?,version=version+1
               WHERE id=? AND version=?""", (actor.user_id, now, close_id, payload.version),
        )
        audit(db, actor.user_id, "month_close.closed", "month_close", close_id,
              f"period={row['period']}; snapshot_version={row['snapshot_version']}")
        create_notification(
            db, row["prepared_by"], "MONTHLY_CLOSE", "月次締めが完了しました",
            f"{row['period']} の月次締めが完了しました。対象レコードの編集はロックされています。",
            "month_close", close_id, title_zh="月度结账已完成",
            message_zh=f"{row['period']} 已完成月度结账，相关记录已锁定。",
        )
    return {"ok": True, "status": "CLOSED", "version": payload.version + 1}


@app.post("/api/month-closes/{close_id}/request-reopen")
def request_month_reopen(close_id: str, payload: MonthCloseReopenInput,
                         actor: CurrentActor = Depends(require_actor)):
    require_month_close_access(actor, ("finance", "administrator", "hq_staff"))
    reason = payload.reason.strip()
    if len(reason) < 10 or len(reason) > 1000:
        raise HTTPException(422, "再オープン理由は10〜1000文字で入力してください")
    now = now_jst()
    with connect() as db:
        row = db.execute("SELECT * FROM month_closes WHERE id=? FOR UPDATE", (close_id,)).fetchone()
        if not row:
            raise HTTPException(404, "月次締めスナップショットが見つかりません")
        if row["status"] != "CLOSED":
            raise HTTPException(409, "締め済みの月次データのみ再オープンを申請できます")
        if row["version"] != payload.version:
            raise HTTPException(409, "月次締めが更新されています。再読み込みしてください")
        db.execute(
            """UPDATE month_closes SET status='REOPEN_REQUESTED',reopen_requested_by=?,
               reopen_reason=?,reopen_requested_at=?,version=version+1 WHERE id=? AND version=?""",
            (actor.user_id, reason, now, close_id, payload.version),
        )
        audit(db, actor.user_id, "month_close.reopen_requested", "month_close", close_id,
              f"period={row['period']}; reason={reason}")
        approvers = db.execute(
            """SELECT id FROM users WHERE role IN ('executive','administrator') AND account_status='ACTIVE'"""
        ).fetchall()
        for approver in approvers:
            create_notification(
                db, approver["id"], "MONTHLY_CLOSE", "月次締め再オープンの承認待ち",
                f"{row['period']} の再オープン申請を確認してください。",
                "month_close", close_id, title_zh="月度结账重新开放待审批",
                message_zh=f"请审核 {row['period']} 的重新开放申请。",
            )
    return {"ok": True, "status": "REOPEN_REQUESTED", "version": payload.version + 1}


@app.post("/api/month-closes/{close_id}/approve-reopen")
def approve_month_reopen(close_id: str, payload: MonthCloseVersionInput,
                         actor: CurrentActor = Depends(require_actor)):
    require_month_close_access(actor, ("executive", "administrator"))
    now = now_jst()
    with connect() as db:
        row = db.execute("SELECT * FROM month_closes WHERE id=? FOR UPDATE", (close_id,)).fetchone()
        if not row:
            raise HTTPException(404, "月次締めスナップショットが見つかりません")
        if row["status"] != "REOPEN_REQUESTED":
            raise HTTPException(409, "再オープン申請がありません")
        if row["version"] != payload.version:
            raise HTTPException(409, "月次締めが更新されています。再読み込みしてください")
        if row["reopen_requested_by"] == actor.user_id:
            raise HTTPException(403, "申請者とは別の承認者が再オープンを承認してください")
        db.execute(
            """UPDATE month_closes SET status='REOPENED',reopen_approved_by=?,reopened_at=?,
               version=version+1 WHERE id=? AND version=?""",
            (actor.user_id, now, close_id, payload.version),
        )
        audit(db, actor.user_id, "month_close.reopened", "month_close", close_id,
              f"period={row['period']}; snapshot_version={row['snapshot_version']}")
        create_notification(
            db, row["reopen_requested_by"], "MONTHLY_CLOSE", "月次締めを再オープンしました",
            f"{row['period']} の再オープンが承認されました。変更履歴は監査ログに記録されます。",
            "month_close", close_id, title_zh="月度结账已重新开放",
            message_zh=f"{row['period']} 的重新开放已批准，修改将记录在审计日志中。",
        )
    return {"ok": True, "status": "REOPENED", "version": payload.version + 1}


KINTONE_IMPORT_FIELDS = (
    "external_id", "representative_name", "store_id",
    "advisor_employee_code", "budget_band", "area_pref", "kana",
)
KINTONE_IMPORT_REQUIRED = ("external_id", "representative_name", "store_id")
KINTONE_IMPORT_ALIASES = {
    "kana": ("kana", "フリガナ", "ふりがな", "カナ"),
    "external_id": ("external_id", "record_id", "レコード番号", "顧客番号"),
    "representative_name": ("representative_name", "代表者名", "顧客名", "氏名"),
    "store_id": ("store_id", "店舗ID", "store"),
    "advisor_employee_code": ("advisor_employee_code", "担当者社員番号", "顧問社員番号"),
    "budget_band": ("budget_band", "予算帯", "予算"),
    "area_pref": ("area_pref", "希望エリア", "希望地域"),
}


def parse_kintone_csv(content, max_rows):
    try:
        text = content.decode("utf-8-sig")
        records = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    except UnicodeDecodeError as error:
        raise HTTPException(422, "CSVはUTF-8形式で保存してください") from error
    except csv.Error as error:
        raise HTTPException(422, "CSV形式を確認してください") from error
    if not records:
        raise HTTPException(422, "CSVにヘッダー行がありません")
    headers = [header.strip() for header in records[0]]
    if not headers or any(not header for header in headers) or len(headers) != len(set(headers)):
        raise HTTPException(422, "CSVのヘッダーが空欄または重複しています")
    rows = []
    for row_number, values in enumerate(records[1:], start=2):
        if not any(value.strip() for value in values):
            continue
        if len(values) != len(headers):
            raise HTTPException(422, f"{row_number} 行目の列数がヘッダーと一致しません")
        rows.append({"source_row_number": row_number, "values": dict(zip(headers, values))})
    if len(rows) > max_rows:
        raise HTTPException(413, "CSV行数が設定上限を超えています")
    return headers, rows


def resolve_kintone_mapping(headers, mapping_json):
    try:
        supplied = json.loads(mapping_json or "{}")
    except (TypeError, ValueError) as error:
        raise HTTPException(422, "フィールドマッピングのJSON形式が正しくありません") from error
    if not isinstance(supplied, dict) or set(supplied) - set(KINTONE_IMPORT_FIELDS):
        raise HTTPException(422, "未対応のフィールドがマッピングされています")
    mapping = {}
    if supplied:
        for field, column in supplied.items():
            if column in (None, ""):
                continue
            if not isinstance(column, str) or column not in headers:
                raise HTTPException(422, f"{field} のCSV列が見つかりません")
            mapping[field] = column
    else:
        normalized = {header.casefold(): header for header in headers}
        for field, aliases in KINTONE_IMPORT_ALIASES.items():
            column = next((normalized[item.casefold()] for item in aliases
                           if item.casefold() in normalized), None)
            if column:
                mapping[field] = column
    if len(set(mapping.values())) != len(mapping):
        raise HTTPException(422, "同じCSV列を複数の項目に割り当てることはできません")
    return mapping


def mapped_value(row, mapping, field):
    column = mapping.get(field)
    return (row.get(column) or "").strip() if column else ""


def analyze_kintone_rows(db, rows, mapping):
    store_ids = {row["id"] for row in db.execute("SELECT id FROM stores").fetchall()}
    advisors = {
        (row["employee_code"], row["store_id"]): row["id"]
        for row in db.execute(
            """SELECT id,employee_code,store_id FROM users WHERE role='advisor'
               AND account_status='ACTIVE' AND employee_code IS NOT NULL"""
        ).fetchall()
    }
    external_ids = list(dict.fromkeys(
        mapped_value(item["values"], mapping, "external_id")
        for item in rows if mapped_value(item["values"], mapping, "external_id")
    ))
    existing = {}
    for start in range(0, len(external_ids), 500):
        batch = external_ids[start:start + 500]
        placeholders = ",".join("?" for _ in batch)
        existing.update({
            row["external_id"]: row["local_id"]
            for row in db.execute(
                f"""SELECT external_id,local_id FROM external_record_mappings
                    WHERE source_system='kintone' AND external_id IN ({placeholders})""",
                batch,
            ).fetchall()
        })
    seen = set()
    result = []
    for item in rows:
        row, row_number = item["values"], item["source_row_number"]
        external_id = mapped_value(row, mapping, "external_id")
        name = mapped_value(row, mapping, "representative_name")
        reason = None
        store_id = None
        advisor_id = None
        if any(field not in mapping for field in KINTONE_IMPORT_REQUIRED):
            reason = "必須項目 external_id、representative_name、store_id をCSV列へ割り当ててください"
        elif not external_id or len(external_id) > 160:
            reason = "external_id は1〜160文字で指定してください"
        elif not name or len(name) > 120:
            reason = "代表者名は1〜120文字で指定してください"
        else:
            try:
                store_id = int(mapped_value(row, mapping, "store_id"))
                if store_id not in store_ids:
                    reason = "店舗が見つかりません"
            except (TypeError, ValueError):
                reason = "store_id は数値で指定してください"
        advisor_code = mapped_value(row, mapping, "advisor_employee_code")
        if not reason and advisor_code:
            advisor_id = advisors.get((advisor_code, store_id))
            if not advisor_id:
                reason = "担当顧問が店舗と一致しないか、有効なアカウントではありません"
        budget = mapped_value(row, mapping, "budget_band")
        area = mapped_value(row, mapping, "area_pref")
        kana = normalize_kana(mapped_value(row, mapping, "kana"))
        if not reason and (len(budget) > 120 or len(area) > 255):
            reason = "予算帯または希望エリアが文字数上限を超えています"
        local_id = existing.get(external_id)
        status = "READY"
        if not reason and (local_id or external_id in seen):
            status, reason = "SKIPPED", (
                "同じCSV内に同一external_idがあります" if external_id in seen
                else "既に取り込み済みです"
            )
        elif reason:
            status = "ERROR"
        if external_id:
            seen.add(external_id)
        result.append({
            "source_row_number": row_number, "external_id": external_id or None,
            "status": status, "reason": reason, "local_id": local_id,
            "representative_name": name[:120], "store_id": store_id,
            "advisor_id": advisor_id, "budget_band": budget or None, "area_pref": area or None,
            "kana": kana or None,
        })
    return result


def import_upload_limits(db):
    if "csv" not in set(config_value(db, "attachment.allowed_extensions")):
        raise HTTPException(403, "CSV取り込みは設定で無効になっています")
    return config_value(db, "import.max_csv_mb") * 1024 * 1024, config_value(db, "import.max_csv_rows")


async def read_kintone_upload(file, max_bytes):
    filename = Path(file.filename or "").name
    if not filename.lower().endswith(".csv"):
        raise HTTPException(422, "CSVファイルを指定してください")
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(413, "CSVファイルが設定サイズ上限を超えています")
    return filename, content


@app.post("/api/imports/kintone/preview")
async def preview_kintone_csv(file: UploadFile = File(...),
                              mapping_json: str = Form("{}"),
                              actor: CurrentActor = Depends(require_actor)):
    if getattr(actor, "account_role", "") not in ("administrator", "hq_staff"):
        raise HTTPException(403, "kintoneデータを取り込む権限がありません")
    with connect() as db:
        max_bytes, max_rows = import_upload_limits(db)
    filename, content = await read_kintone_upload(file, max_bytes)
    headers, rows = parse_kintone_csv(content, max_rows)
    mapping = resolve_kintone_mapping(headers, mapping_json)
    now = now_jst()
    job_id = str(uuid.uuid4())
    with connect() as db:
        analyzed = analyze_kintone_rows(db, rows, mapping)
        ready = sum(item["status"] == "READY" for item in analyzed)
        skipped = sum(item["status"] == "SKIPPED" for item in analyzed)
        errors = sum(item["status"] == "ERROR" for item in analyzed)
        db.execute(
            """INSERT INTO import_jobs(id,source_system,requested_by,filename,total_rows,
               success_rows,skipped_rows,error_rows,status,created_at,finished_at,content_sha256,
               mapping_json,preview_expires_at)
               VALUES(?,'kintone',?,?,?,?,?,?, 'DRY_RUN',?,?,?,?,?)""",
            (job_id, actor.user_id, filename[:255], len(rows), ready, skipped, errors, now, now,
             hashlib.sha256(content).hexdigest(),
             json.dumps(mapping, ensure_ascii=False, sort_keys=True),
             now + timedelta(hours=1)),
        )
        for item in analyzed:
            db.execute(
                """INSERT INTO import_row_results(job_id,source_row_number,external_id,status,
                   reason,local_id,created_at) VALUES(?,?,?,?,?,?,?)""",
                (job_id, item["source_row_number"], item["external_id"], item["status"],
                 item["reason"], item["local_id"], now),
            )
        audit(db, actor.user_id, "kintone.import_previewed", "import_job", job_id,
              f"ready={ready}; skipped={skipped}; errors={errors}; sha256={hashlib.sha256(content).hexdigest()}")
    return {
        "id": job_id, "status": "DRY_RUN", "filename": filename, "headers": headers,
        "mapping": mapping, "total_rows": len(rows), "ready_rows": ready,
        "skipped_rows": skipped, "error_rows": errors,
        "preview_expires_at": (now + timedelta(hours=1)).isoformat(timespec="seconds"),
        "rows": analyzed[:200], "truncated": len(analyzed) > 200,
    }


@app.post("/api/imports/kintone")
async def import_kintone_csv(file: UploadFile = File(...),
                             preview_job_id: str = Form(...),
                             mapping_json: str = Form("{}"),
                             actor: CurrentActor = Depends(require_actor)):
    if getattr(actor, "account_role", "") not in ("administrator", "hq_staff"):
        raise HTTPException(403, "kintoneデータを取り込む権限がありません")
    with connect() as db:
        max_bytes, max_rows = import_upload_limits(db)
    filename, content = await read_kintone_upload(file, max_bytes)
    headers, rows = parse_kintone_csv(content, max_rows)
    requested_mapping = resolve_kintone_mapping(headers, mapping_json)
    content_hash = hashlib.sha256(content).hexdigest()
    now = now_jst()
    with connect() as db:
        preview = db.execute(
            """SELECT * FROM import_jobs WHERE id=? AND requested_by=?
               AND source_system='kintone' FOR UPDATE""",
            (preview_job_id, actor.user_id),
        ).fetchone()
        if not preview or preview["status"] != "DRY_RUN":
            raise HTTPException(409, "有効なドライラン結果がありません。再度プレビューしてください")
        if not preview["preview_expires_at"] or preview["preview_expires_at"] <= now:
            raise HTTPException(410, "ドライラン結果の有効期限が切れています。再度プレビューしてください")
        saved_mapping = preview["mapping_json"]
        if isinstance(saved_mapping, str):
            saved_mapping = json.loads(saved_mapping)
        if (preview["content_sha256"] != content_hash or
                preview["filename"] != filename or saved_mapping != requested_mapping):
            raise HTTPException(409, "プレビュー後にファイルまたはマッピングが変更されています")
        if not db.execute(
                "UPDATE import_jobs SET status='PROCESSING' WHERE id=? AND status='DRY_RUN'",
                (preview_job_id,)).rowcount:
            raise HTTPException(409, "ドライラン結果は既に使用されています")
        db.execute("DELETE FROM import_row_results WHERE job_id=?", (preview_job_id,))
        analyzed = analyze_kintone_rows(db, rows, requested_mapping)
        imported = skipped = errors = 0
        for item in analyzed:
            external_id = item["external_id"]
            if item["status"] == "SKIPPED":
                db.execute(
                    """INSERT INTO import_row_results(job_id,source_row_number,external_id,status,
                       reason,local_id,created_at) VALUES(?,?,?,'SKIPPED',?,?,?)""",
                    (preview_job_id, item["source_row_number"], external_id, item["reason"],
                     item["local_id"], now),
                )
                skipped += 1
                continue
            if item["status"] == "ERROR":
                db.execute(
                    """INSERT INTO import_row_results(job_id,source_row_number,external_id,status,
                       reason,created_at) VALUES(?,?,?,'ERROR',?,?)""",
                    (preview_job_id, item["source_row_number"], external_id,
                     item["reason"], now),
                )
                errors += 1
                continue
            db.execute("SAVEPOINT kintone_import_row")
            try:
                household_code = "HH-KT-" + hashlib.sha256(
                    external_id.encode("utf-8")
                ).hexdigest()[:12].upper()
                household_id = db.execute(
                    """INSERT INTO households(representative_name,store_id,advisor_id,budget_band,
                       area_pref,land_status,status,created_at,household_code,kana)
                       VALUES(?,?,?,?,?,'検討中','active',?,?,?)""",
                    (item["representative_name"], item["store_id"], item["advisor_id"],
                     item["budget_band"], item["area_pref"], now, household_code, item["kana"]),
                ).lastrowid
                db.execute(
                    """INSERT INTO external_record_mappings(source_system,external_id,object_type,
                       local_id,created_at,updated_at) VALUES('kintone',?,'household',?,?,?)""",
                    (external_id, str(household_id), now, now),
                )
                db.execute(
                    """INSERT INTO stage_events(household_id,from_stage,to_stage,changed_by,changed_at)
                       VALUES(?,NULL,'新規予約',?,?)""",
                    (household_id, actor.user_id, now),
                )
                db.execute("RELEASE SAVEPOINT kintone_import_row")
                db.execute(
                    """INSERT INTO import_row_results(job_id,source_row_number,external_id,status,
                       local_id,created_at) VALUES(?,?,?,'IMPORTED',?,?)""",
                    (preview_job_id, item["source_row_number"], external_id,
                     str(household_id), now),
                )
                imported += 1
            except pymysql.MySQLError as error:
                db.execute("ROLLBACK TO SAVEPOINT kintone_import_row")
                db.execute("RELEASE SAVEPOINT kintone_import_row")
                db.execute(
                    """INSERT INTO import_row_results(job_id,source_row_number,external_id,status,
                       reason,created_at) VALUES(?,?,?,'ERROR',?,?)""",
                    (preview_job_id, item["source_row_number"], external_id,
                     f"データベース登録エラー: {error.args[0]}", now),
                )
                errors += 1
        status = "COMPLETED" if not errors else "COMPLETED_WITH_ERRORS"
        db.execute(
            """UPDATE import_jobs SET success_rows=?,skipped_rows=?,error_rows=?,status=?,finished_at=?
               WHERE id=?""",
            (imported, skipped, errors, status, now_jst(), preview_job_id),
        )
        audit(db, actor.user_id, "kintone.import_completed", "import_job", preview_job_id,
              f"imported={imported}; skipped={skipped}; errors={errors}; sha256={content_hash}")
        create_notification(
            db, actor.user_id, "IMPORT", "kintone CSV取込が完了しました",
            f"{filename}: 取込 {imported} 件、スキップ {skipped} 件、エラー {errors} 件。",
            "import_job", preview_job_id, title_zh="kintone CSV 导入完成",
            message_zh=f"{filename}：导入 {imported} 条，跳过 {skipped} 条，错误 {errors} 条。",
        )
    return {"id": preview_job_id, "status": status, "total_rows": len(rows),
            "success_rows": imported, "skipped_rows": skipped, "error_rows": errors}


@app.get("/api/import-jobs/{job_id}")
def import_job_detail(job_id: str, limit: int = 100, offset: int = 0,
                      actor: CurrentActor = Depends(require_actor)):
    if not 1 <= limit <= 500 or offset < 0:
        raise HTTPException(422, "取得範囲が正しくありません")
    with connect() as db:
        job = db.execute(
            "SELECT * FROM import_jobs WHERE id=?",
            (job_id,),
        ).fetchone()
        if not job or (job["requested_by"] != actor.user_id and
                       getattr(actor, "account_role", "") not in ("administrator", "hq_staff")):
            raise HTTPException(404, "取り込み結果が見つかりません")
        results = db.execute(
            """SELECT source_row_number,external_id,status,reason,local_id,created_at
               FROM import_row_results WHERE job_id=? ORDER BY source_row_number LIMIT ? OFFSET ?""",
            (job_id, limit, offset),
        ).fetchall()
    result = dict(job)
    result["rows"] = [dict(row) for row in results]
    return result


@app.get("/api/operations/status")
def operations_status(actor: CurrentActor = Depends(require_actor)):
    if getattr(actor, "account_role", "") not in ("administrator", "executive", "finance", "hq_staff"):
        raise HTTPException(403, "運用状態を確認する権限がありません")
    now = now_jst()
    with connect() as db:
        audit_chain_status = "OK"
        try:
            verify_audit_chain(db)
        except RuntimeError:
            audit_chain_status = "DEGRADED"
            LOGGER.exception("Audit chain integrity check failed during operations status request.")
        outbox = db.execute(
            """SELECT COUNT(*) AS pending FROM audit_outbox WHERE status IN ('PENDING','PROCESSING')"""
        ).fetchone()
        dead_letters = db.execute(
            "SELECT COUNT(*) AS count FROM audit_outbox WHERE status='DEAD_LETTER'"
        ).fetchone()
        expired_exports = db.execute(
            "SELECT COUNT(*) AS count FROM export_jobs WHERE status='READY' AND expires_at<=?",
            (now,),
        ).fetchone()
        active_sessions = db.execute(
            "SELECT COUNT(*) AS count FROM auth_sessions WHERE revoked_at IS NULL AND expires_at>?",
            (now,),
        ).fetchone()
        fallback_tasks = db.execute(
            "SELECT COUNT(*) AS count FROM tasks WHERE source='notification_fallback' AND done=0 AND cancelled=0"
        ).fetchone()
        seed = db.execute("SELECT batch_key,seeded_at FROM seed_metadata WHERE id=1").fetchone()
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "database": "OK",
        "audit_chain": audit_chain_status,
        "outbox_pending": outbox["pending"],
        "outbox_dead_letters": dead_letters["count"],
        "expired_exports_ready_for_cleanup": expired_exports["count"],
        "active_sessions": active_sessions["count"],
        "notification_fallback_tasks": fallback_tasks["count"],
        "email_integration": "NOT_CONFIGURED",
        "seed_batch": seed["batch_key"] if seed else None,
        "seeded_at": seed["seeded_at"] if seed else None,
    }


@app.get("/api/health")
def health():
    with connect() as db:
        db.execute("SELECT 1")
    return {"status": "ok"}


rental.register_rental_routes(app, connect, require_actor)

DIST = ROOT / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def frontend(path: str):
        candidate = DIST / path
        return FileResponse(candidate if candidate.is_file() else DIST / "index.html")
