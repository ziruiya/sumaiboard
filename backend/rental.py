"""Rental schema, sample data, and staff workflows."""

import json
import random
import re
import uuid
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pymysql.err import IntegrityError, OperationalError

TENANT_ID = 1
JST = ZoneInfo("Asia/Tokyo")

# Tables are declared in dependency order so reset can drop them in reverse order.
TABLE_DEFINITIONS = {
    "parties": """
        party_code VARCHAR(40) NOT NULL, party_type VARCHAR(24) NOT NULL,
        display_name VARCHAR(200) NOT NULL, name_kana VARCHAR(200), postal_code VARCHAR(20),
        address VARCHAR(500), phone VARCHAR(50), email VARCHAR(255), contact_person VARCHAR(120),
        remittance_destination_ref VARCHAR(120), status VARCHAR(24) NOT NULL, notes TEXT,
        UNIQUE (tenant_id, party_code)
    """,
    "buildings": """
        building_code VARCHAR(40) NOT NULL, building_name VARCHAR(200) NOT NULL,
        postal_code VARCHAR(20), address VARCHAR(500) NOT NULL, building_type VARCHAR(40) NOT NULL,
        structure_type VARCHAR(40), construction_month DATE, floor_count INT,
        management_start_date DATE, status VARCHAR(24) NOT NULL, notes TEXT,
        UNIQUE (tenant_id, building_code)
    """,
    "units": """
        building_id BIGINT NOT NULL, unit_number VARCHAR(32) NOT NULL, owner_party_id BIGINT NOT NULL,
        floor_number INT, floor_area DECIMAL(8,2), layout_type VARCHAR(32),
        advertised_rent BIGINT NOT NULL, advertised_common_fee BIGINT NOT NULL,
        management_status VARCHAR(24) NOT NULL, occupancy_status VARCHAR(24) NOT NULL, notes TEXT,
        UNIQUE (tenant_id, building_id, unit_number)
    """,
    "fee_plans": """
        plan_code VARCHAR(40) NOT NULL, plan_name VARCHAR(120) NOT NULL, plan_version INT NOT NULL,
        rate DECIMAL(9,6) NOT NULL, calculation_basis VARCHAR(32) NOT NULL,
        included_charge_types JSON NOT NULL, tax_inclusive BOOLEAN NOT NULL, tax_rate DECIMAL(9,6) NOT NULL,
        vacancy_exempt BOOLEAN NOT NULL, rounding_rule VARCHAR(24) NOT NULL,
        minimum_fee BIGINT NOT NULL, effective_from DATE NOT NULL, effective_to DATE,
        status VARCHAR(24) NOT NULL, UNIQUE (tenant_id, plan_code, plan_version)
    """,
    "management_contracts": """
        contract_code VARCHAR(40) NOT NULL, owner_party_id BIGINT NOT NULL,
        principal_party_id BIGINT NOT NULL, payee_party_id BIGINT NOT NULL,
        acquisition_channel VARCHAR(32) NOT NULL, accepted_date DATE NOT NULL, acquired_date DATE,
        start_date DATE NOT NULL, end_date DATE, previous_manager_name VARCHAR(200),
        assigned_user_id INT NOT NULL, fee_plan_id BIGINT NOT NULL, fee_plan_version INT NOT NULL,
        fee_plan_snapshot JSON NOT NULL, charge_rule_snapshot JSON NOT NULL,
        settlement_cutoff_day TINYINT NOT NULL, remittance_day TINYINT NOT NULL,
        deposit_custodian VARCHAR(32) NOT NULL, status VARCHAR(24) NOT NULL,
        termination_reason TEXT, notes TEXT, UNIQUE (tenant_id, contract_code)
    """,
    "management_contract_units": """
        management_contract_id BIGINT NOT NULL, unit_id BIGINT NOT NULL,
        valid_from DATE NOT NULL, valid_to DATE,
        UNIQUE (tenant_id, management_contract_id, unit_id, valid_from)
    """,
    "applications": """
        application_code VARCHAR(40) NOT NULL, unit_id BIGINT NOT NULL, applicant_party_id BIGINT NOT NULL,
        application_date DATE NOT NULL, application_channel VARCHAR(32) NOT NULL,
        desired_move_in_date DATE NOT NULL, proposed_rent BIGINT NOT NULL,
        proposed_common_fee BIGINT NOT NULL, screening_result VARCHAR(24) NOT NULL,
        external_procedure_status VARCHAR(32) NOT NULL, external_reference VARCHAR(120),
        cancellation_reason TEXT, assigned_user_id INT NOT NULL, status VARCHAR(24) NOT NULL,
        notes TEXT, UNIQUE (tenant_id, application_code)
    """,
    "leases": """
        lease_code VARCHAR(40) NOT NULL, application_id BIGINT, unit_id BIGINT NOT NULL,
        tenant_party_id BIGINT NOT NULL, guarantor_party_id BIGINT, contract_type VARCHAR(32) NOT NULL,
        signed_date DATE, start_date DATE NOT NULL, scheduled_end_date DATE, actual_move_in_date DATE,
        rent_amount BIGINT NOT NULL, common_fee_amount BIGINT NOT NULL,
        deposit_amount BIGINT NOT NULL, key_money_amount BIGINT NOT NULL,
        payment_due_day TINYINT NOT NULL, proration_rule VARCHAR(32) NOT NULL,
        external_signature_status VARCHAR(32) NOT NULL, termination_notice_date DATE,
        scheduled_move_out_date DATE, actual_move_out_date DATE, termination_reason TEXT,
        status VARCHAR(24) NOT NULL, UNIQUE (tenant_id, lease_code), UNIQUE (tenant_id, application_id)
    """,
    "charge_types": """
        charge_code VARCHAR(40) NOT NULL, charge_name VARCHAR(120) NOT NULL,
        beneficiary_type VARCHAR(32) NOT NULL, tax_category VARCHAR(24) NOT NULL,
        refundable BOOLEAN NOT NULL, recurring BOOLEAN NOT NULL, settlement_eligible BOOLEAN NOT NULL,
        status VARCHAR(24) NOT NULL, UNIQUE (tenant_id, charge_code)
    """,
    "rent_charges": """
        charge_code VARCHAR(40) NOT NULL, lease_id BIGINT NOT NULL, management_contract_id BIGINT NOT NULL,
        charge_type_id BIGINT NOT NULL, service_month DATE NOT NULL, service_from DATE, service_to DATE,
        due_date DATE NOT NULL, amount BIGINT NOT NULL, tax_category VARCHAR(24) NOT NULL,
        tax_amount BIGINT NOT NULL, beneficiary_snapshot JSON NOT NULL, source_type VARCHAR(32) NOT NULL,
        source_reference VARCHAR(120) NOT NULL, status VARCHAR(24) NOT NULL, cancellation_reason TEXT,
        recurring_month DATE GENERATED ALWAYS AS
            (CASE WHEN source_type = 'MONTHLY_RECURRING' THEN service_month END) STORED,
        UNIQUE (tenant_id, charge_code),
        UNIQUE (tenant_id, lease_id, charge_type_id, recurring_month),
        UNIQUE (tenant_id, source_type, source_reference),
        INDEX (tenant_id, service_month)
    """,
    "fund_accounts": """
        account_code VARCHAR(40) NOT NULL, account_name VARCHAR(120) NOT NULL,
        account_type VARCHAR(32) NOT NULL, currency CHAR(3) NOT NULL DEFAULT 'JPY',
        is_simulated BOOLEAN NOT NULL, status VARCHAR(24) NOT NULL, UNIQUE (tenant_id, account_code)
    """,
    "payments": """
        payment_code VARCHAR(40) NOT NULL, received_date DATE NOT NULL, amount BIGINT NOT NULL,
        payer_name VARCHAR(200) NOT NULL, payer_party_id BIGINT, payment_source VARCHAR(32) NOT NULL,
        fund_account_id BIGINT NOT NULL, management_contract_id BIGINT,
        external_reference VARCHAR(120), idempotency_key VARCHAR(120) NOT NULL,
        status VARCHAR(24) NOT NULL, notes TEXT,
        UNIQUE (tenant_id, payment_code), UNIQUE (tenant_id, idempotency_key), INDEX (tenant_id, status)
    """,
    "payment_allocations": """
        payment_id BIGINT NOT NULL, charge_id BIGINT NOT NULL, allocation_date DATE NOT NULL,
        amount BIGINT NOT NULL, allocated_by INT NOT NULL, idempotency_key VARCHAR(120) NOT NULL,
        reversal_of_id BIGINT, reason TEXT, UNIQUE (tenant_id, idempotency_key)
    """,
    "fund_ledger_entries": """
        entry_code VARCHAR(40) NOT NULL, transaction_group_id VARCHAR(80) NOT NULL,
        fund_account_id BIGINT NOT NULL, management_contract_id BIGINT, fund_category VARCHAR(32) NOT NULL,
        entry_type VARCHAR(32) NOT NULL, direction VARCHAR(8) NOT NULL, amount BIGINT NOT NULL,
        posting_date DATE NOT NULL, accounting_month DATE NOT NULL, source_type VARCHAR(40) NOT NULL,
        source_id BIGINT NOT NULL, reversal_of_id BIGINT, reason TEXT, UNIQUE (tenant_id, entry_code),
        INDEX (tenant_id, source_type, source_id)
    """,
    "deposits": """
        lease_id BIGINT NOT NULL, management_contract_id BIGINT NOT NULL, custodian_type VARCHAR(32) NOT NULL,
        agreed_amount BIGINT NOT NULL, received_amount BIGINT NOT NULL, refunded_amount BIGINT NOT NULL,
        transferred_amount BIGINT NOT NULL, status VARCHAR(24) NOT NULL,
        UNIQUE (tenant_id, lease_id, management_contract_id)
    """,
    "owner_settlements": """
        settlement_code VARCHAR(40) NOT NULL, management_contract_id BIGINT NOT NULL,
        settlement_month DATE NOT NULL, cutoff_date DATE NOT NULL, opening_available_balance BIGINT NOT NULL,
        collected_income BIGINT NOT NULL, management_fee BIGINT NOT NULL, approved_expenses BIGINT NOT NULL,
        adjustment_amount BIGINT NOT NULL, payable_amount BIGINT NOT NULL, closing_available_balance BIGINT NOT NULL,
        outstanding_expense_balance BIGINT NOT NULL, calculation_snapshot JSON NOT NULL,
        status VARCHAR(24) NOT NULL, submitted_by INT, approved_by INT, approved_at DATETIME(6),
        UNIQUE (tenant_id, settlement_code), INDEX (tenant_id, settlement_month, status)
    """,
    "settlement_lines": """
        settlement_id BIGINT NOT NULL, line_type VARCHAR(32) NOT NULL, unit_id BIGINT,
        source_type VARCHAR(40) NOT NULL, source_id BIGINT NOT NULL, description VARCHAR(255) NOT NULL,
        amount BIGINT NOT NULL, tax_amount BIGINT NOT NULL, source_month DATE,
        rule_snapshot JSON, adjustment_of_id BIGINT, INDEX (tenant_id, source_type, source_id)
    """,
    "owner_remittances": """
        remittance_code VARCHAR(40) NOT NULL, settlement_id BIGINT NOT NULL, payee_party_id BIGINT NOT NULL,
        destination_snapshot JSON NOT NULL, scheduled_amount BIGINT NOT NULL, actual_amount BIGINT,
        scheduled_date DATE NOT NULL, remitted_date DATE, simulation_reference VARCHAR(120),
        failure_reason TEXT, status VARCHAR(32) NOT NULL,
        successful_settlement_id BIGINT GENERATED ALWAYS AS
            (CASE WHEN status = 'SIMULATED_REMITTED' THEN settlement_id END) STORED,
        UNIQUE (tenant_id, remittance_code), UNIQUE (tenant_id, successful_settlement_id)
    """,
    "complaints": """
        complaint_code VARCHAR(40) NOT NULL, building_id BIGINT NOT NULL, unit_id BIGINT, reporter_party_id BIGINT,
        received_at DATETIME(6) NOT NULL, category VARCHAR(32) NOT NULL, urgency VARCHAR(24) NOT NULL,
        description TEXT NOT NULL, assigned_user_id INT NOT NULL, resolved_at DATETIME(6),
        resolution_summary TEXT, status VARCHAR(24) NOT NULL, UNIQUE (tenant_id, complaint_code)
    """,
    "work_orders": """
        work_order_code VARCHAR(40) NOT NULL, building_id BIGINT NOT NULL, unit_id BIGINT,
        management_contract_id BIGINT, complaint_id BIGINT, received_date DATE NOT NULL,
        category VARCHAR(32) NOT NULL, urgency VARCHAR(24) NOT NULL, description TEXT NOT NULL,
        contractor_party_id BIGINT, cost_bearer VARCHAR(24), estimated_amount BIGINT,
        approved_amount BIGINT, actual_amount BIGINT, approved_by INT, scheduled_date DATE,
        completed_date DATE, inspected_date DATE, inspected_by INT, cost_confirmed_at DATETIME(6),
        assigned_user_id INT NOT NULL, status VARCHAR(24) NOT NULL, UNIQUE (tenant_id, work_order_code)
    """,
    "inspections": """
        building_id BIGINT NOT NULL, unit_id BIGINT, work_order_id BIGINT,
        inspection_type VARCHAR(32) NOT NULL, inspection_date DATE NOT NULL, inspected_by INT NOT NULL,
        result VARCHAR(32) NOT NULL, findings TEXT, next_inspection_date DATE
    """,
    "owner_accounts": """
        user_id INT NOT NULL UNIQUE, party_id BIGINT NOT NULL, UNIQUE (tenant_id, party_id)
    """,
}

RELATIONSHIPS = {
    "units": {"building_id": "buildings", "owner_party_id": "parties"},
    "management_contracts": {
        "owner_party_id": "parties", "principal_party_id": "parties", "payee_party_id": "parties",
        "assigned_user_id": "users", "fee_plan_id": "fee_plans",
    },
    "management_contract_units": {"management_contract_id": "management_contracts", "unit_id": "units"},
    "applications": {"unit_id": "units", "applicant_party_id": "parties", "assigned_user_id": "users"},
    "leases": {
        "application_id": "applications", "unit_id": "units",
        "tenant_party_id": "parties", "guarantor_party_id": "parties",
    },
    "rent_charges": {
        "lease_id": "leases", "management_contract_id": "management_contracts", "charge_type_id": "charge_types",
    },
    "payments": {
        "payer_party_id": "parties", "fund_account_id": "fund_accounts",
        "management_contract_id": "management_contracts",
    },
    "payment_allocations": {
        "payment_id": "payments", "charge_id": "rent_charges", "allocated_by": "users",
        "reversal_of_id": "payment_allocations",
    },
    "fund_ledger_entries": {
        "fund_account_id": "fund_accounts", "management_contract_id": "management_contracts",
        "reversal_of_id": "fund_ledger_entries",
    },
    "deposits": {"lease_id": "leases", "management_contract_id": "management_contracts"},
    "owner_settlements": {
        "management_contract_id": "management_contracts", "submitted_by": "users", "approved_by": "users",
    },
    "settlement_lines": {"settlement_id": "owner_settlements", "unit_id": "units", "adjustment_of_id": "settlement_lines"},
    "owner_remittances": {"settlement_id": "owner_settlements", "payee_party_id": "parties"},
    "complaints": {
        "building_id": "buildings", "unit_id": "units", "reporter_party_id": "parties", "assigned_user_id": "users",
    },
    "work_orders": {
        "building_id": "buildings", "unit_id": "units", "management_contract_id": "management_contracts",
        "complaint_id": "complaints", "contractor_party_id": "parties", "approved_by": "users",
        "inspected_by": "users", "assigned_user_id": "users",
    },
    "inspections": {"building_id": "buildings", "unit_id": "units", "work_order_id": "work_orders", "inspected_by": "users"},
    "owner_accounts": {"user_id": "users", "party_id": "parties"},
}


def _create_table(table, columns):
    keys = []
    for column, target in RELATIONSHIPS.get(table, {}).items():
        if target == "users":
            keys.append(f"FOREIGN KEY ({column}) REFERENCES users (id)")
        else:
            keys.append(f"FOREIGN KEY (tenant_id, {column}) REFERENCES {target} (tenant_id, id)")
    constraints = "".join(f",\n        {key}" for key in keys)
    return f"""CREATE TABLE IF NOT EXISTS {table} (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        tenant_id INT NOT NULL DEFAULT 1,
        created_at DATETIME(6) NOT NULL DEFAULT (UTC_TIMESTAMP(6)),
        updated_at DATETIME(6) NOT NULL DEFAULT (UTC_TIMESTAMP(6)),
        created_by INT, updated_by INT, version INT NOT NULL DEFAULT 1,
        UNIQUE (tenant_id, id),
        {columns.strip()}{constraints}
    ) ENGINE=InnoDB;"""


RENTAL_SCHEMA = "\n".join(_create_table(table, columns) for table, columns in TABLE_DEFINITIONS.items())
RENTAL_RESET_TABLES = tuple(reversed(TABLE_DEFINITIONS))
SEED_COMPLETED_KEY = "rental_seed_completed"


# Reset recreates the tables at the current width and keeps schema history.
# CREATE IF NOT EXISTS also restores tables during reset and interrupted setup.
_RENTAL_V2_COLUMNS = {
    "parties": {"display_name": (200, "NOT NULL"), "name_kana": (200, "NULL"), "address": (500, "NULL")},
    "buildings": {"building_name": (200, "NOT NULL"), "address": (500, "NOT NULL")},
    "units": {"unit_number": (32, "NOT NULL"), "layout_type": (32, "NULL")},
    "management_contracts": {"previous_manager_name": (200, "NULL")},
    "payments": {"payer_name": (200, "NOT NULL")},
}


def widen_rental_columns(db):
    for table, columns in _RENTAL_V2_COLUMNS.items():
        widths = {
            row["COLUMN_NAME"]: row["CHARACTER_MAXIMUM_LENGTH"]
            for row in db.execute(
                """SELECT COLUMN_NAME, CHARACTER_MAXIMUM_LENGTH FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=?""", (table,),
            )
        }
        changes = [
            f"MODIFY COLUMN `{column}` VARCHAR({width}) {nullable}"
            for column, (width, nullable) in columns.items() if widths[column] < width
        ]
        if changes:
            db.execute(f"ALTER TABLE `{table}` " + ", ".join(changes))


def ensure_rental_schema(db):
    db.executescript(RENTAL_SCHEMA)
    db.execute(
        """CREATE TABLE IF NOT EXISTS rental_schema_migrations (
            version INT PRIMARY KEY, applied_at DATETIME NOT NULL
        ) ENGINE=InnoDB"""
    )
    applied = {row["version"] for row in db.execute("SELECT version FROM rental_schema_migrations")}
    for version, migrate in ((1, None), (2, widen_rental_columns)):
        if version in applied:
            continue
        if migrate:
            migrate(db)
        db.execute("INSERT INTO rental_schema_migrations VALUES (?, UTC_TIMESTAMP())", (version,))


def check_rental_reset_scope(db, *, existing_tables=None):
    for table in RENTAL_RESET_TABLES:
        if existing_tables is not None and table not in existing_tables:
            continue
        if db.execute(f"SELECT 1 FROM {table} WHERE tenant_id <> ? LIMIT 1", (TENANT_ID,)).fetchone():
            raise HTTPException(409, "サンプル以外の賃貸管理データがあるためリセットできません")


def _month_shift(month, offset):
    year, month_index = divmod(month.year * 12 + month.month - 1 + offset, 12)
    return date(year, month_index + 1, 1)


def seed_rental(db):
    # Lock an existing baseline row until the surrounding transaction commits.
    # This serializes startup seed attempts even when the rental tables are empty.
    staff = db.execute(
        """SELECT id FROM users WHERE role IN ('advisor', 'executive', 'administrator')
           ORDER BY id LIMIT 1 FOR UPDATE"""
    ).fetchone()
    if db.execute(
        "SELECT value_json FROM system_configs WHERE config_key=? FOR UPDATE", (SEED_COMPLETED_KEY,),
    ).fetchone():
        return
    if not staff:
        raise RuntimeError("Rental sample seeding requires a baseline staff account")
    for table in RENTAL_RESET_TABLES:
        # Clear nullable self-references before deleting rows in foreign-key order.
        for column, target in RELATIONSHIPS.get(table, {}).items():
            if target == table:
                db.execute(f"UPDATE {table} SET {column}=NULL WHERE tenant_id=? AND {column} IS NOT NULL",
                           (TENANT_ID,))
        db.execute(f"DELETE FROM {table} WHERE tenant_id=?", (TENANT_ID,))
    staff_id = staff["id"]
    month = datetime.now(JST).date().replace(day=1)
    history = [_month_shift(month, offset) for offset in range(-12, 0)]
    start = history[0]
    stamp = datetime.combine(month, datetime.min.time())
    rng = random.Random(20261126)

    def insert(table, **fields):
        values = dict(tenant_id=TENANT_ID, created_at=stamp, updated_at=stamp, **fields)
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        return db.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", tuple(values.values())).lastrowid

    def party(code, name, kind="individual"):
        return insert("parties", party_code=code, party_type=kind, display_name=name, status="ACTIVE")

    owners = [party(f"OWN-{letter}", f"サンプルオーナー{letter}") for letter in "ABCDEFGHIJKL"]
    for letter, party_id in zip("AB", owners):
        code = f"OW-{letter}"
        name = f"サンプルオーナー{letter}"
        db.execute(
            """INSERT INTO users (name, role, employee_code, public_id, display_name, must_change_password)
               VALUES (?, 'owner', ?, ?, ?, 0)
               ON DUPLICATE KEY UPDATE id=id""",
            (name, code, str(uuid.uuid5(uuid.NAMESPACE_URL, f"sumaiboard:sample:{code}")), name),
        )
        account = db.execute("SELECT id, role FROM users WHERE employee_code=?", (code,)).fetchone()
        if not account or account["role"] != "owner":
            raise RuntimeError(f"Sample owner employee code is already in use: {code}")
        insert("owner_accounts", user_id=account["id"], party_id=party_id)

    contractors = [party(f"VENDOR-{n}", f"サンプル修繕事業者{n}", "company") for n in range(1, 4)]
    guarantor = party("GUARANTOR-1", "サンプル保証事業者", "company")
    charge_rules = {}
    for code, name, beneficiary, tax, refundable, recurring, eligible in (
        ("RENT", "家賃", "OWNER", "EXEMPT", False, True, True),
        ("COMMON_FEE", "共益費", "OWNER", "EXEMPT", False, True, True),
        ("KEY_MONEY", "礼金", "OWNER", "EXEMPT", False, False, True),
        ("DEPOSIT", "敷金", "CUSTODY", "OUT_OF_SCOPE", True, False, False),
        ("RENEWAL", "更新料", "OWNER", "EXEMPT", False, False, True),
        ("RENEWAL_ADMIN", "更新事務手数料", "COMPANY", "TAXABLE", False, False, False),
        ("BROKERAGE", "仲介手数料", "COMPANY", "TAXABLE", False, False, False),
        ("MANAGEMENT", "管理料", "COMPANY", "TAXABLE", False, False, False),
        ("REPAIR", "修繕費", "COST_BEARER", "TAXABLE", False, False, True),
    ):
        rule = dict(beneficiary_type=beneficiary, tax_category=tax, refundable=refundable,
                    recurring=recurring, settlement_eligible=eligible)
        charge_id = insert("charge_types", charge_code=code, charge_name=name, status="ACTIVE", **rule)
        charge_rules[code] = dict(id=charge_id, **rule)

    plans = []
    for letter, rate, vacancy_exempt in (("A", "0.050000", False), ("B", "0.033000", True)):
        rule = dict(plan_code=f"PLAN-{letter}", plan_name=f"サンプルプラン{letter}", plan_version=1,
                    rate=rate, calculation_basis="CASH_COLLECTED", tax_inclusive=True, tax_rate="0.100000",
                    vacancy_exempt=vacancy_exempt, rounding_rule="FLOOR", minimum_fee=0)
        included = ["RENT", "COMMON_FEE"]
        plan_id = insert("fee_plans", **rule, included_charge_types=json.dumps(included),
                         effective_from=start, status="ACTIVE")
        plans.append((plan_id, json.dumps(dict(rule, included_charge_types=included))))

    escrow_id = insert("fund_accounts", account_code="ESCROW", account_name="預り金口座",
                       account_type="OWNER_FUNDS", is_simulated=True, status="ACTIVE")
    insert("fund_accounts", account_code="COMPANY", account_name="自社資金口座",
           account_type="COMPANY_FUNDS", is_simulated=True, status="ACTIVE")

    def ledger(code, contract_id, category, amount, posted, source_type, source_id, group):
        insert("fund_ledger_entries", entry_code=code, transaction_group_id=group,
               fund_account_id=escrow_id, management_contract_id=contract_id, fund_category=category,
               entry_type="RECEIPT", direction="IN", amount=amount, posting_date=posted,
               accounting_month=posted.replace(day=1), source_type=source_type, source_id=source_id)

    vacant = []
    occupied = []
    building_sizes = [5, 5, 8, 6, 8] + [12] * 3 + [11] * 12
    vacancy_buildings = {2, *range(3, 21)}
    for building_number, size in enumerate(building_sizes, start=1):
        if building_number <= 2:
            owner_index = 0
        elif building_number == 3:
            owner_index = 1
        else:
            owner_index = 2 + (building_number - 4) % 10
        owner = owners[owner_index]
        building_id = insert("buildings", building_code=f"BLD-{building_number:02}",
                             building_name=f"サンプル物件 {building_number:02}",
                             address=f"サンプル市見本町 {building_number} 番地（架空）",
                             building_type="APARTMENT", management_start_date=start, status="ACTIVE")
        plan_id, snapshot = plans[owner_index % 2]
        for room in range(1, size + 1):
            code = f"{building_number:02}-{100 + room}"
            fixture = code == "01-101"
            is_vacant = (building_number in vacancy_buildings and room == size) or (
                building_number == 20 and room == size - 1
            )
            rent = 80000 if fixture else rng.randrange(55, 131) * 1000
            common_fee = 5000 if fixture else rng.randrange(3, 9) * 1000
            unit_id = insert("units", building_id=building_id, unit_number=str(100 + room),
                             owner_party_id=owner, floor_number=1, advertised_rent=rent,
                             advertised_common_fee=common_fee, management_status="MANAGED",
                             occupancy_status="VACANT" if is_vacant else "OCCUPIED")
            contract_fields = dict(
                owner_party_id=owner, principal_party_id=owner, payee_party_id=owner,
                acquisition_channel="MANAGEMENT_TRANSFER", assigned_user_id=staff_id, fee_plan_id=plan_id,
                fee_plan_version=1, fee_plan_snapshot=snapshot, charge_rule_snapshot=json.dumps(charge_rules),
                settlement_cutoff_day=31, remittance_day=15, deposit_custodian="COMPANY",
            )
            contract_start = month if fixture else start
            historical_contract = None
            if fixture:
                historical_end = month - timedelta(days=1)
                historical_contract = insert(
                    "management_contracts", contract_code=f"MC-{code}-HISTORY", accepted_date=start,
                    start_date=start, end_date=historical_end, status="ENDED", **contract_fields,
                )
                insert("management_contract_units", management_contract_id=historical_contract,
                       unit_id=unit_id, valid_from=start, valid_to=historical_end)
            contract_id = insert(
                "management_contracts", contract_code=f"MC-{code}", accepted_date=contract_start,
                start_date=contract_start, status="ACTIVE", **contract_fields,
            )
            insert("management_contract_units", management_contract_id=contract_id,
                   unit_id=unit_id, valid_from=contract_start)
            if is_vacant:
                vacant.append((unit_id, rent, common_fee))
                continue

            tenant = party(f"TEN-{code}", f"サンプル入居者 {code}")
            occupied.append((building_id, unit_id, contract_id, tenant))
            application_id = None
            if fixture:
                application_id = insert(
                    "applications", application_code="APP-F03", unit_id=unit_id, applicant_party_id=tenant,
                    application_date=start, application_channel="SAMPLE", desired_move_in_date=start,
                    proposed_rent=rent, proposed_common_fee=common_fee, screening_result="APPROVED",
                    external_procedure_status="RECORDED_SAMPLE", assigned_user_id=staff_id, status="CONTRACTED",
                )
            lease_id = insert(
                "leases", lease_code=f"LEASE-{code}", application_id=application_id, unit_id=unit_id,
                tenant_party_id=tenant, guarantor_party_id=guarantor, contract_type="STANDARD",
                signed_date=start, start_date=start, actual_move_in_date=start, rent_amount=rent,
                common_fee_amount=common_fee, deposit_amount=rent, key_money_amount=0,
                payment_due_day=1, proration_rule="ACTUAL_DAYS_FLOOR",
                external_signature_status="RECORDED_SAMPLE", status="OCCUPIED",
            )
            deposit_id = insert(
                "deposits", lease_id=lease_id, management_contract_id=contract_id, custodian_type="COMPANY",
                agreed_amount=rent, received_amount=rent, refunded_amount=0, transferred_amount=0, status="HELD",
            )
            ledger(f"D-{code}", contract_id, "DEPOSIT", rent, month if fixture else start,
                   "deposit", deposit_id, f"D-{code}")

            for service_month in [*history, month]:
                billing_contract = historical_contract if fixture and service_month < month else contract_id
                suffix = f"{code}-{service_month:%Y%m}"
                paid = (fixture and service_month == month) or rng.random() < 0.93
                payment_id = None
                if paid:
                    payment_id = insert(
                        "payments", payment_code=f"P-{suffix}", received_date=service_month,
                        amount=rent + common_fee, payer_name=f"サンプル入居者 {code}", payer_party_id=tenant,
                        payment_source="TENANT", fund_account_id=escrow_id, management_contract_id=billing_contract,
                        idempotency_key=f"SEED-P-{suffix}", status="ALLOCATED",
                    )
                for charge, amount in (("RENT", rent), ("COMMON_FEE", common_fee)):
                    rule = charge_rules[charge]
                    reference = f"{charge}-{suffix}"
                    charge_id = insert(
                        "rent_charges", charge_code=reference, lease_id=lease_id, management_contract_id=billing_contract,
                        charge_type_id=rule["id"], service_month=service_month, service_from=service_month,
                        service_to=_month_shift(service_month, 1) - timedelta(days=1),
                        due_date=service_month, amount=amount, tax_category=rule["tax_category"], tax_amount=0,
                        beneficiary_snapshot=json.dumps(dict(beneficiary_type="OWNER", owner_party_id=owner)),
                        source_type="MONTHLY_RECURRING", source_reference=reference,
                        status="PAID" if paid else "UNPAID",
                    )
                    if payment_id is not None:
                        allocation_id = insert(
                            "payment_allocations", payment_id=payment_id, charge_id=charge_id,
                            allocation_date=service_month, amount=amount, allocated_by=staff_id,
                            idempotency_key=f"SEED-A-{reference}",
                        )
                        ledger(reference, billing_contract, "OWNER_RENT" if charge == "RENT" else "OWNER_OTHER",
                               amount, service_month, "payment_allocation", allocation_id, f"P-{suffix}")

    payment_id = insert("payments", payment_code="P-UNIDENTIFIED", received_date=month, amount=20000,
                        payer_name="サンプル未確認入金", payment_source="OTHER", fund_account_id=escrow_id,
                        idempotency_key="SEED-UNIDENTIFIED", status="UNALLOCATED")
    ledger("P-UNIDENTIFIED", None, "UNIDENTIFIED", 20000, month, "payment", payment_id, "P-UNIDENTIFIED")

    for index, status in enumerate(("RECEIVED", "SCREENING", "APPROVED"), start=1):
        unit_id, rent, common_fee = vacant[index - 1]
        db.execute("UPDATE units SET occupancy_status=? WHERE tenant_id=? AND id=?",
                   ("CONTRACTING" if status == "APPROVED" else "APPLYING", TENANT_ID, unit_id))
        applicant_id = party(f"APP-PARTY-{index}", f"サンプル申込者 {index}")
        insert("applications", application_code=f"APP-{index:02}", unit_id=unit_id,
               applicant_party_id=applicant_id, application_date=month, application_channel="SAMPLE",
               desired_move_in_date=_month_shift(month, 1), proposed_rent=rent, proposed_common_fee=common_fee,
               screening_result="APPROVED" if status == "APPROVED" else "PENDING",
               external_procedure_status="NOT_STARTED_SAMPLE", assigned_user_id=staff_id, status=status)

    # 25 complaints, 15 work orders (including F03), and six inspections.
    for index in range(25):
        building_id, unit_id, _, tenant = occupied[index * 7]
        received = datetime.combine(history[index % 12], datetime.min.time())
        closed = index % 3 == 2
        insert("complaints", complaint_code=f"CMP-{index + 1:02}", building_id=building_id,
               unit_id=unit_id, reporter_party_id=tenant, received_at=received, category="NOISE",
               urgency="URGENT" if index % 5 == 0 else "NORMAL", description="サンプル騒音相談",
               assigned_user_id=staff_id, resolved_at=received if closed else None,
               resolution_summary="サンプル対応済み" if closed else None,
               status=("OPEN", "IN_PROGRESS", "CLOSED")[index % 3])

    for index in range(15):
        building_id, unit_id, contract_id, _ = occupied[index * 11]
        received = month if index == 0 else history[(index - 1) % 12]
        inspected = index < 6
        if index == 0:
            status = "COST_CONFIRMED"
        else:
            status = "INSPECTED" if inspected else ("RECEIVED", "ESTIMATED", "APPROVED")[index % 3]
        amount = 12000 if index == 0 else rng.randrange(8, 30) * 1000
        approved = inspected or status == "APPROVED"
        work_order_id = insert(
            "work_orders", work_order_code="WO-F03" if index == 0 else f"WO-{index:02}",
            building_id=building_id, unit_id=unit_id, management_contract_id=contract_id,
            received_date=received, category="EQUIPMENT", urgency="NORMAL",
            description="サンプル設備修繕", contractor_party_id=contractors[index % 3], cost_bearer="OWNER",
            estimated_amount=amount if status != "RECEIVED" else None,
            approved_amount=amount if approved else None, approved_by=staff_id if approved else None,
            actual_amount=amount if inspected else None, scheduled_date=received if inspected else None,
            completed_date=received if inspected else None, inspected_date=received if inspected else None,
            inspected_by=staff_id if inspected else None,
            cost_confirmed_at=stamp if index == 0 else None, assigned_user_id=staff_id, status=status,
        )
        if inspected:
            insert("inspections", building_id=building_id, unit_id=unit_id, work_order_id=work_order_id,
                   inspection_type="REPAIR_ACCEPTANCE", inspection_date=received, inspected_by=staff_id, result="PASS")

    db.execute(
        """INSERT INTO system_configs (config_key,value_json,updated_at) VALUES (?,?,UTC_TIMESTAMP())
           ON DUPLICATE KEY UPDATE value_json=VALUES(value_json),updated_at=VALUES(updated_at)""",
        (SEED_COMPLETED_KEY, "1"),
    )


def rental_summary(db, today):
    month = today.replace(day=1)
    occupancy = db.execute(
        """SELECT COUNT(*) AS managed_units,
                  COALESCE(SUM(EXISTS (
                      SELECT 1 FROM leases l
                      WHERE l.tenant_id=u.tenant_id AND l.unit_id=u.id
                        AND l.status IN ('OCCUPIED', 'TERMINATION_PENDING', 'ENDED')
                        AND l.actual_move_in_date <= ?
                        AND (l.actual_move_out_date IS NULL OR l.actual_move_out_date > ?)
                  )), 0) AS occupied_units
           FROM units u
           WHERE u.tenant_id=? AND EXISTS (
               SELECT 1 FROM management_contract_units cu
               JOIN management_contracts mc ON mc.tenant_id=cu.tenant_id AND mc.id=cu.management_contract_id
               WHERE cu.tenant_id=u.tenant_id AND cu.unit_id=u.id
                 AND cu.valid_from <= ? AND (cu.valid_to IS NULL OR cu.valid_to >= ?)
                 AND mc.start_date <= ? AND (mc.end_date IS NULL OR mc.end_date >= ?)
                 AND mc.status IN ('ACTIVE','ENDED')
           )""",
        (today, today, TENANT_ID, today, today, today, today),
    ).fetchone()
    charges = db.execute(
        """SELECT
               COALESCE(SUM(total.amount),0) AS billed_amount,
               COALESCE(SUM(total.allocated),0) AS allocated_amount,
               COALESCE(SUM(total.amount - total.allocated),0) AS outstanding_amount
           FROM (
               SELECT c.id, c.amount, COALESCE(SUM(
                   CASE WHEN a.reversal_of_id IS NULL THEN a.amount ELSE -ABS(a.amount) END
               ), 0) AS allocated
               FROM rent_charges c
               LEFT JOIN payment_allocations a ON a.tenant_id=c.tenant_id AND a.charge_id=c.id
                   AND a.allocation_date <= ?
               WHERE c.tenant_id=? AND c.service_month=? AND c.status <> 'CANCELLED'
               GROUP BY c.id, c.amount
           ) total""",
        (today, TENANT_ID, month),
    ).fetchone()
    counts = db.execute(
        """SELECT
            (SELECT COUNT(*) FROM buildings WHERE tenant_id=?) AS building_count,
            (SELECT COUNT(*) FROM units WHERE tenant_id=?) AS unit_count,
            (SELECT COUNT(*) FROM payments WHERE tenant_id=? AND received_date <= ?
                AND status IN ('UNALLOCATED', 'PARTIALLY_ALLOCATED')) AS unallocated_payment_count,
            (SELECT COUNT(*) FROM complaints WHERE tenant_id=? AND urgency='URGENT'
                AND status IN ('OPEN', 'IN_PROGRESS')) AS urgent_complaint_count,
            (SELECT COUNT(*) FROM owner_settlements WHERE tenant_id=? AND status='SUBMITTED')
                AS pending_settlement_approval_count""",
        (TENANT_ID, TENANT_ID, TENANT_ID, today, TENANT_ID, TENANT_ID),
    ).fetchone()
    managed = int(occupancy["managed_units"])
    occupied = int(occupancy["occupied_units"])
    return {
        **counts, **{key: int(value) for key, value in charges.items()},
        "service_month": month, "managed_unit_count": managed, "occupied_unit_count": occupied,
        "occupancy_rate": occupied / managed if managed else 0,
    }


router = APIRouter(prefix="/api/rental")


def register_rental_routes(app, connect, require_actor, audit):
    def require_staff(actor=Depends(require_actor)):
        if actor.account_role not in {
            "executive", "administrator", "hq_staff", "store_manager", "advisor", "finance",
        }:
            raise HTTPException(403, "賃貸管理業務へのアクセス権限がありません")
        return actor

    @router.get("/summary", dependencies=[Depends(require_staff)])
    def summary():
        with connect() as db:
            return rental_summary(db, datetime.now(JST).date())

    snapshot_fields = (
        "plan_code", "plan_version", "rate", "calculation_basis", "tax_inclusive",
        "tax_rate", "vacancy_exempt", "rounding_rule", "minimum_fee", "included_charge_types",
    )
    json_fields = {"included_charge_types", "fee_plan_snapshot", "charge_rule_snapshot", "beneficiary_snapshot"}
    boolean_fields = {"tax_inclusive", "vacancy_exempt", "refundable", "recurring", "settlement_eligible"}
    occupancy_states = ("VACANT", "APPLYING", "CONTRACTING", "OCCUPIED", "TERMINATION_PENDING")
    choices = {
        "party_type": ("individual", "company"),
        "calculation_basis": ("CASH_COLLECTED",),
        "rounding_rule": ("FLOOR",),
        "acquisition_channel": ("OWN_SALE", "OTHER_PURCHASE", "INHERITANCE", "MANAGEMENT_TRANSFER", "OTHER"),
        "deposit_custodian": ("COMPANY", "OWNER", "OTHER"),
        "proration_rule": ("ACTUAL_DAYS_FLOOR",),
        "screening_result": ("PENDING", "APPROVED", "REJECTED"),
    }
    choices["cost_bearer"] = ("OWNER", "COMPANY", "TENANT")
    choices["payment_source"] = ("TENANT", "GUARANTOR_COMPANY", "OTHER")
    for field in ("external_signature_status", "external_procedure_status"):
        choices[field] = ("NOT_STARTED_SAMPLE", "IN_PROGRESS_SAMPLE", "RECORDED_SAMPLE")

    # Editable fields are explicit. Column metadata keeps validation within the existing schema bounds.
    editable = {
        "parties": "party_type display_name name_kana postal_code address phone email contact_person remittance_destination_ref notes",
        "buildings": "building_code building_name postal_code address building_type structure_type construction_month floor_count management_start_date status notes",
        "units": "building_id unit_number owner_party_id floor_number floor_area layout_type advertised_rent advertised_common_fee notes",
        "fee_plans": "plan_code plan_name rate calculation_basis included_charge_types tax_inclusive tax_rate vacancy_exempt rounding_rule minimum_fee effective_from effective_to",
        "management_contracts": "contract_code owner_party_id principal_party_id payee_party_id acquisition_channel accepted_date acquired_date start_date end_date previous_manager_name assigned_user_id remittance_day deposit_custodian notes",
        "management_contract_units": "unit_id valid_from valid_to",
        "applications": "application_code unit_id applicant_party_id application_date application_channel desired_move_in_date proposed_rent proposed_common_fee external_procedure_status external_reference assigned_user_id notes",
        "leases": "lease_code unit_id tenant_party_id guarantor_party_id contract_type start_date scheduled_end_date rent_amount common_fee_amount deposit_amount key_money_amount payment_due_day proration_rule external_signature_status",
    }
    columns = {
        table: {match[1]: (match[2], match[3], match[4], bool(match[5]))
                for match in re.finditer(
                    r"(\w+) (BIGINT|INT|TINYINT|DATETIME|DATE|VARCHAR|TEXT|DECIMAL|BOOLEAN|JSON)"
                    r"(?:\((\d+)(?:,(\d+))?\))?( NOT NULL)?(?=,|\s*$)", TABLE_DEFINITIONS[table], re.M)}
        for table in (*editable, "rent_charges", "payments", "payment_allocations",
                      "work_orders", "complaints", "inspections")
    }
    columns["leases"]["cancellation_reason"] = columns["leases"]["termination_reason"]
    columns["reasons"] = {"reason": ("TEXT", None, None, True)}
    columns["deposit_event"] = {
        "amount": columns["payments"]["amount"],
        "received_date": columns["payments"]["received_date"],
        "refunded_date": columns["payments"]["received_date"],
        "payer_name": columns["payments"]["payer_name"],
        **columns["reasons"],
    }
    amount_fields = {
        "advertised_rent", "advertised_common_fee", "minimum_fee", "proposed_rent",
        "proposed_common_fee", "rent_amount", "common_fee_amount", "deposit_amount", "key_money_amount",
        "estimated_amount", "approved_amount", "actual_amount",
    }
    defaults = {
        "buildings": {"status": "ACTIVE"},
        "fee_plans": {"calculation_basis": "CASH_COLLECTED", "rounding_rule": "FLOOR"},
        "applications": {"external_procedure_status": "NOT_STARTED_SAMPLE"},
        "leases": {"proration_rule": "ACTUAL_DAYS_FLOOR", "external_signature_status": "NOT_STARTED_SAMPLE"},
    }

    def invalid(message):
        raise HTTPException(422, message)

    def conflict(message):
        raise HTTPException(409, message)

    def fields(table, payload, allowed, *, create=False):
        unknown = payload.keys() - set(allowed)
        if unknown:
            invalid(f"指定・変更できない項目です（{', '.join(sorted(unknown))}）")
        values = {}
        for key in allowed:
            kind, precision, scale, required = columns[table][key]
            if key not in payload:
                if create and required:
                    invalid(f"必須項目を入力してください（{key}）")
                continue
            value = payload[key]
            if value is None and not required:
                values[key] = None
                continue
            valid = True
            if kind in {"BIGINT", "INT", "TINYINT"}:
                bits = {"BIGINT": 64, "INT": 32, "TINYINT": 8}[kind]
                valid = type(value) is int and -(2 ** (bits - 1)) <= value < 2 ** (bits - 1)
                if valid and (key.endswith("_id") or key in amount_fields):
                    valid = value >= (1 if key.endswith("_id") else 0)
                if valid and key in {"payment_due_day", "remittance_day"}:
                    valid = 1 <= value <= 31
                if valid and key in {"plan_version", "floor_count"}:
                    valid = value >= 1
            elif kind in {"VARCHAR", "TEXT"}:
                valid = isinstance(value, str) and len(value) <= int(precision or 16000)
                if valid:
                    value = value.strip()
                    valid = bool(value) or not required
            elif kind == "BOOLEAN":
                valid = type(value) is bool
            elif kind == "DATE":
                try:
                    valid = isinstance(value, str) and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value))
                    if valid:
                        value = date.fromisoformat(value)
                        valid = value.year >= 1000
                except ValueError:
                    valid = False
            elif kind == "DATETIME":
                try:
                    valid = isinstance(value, str) and bool(re.fullmatch(
                        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:\d{2})?", value,
                    ))
                    if valid:
                        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
                        value = value.replace(tzinfo=value.tzinfo or JST).astimezone(timezone.utc).replace(tzinfo=None)
                        valid = value.year >= 1000
                except (ValueError, OverflowError):
                    valid = False
            elif kind == "DECIMAL":
                try:
                    value = Decimal(str(value))
                    valid = (value.is_finite() and 0 <= value < 10 ** (int(precision) - int(scale))
                             and value == round(value, int(scale))
                             and (key == "floor_area" or value <= 1))
                except (InvalidOperation, ValueError, OverflowError):
                    valid = False
            elif kind == "JSON":
                valid = (isinstance(value, list) and 0 < len(value) <= 100
                         and all(isinstance(code, str) and len(code) <= 40 for code in value)
                         and len(value) == len(set(value)))
                if valid:
                    value = json.dumps(value)
            if not valid or (key in choices and value not in choices[key]):
                if key == "calculation_basis":
                    invalid("計算基準には実収納基準（CASH_COLLECTED）を指定してください")
                invalid(f"入力値が正しくありません（{key}）")
            if table == "buildings" and key == "status" and value not in {"ACTIVE", "INACTIVE"}:
                invalid("建物の状態が正しくありません")
            values[key] = value
        return values

    def decode(row):
        for key in row.keys() & json_fields:
            if isinstance(row[key], (str, bytes)):
                row[key] = json.loads(row[key])
        for key in row.keys() & boolean_fields:
            row[key] = bool(row[key])
        return row

    def get(db, table, row_id, *, lock=False):
        suffix = " FOR UPDATE" if lock else ""
        if table == "users":
            # Platform identities are global. Only active staff can be assigned rental work.
            row = db.execute(
                "SELECT id FROM users WHERE id=? AND account_status='ACTIVE' AND role IN "
                "('executive','administrator','hq_staff','store_manager','advisor','finance')",
                (row_id,),
            ).fetchone()
        else:
            row = db.execute(
                f"SELECT * FROM {table} WHERE tenant_id=? AND id=?{suffix}", (TENANT_ID, row_id),
            ).fetchone()
        if row is None:
            raise HTTPException(404, "指定されたデータが見つかりません")
        return row

    def validate_refs(db, table, values):
        for key, target in RELATIONSHIPS.get(table, {}).items():
            if values.get(key) is not None:
                get(db, target, values[key])

    def require_active_parties(db, table, values):
        ids = {values[key] for key, target in RELATIONSHIPS[table].items()
               if target == "parties" and values.get(key) is not None}
        for party_id in sorted(ids):
            if get(db, "parties", party_id, lock=True)["status"] != "ACTIVE":
                invalid("有効な関係者を指定してください")

    def check_party_inactivation(db, party_id):
        references = (
            ("management_contracts", "status='ACTIVE'",
             ("owner_party_id", "principal_party_id", "payee_party_id"), "有効な管理契約"),
            ("leases", "status NOT IN ('ENDED','CANCELLED')", ("tenant_party_id", "guarantor_party_id"), "未終了の賃貸借契約"),
            ("applications", "status NOT IN ('CONTRACTED','REJECTED','WITHDRAWN')", ("applicant_party_id",), "未完了の入居申込"),
        )
        for table, status, columns, label in references:
            parties = " OR ".join(f"{column}=?" for column in columns)
            if db.execute(f"SELECT 1 FROM {table} WHERE tenant_id=? AND {status} AND ({parties}) LIMIT 1",
                          (TENANT_ID, *([party_id] * len(columns)))).fetchone():
                invalid(f"{label}に関連する関係者は無効化できません")

    def insert(db, actor, table, values):
        values = dict(values, tenant_id=TENANT_ID, created_by=actor.user_id, updated_by=actor.user_id)
        placeholders = ", ".join("?" for _ in values)
        return db.execute(
            f"INSERT INTO {table} ({', '.join(values)}) VALUES ({placeholders})", tuple(values.values()),
        ).lastrowid

    def update(db, actor, table, row, values):
        if not values:
            return
        assignments = ", ".join(f"{key}=?" for key in values)
        result = db.execute(
            f"""UPDATE {table} SET {assignments}, updated_by=?, updated_at=UTC_TIMESTAMP(6),
                version=version+1 WHERE tenant_id=? AND id=? AND version=?""",
            (*values.values(), actor.user_id, TENANT_ID, row["id"], row["version"]),
        )
        if result.rowcount != 1:
            conflict("他の操作で更新されました。最新のデータを読み込んでください")

    def check_version(payload, row):
        version = payload.pop("version", None)
        if type(version) is not int or version < 1:
            invalid("更新には version が必要です")
        if version != row["version"]:
            conflict("他の操作で更新されました。最新のデータを読み込んでください")

    def ordered_dates(values, first, last):
        if values.get(first) is not None and values.get(last) is not None and values[first] > values[last]:
            invalid(f"終了日は開始日以降にしてください（{first}, {last}）")

    def overlaps(start, end, other_start, other_end):
        return (end is None or other_start <= end) and (other_end is None or start <= other_end)

    def unit_locks(db, ids):
        for unit_id in sorted(set(ids)):
            get(db, "units", unit_id, lock=True)

    def assignments(db, contract_id):
        return db.execute(
            """SELECT cu.*, u.unit_number, u.building_id, b.building_name
               FROM management_contract_units cu
               JOIN units u ON u.tenant_id=cu.tenant_id AND u.id=cu.unit_id
               JOIN buildings b ON b.tenant_id=u.tenant_id AND b.id=u.building_id
               WHERE cu.tenant_id=? AND cu.management_contract_id=? ORDER BY cu.valid_from, cu.id""",
            (TENANT_ID, contract_id),
        ).fetchall()

    def assignment_has_period(row):
        # A removed assignment that never took effect has an empty period.
        return row.get("valid_to") is None or row["valid_from"] <= row["valid_to"]

    def check_assignments(db, contract, rows):
        checked = {}
        for row in rows:
            if not assignment_has_period(row):
                continue
            start, end = row["valid_from"], row.get("valid_to")
            if start < contract["start_date"] or (
                contract.get("end_date") and (start > contract["end_date"] or (end and end > contract["end_date"]))
            ):
                invalid("部屋の割当期間は管理契約期間内にしてください")
            unit_id = row["unit_id"]
            if unit_id not in checked:
                existing = db.execute(
                    """SELECT cu.valid_from, cu.valid_to, mc.end_date FROM management_contract_units cu
                       JOIN management_contracts mc ON mc.tenant_id=cu.tenant_id AND mc.id=cu.management_contract_id
                       WHERE cu.tenant_id=? AND cu.unit_id=? AND mc.id<>?
                         AND mc.status IN ('ACTIVE','ENDED')""",
                    (TENANT_ID, unit_id, contract.get("id", 0)),
                ).fetchall()
                checked[unit_id] = []
                for item in existing:
                    # Ending a contract caps its effective periods without rewriting closed rows.
                    ends = [end for end in (item["valid_to"], item["end_date"]) if end is not None]
                    first, last = item["valid_from"], min(ends, default=None)
                    if last is None or first <= last:
                        checked[unit_id].append((first, last))
            effective_end = end or contract.get("end_date")
            if any(overlaps(start, effective_end, old_start, old_end) for old_start, old_end in checked[unit_id]):
                conflict("同じ部屋の管理契約の有効期間が重複しています")
            checked[unit_id].append((start, effective_end))

    def assignment_key(row):
        return row["unit_id"], row["valid_from"]

    def close_assignments(rows, cutoff, *, draft=False):
        closed = []
        for row in rows:
            if not draft and row["valid_to"] is not None:
                closed.append(row)
                continue
            last = min(cutoff, row.get("valid_to") or cutoff)
            if draft:
                last = min(last, row["valid_from"] - timedelta(days=1))
            closed.append(dict(row, valid_to=last))
        return closed

    def save_assignments(db, actor, row_id, rows, previous, *, draft=False):
        old = {assignment_key(row): row for row in previous}
        for row in rows:
            values = {key: row.get(key) for key in ("unit_id", "valid_from", "valid_to")}
            prior = old.get(assignment_key(row))
            if prior is None:
                assignment_id = insert(db, actor, "management_contract_units", dict(values, management_contract_id=row_id))
                audit(db, actor.user_id, "rental.assignment.created", "management_contract_unit", assignment_id, f"管理契約 {row_id}")
            elif prior["valid_to"] != values["valid_to"]:
                if not draft and prior["valid_to"] is not None:
                    conflict("終了済みの部屋割当は変更できません。新しい開始日で割り当ててください")
                update(db, actor, "management_contract_units", prior, {"valid_to": values["valid_to"]})
                audit(db, actor.user_id, "rental.assignment.updated", "management_contract_unit", prior["id"], f"管理契約 {row_id}")

    def refresh_management(db, actor, unit_ids, today):
        for unit_id in sorted(set(unit_ids)):
            unit = get(db, "units", unit_id)
            active = db.execute(
                """SELECT 1 FROM management_contract_units cu
                   JOIN management_contracts mc ON mc.tenant_id=cu.tenant_id AND mc.id=cu.management_contract_id
                   WHERE cu.tenant_id=? AND cu.unit_id=? AND mc.status IN ('ACTIVE','ENDED')
                     AND cu.valid_from<=? AND (cu.valid_to IS NULL OR cu.valid_to>=?)
                     AND mc.start_date<=? AND (mc.end_date IS NULL OR mc.end_date>=?) LIMIT 1""",
                (TENANT_ID, unit_id, today, today, today, today),
            ).fetchone()
            status = "MANAGED" if active else "UNMANAGED"
            if unit["management_status"] != status:
                update(db, actor, "units", unit, {"management_status": status})

    def plan_snapshots(db, plan_id, start):
        plan = decode(get(db, "fee_plans", plan_id, lock=True))
        if plan["status"] != "ACTIVE":
            invalid("有効な管理料プランを選んでください")
        if start < plan["effective_from"] or (plan["effective_to"] and start > plan["effective_to"]):
            invalid("管理契約の開始日が管理料プランの適用期間外です")
        snapshot = {key: str(plan[key]) if isinstance(plan[key], Decimal) else plan[key] for key in snapshot_fields}
        rules = db.execute(
            """SELECT id, charge_code, beneficiary_type, tax_category, refundable, recurring, settlement_eligible
               FROM charge_types WHERE tenant_id=? AND status='ACTIVE' ORDER BY id""", (TENANT_ID,),
        ).fetchall()
        charge_rules = {rule.pop("charge_code"): decode(rule) for rule in rules}
        if "BROKERAGE" in charge_rules:
            charge_rules["BROKERAGE"]["settlement_deduction_allowed"] = False
        return {
            "fee_plan_id": plan_id, "fee_plan_version": plan["plan_version"],
            "fee_plan_snapshot": json.dumps(snapshot),
            "charge_rule_snapshot": json.dumps(charge_rules),
        }

    def validate_business(db, table, values):
        if table == "fee_plans":
            ordered_dates(values, "effective_from", "effective_to")
            if "included_charge_types" in values:
                codes = json.loads(values["included_charge_types"])
                existing = db.execute("SELECT charge_code FROM charge_types WHERE tenant_id=?", (TENANT_ID,)).fetchall()
                if not set(codes) <= {row["charge_code"] for row in existing}:
                    invalid("存在しない対象費目が指定されています")
        if table == "management_contracts":
            ordered_dates(values, "start_date", "end_date")
        if table == "leases":
            for first, last in (
                ("start_date", "scheduled_end_date"), ("signed_date", "actual_move_in_date"),
                ("actual_move_in_date", "scheduled_end_date"), ("start_date", "actual_move_out_date"),
                ("actual_move_in_date", "actual_move_out_date"),
                ("actual_move_in_date", "termination_notice_date"),
                ("termination_notice_date", "scheduled_move_out_date"),
                ("termination_notice_date", "actual_move_out_date"),
            ):
                ordered_dates(values, first, last)

    def check_lease_period(db, lease):
        rows = db.execute(
            """SELECT start_date, scheduled_end_date, status, actual_move_in_date, actual_move_out_date
               FROM leases WHERE tenant_id=? AND unit_id=? AND id<>?
                 AND status IN ('SIGNED','OCCUPIED','TERMINATION_PENDING','ENDED')""",
            (TENANT_ID, lease["unit_id"], lease.get("id", 0)),
        ).fetchall()
        for other in rows:
            other_start, other_end = other["start_date"], other["scheduled_end_date"]
            if other["status"] != "SIGNED":
                other_end = other["actual_move_out_date"]
                if other["status"] == "ENDED" or other_end is not None:
                    other_start = other["actual_move_in_date"] or other_start
            if overlaps(lease["start_date"], lease.get("scheduled_end_date"), other_start, other_end):
                conflict("同じ部屋の賃貸借契約期間が重複しています")

    def refresh_occupancy(db, actor, unit_id):
        unit = get(db, "units", unit_id)
        leases = db.execute(
            "SELECT status FROM leases WHERE tenant_id=? AND unit_id=? AND status NOT IN ('ENDED','CANCELLED')",
            (TENANT_ID, unit_id),
        ).fetchall()
        applications = db.execute(
            "SELECT status FROM applications WHERE tenant_id=? AND unit_id=?", (TENANT_ID, unit_id),
        ).fetchall()
        lease_states = {row["status"] for row in leases}
        application_states = {row["status"] for row in applications}
        if "OCCUPIED" in lease_states:
            status = "OCCUPIED"
        elif "TERMINATION_PENDING" in lease_states:
            status = "TERMINATION_PENDING"
        elif lease_states or "APPROVED" in application_states:
            status = "CONTRACTING"
        elif application_states & {"RECEIVED", "SCREENING"}:
            status = "APPLYING"
        else:
            status = "VACANT"
        if unit["occupancy_status"] != status:
            update(db, actor, "units", unit, {"occupancy_status": status})
            audit(db, actor.user_id, "rental.unit.occupancy_updated", "unit", unit_id, status)

    def detail(db, table, row_id):
        row = decode(get(db, table, row_id))
        if table == "buildings":
            counts = db.execute(
                """SELECT occupancy_status, COUNT(*) AS count FROM units
                   WHERE tenant_id=? AND building_id=? GROUP BY occupancy_status""", (TENANT_ID, row_id),
            ).fetchall()
            row["occupancy_counts"] = {state: 0 for state in occupancy_states}
            row["occupancy_counts"].update({item["occupancy_status"]: item["count"] for item in counts})
            row["unit_count"] = sum(row["occupancy_counts"].values())
        if table == "units":
            today = datetime.now(JST).date()
            contract = db.execute(
                """SELECT mc.* FROM management_contract_units cu JOIN management_contracts mc
                   ON mc.tenant_id=cu.tenant_id AND mc.id=cu.management_contract_id
                   WHERE cu.tenant_id=? AND cu.unit_id=? AND mc.status IN ('ACTIVE','ENDED')
                     AND cu.valid_from<=? AND (cu.valid_to IS NULL OR cu.valid_to>=?)
                     AND mc.start_date<=? AND (mc.end_date IS NULL OR mc.end_date>=?)
                   ORDER BY cu.valid_from DESC, mc.id DESC LIMIT 1""",
                (TENANT_ID, row_id, today, today, today, today),
            ).fetchone()
            row["building_name"] = get(db, "buildings", row["building_id"])["building_name"]
            row["current_management_contract"] = decode(contract) if contract else None
            row["management_status"] = "MANAGED" if contract else "UNMANAGED"
            row["current_lease"] = db.execute(
                """SELECT * FROM leases WHERE tenant_id=? AND unit_id=?
                   AND status IN ('SIGNED','OCCUPIED','TERMINATION_PENDING')
                   AND (start_date<=? OR actual_move_in_date<=?)
                   AND (actual_move_out_date IS NULL OR actual_move_out_date>?)
                   AND (status IN ('OCCUPIED','TERMINATION_PENDING') OR scheduled_end_date IS NULL OR scheduled_end_date>=?)
                   ORDER BY status IN ('OCCUPIED','TERMINATION_PENDING') DESC, start_date DESC, id DESC LIMIT 1""",
                (TENANT_ID, row_id, today, today, today, today),
            ).fetchone()
            row["recent_repairs"] = db.execute(
                """SELECT id, work_order_code, received_date, description, status FROM work_orders
                   WHERE tenant_id=? AND unit_id=? ORDER BY received_date DESC, id DESC LIMIT 10""",
                (TENANT_ID, row_id),
            ).fetchall()
        if table == "management_contracts":
            row["units"] = assignments(db, row_id)
        if table == "applications":
            row["lease"] = db.execute(
                "SELECT id, lease_code, status FROM leases WHERE tenant_id=? AND application_id=?",
                (TENANT_ID, row_id),
            ).fetchone()
        return row

    def write(operation):
        try:
            with connect() as db:
                # Unit locks serialize period checks. Reads after taking a lock must see the latest commit.
                db.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
                return operation(db)
        except IntegrityError as error:
            if error.args[0] == 1062:
                conflict("同じコード、部屋番号、または申込の契約が既に登録されています")
            if error.args[0] == 1452:
                invalid("参照先のデータが見つかりません")
            raise
        except OperationalError as error:
            if error.args[0] in {1205, 1213}:
                conflict("同時に変更されています。最新のデータを読み込んでください")
            raise

    def create_record(db, actor, table, payload, *, application=None):
        payload = dict(payload)
        extra = {}
        rows = None
        if table == "parties":
            extra = {"party_code": uuid.uuid4().hex, "status": "ACTIVE"}
        elif table == "units":
            extra = {"management_status": "UNMANAGED", "occupancy_status": "VACANT"}
        elif table == "fee_plans":
            extra = dict(fields(table, {"plan_version": payload.pop("plan_version", 1)}, ("plan_version",)),
                         status="DRAFT")
        elif table == "management_contracts":
            plan = fields(table, {"fee_plan_id": payload.pop("fee_plan_id", None)}, ("fee_plan_id",))
            rows = parse_assignments(payload.pop("units", []))
            cutoff = payload.pop("settlement_cutoff_day", 31)
            if type(cutoff) is not int or cutoff != 31:
                invalid("精算締め日は月末固定です")
            extra = dict(plan, settlement_cutoff_day=31, status="DRAFT")
        elif table == "applications":
            payload.setdefault("assigned_user_id", actor.user_id)
            extra = {"status": "RECEIVED", "screening_result": "PENDING"}
        elif table == "leases":
            extra = {"status": "DRAFT"}
            if application:
                extra["application_id"] = application["id"]

        if table == "management_contracts":
            payload.setdefault("assigned_user_id", actor.user_id)
        values = fields(table, {**defaults.get(table, {}), **payload}, editable[table].split(), create=True)
        values.update(extra)
        validate_refs(db, table, values)
        validate_business(db, table, values)
        if rows is not None:
            unit_locks(db, [item["unit_id"] for item in rows])
            values.update(plan_snapshots(db, values["fee_plan_id"], values["start_date"]))
            check_assignments(db, values, rows)
        if table in {"applications", "leases"}:
            unit_locks(db, [values["unit_id"]])
        if table in {"units", "applications", "leases"}:
            require_active_parties(db, table, values)
        if table == "leases":
            check_lease_period(db, values)
        row_id = insert(db, actor, table, values)
        if table == "leases" and values["deposit_amount"]:
            sync_expected_deposit(db, actor, row_id, values)
        if table == "parties":
            db.execute("UPDATE parties SET party_code=? WHERE tenant_id=? AND id=?",
                       (f"P-{row_id}", TENANT_ID, row_id))
        if rows is not None:
            save_assignments(db, actor, row_id, rows, [])
        if table in {"applications", "leases"}:
            refresh_occupancy(db, actor, values["unit_id"])
        audit(db, actor.user_id, f"rental.{table}.created", table, row_id, "登録")
        return detail(db, table, row_id)

    def parse_assignments(raw):
        if not isinstance(raw, list) or len(raw) > 100 or any(not isinstance(row, dict) for row in raw):
            invalid("部屋割当は100件以内で指定してください")
        rows = [fields("management_contract_units", row, editable["management_contract_units"].split(), create=True)
                for row in raw]
        if len({assignment_key(row) for row in rows}) != len(rows):
            conflict("同じ部屋と開始日の割当が重複しています")
        for row in rows:
            ordered_dates(row, "valid_from", "valid_to")
        return rows

    def edit_record(db, actor, table, row_id, payload):
        if table in {"applications", "leases"}:
            unit_locks(db, [get(db, table, row_id)["unit_id"]])
        row = get(db, table, row_id, lock=True)
        payload = dict(payload)
        check_version(payload, row)
        changed_assignments = table == "management_contracts" and "units" in payload
        rows = parse_assignments(payload.pop("units")) if changed_assignments else None
        allowed = editable[table].split()
        if table == "management_contracts" and row["status"] in {"ENDED", "CANCELLED"}:
            invalid("終了または取消済みの管理契約は変更できません")
        if table == "management_contracts" and row["status"] == "ACTIVE":
            allowed = [key for key in allowed if key not in {"owner_party_id", "principal_party_id", "payee_party_id", "start_date"}]
        if table == "applications":
            allowed = [key for key in allowed if key not in {"unit_id", "applicant_party_id"}]
            if row["status"] in {"CONTRACTED", "REJECTED", "WITHDRAWN"}:
                allowed = ["external_procedure_status", "external_reference", "notes"]
        if table == "leases":
            allowed = [key for key in allowed if key != "unit_id"]
            if row["application_id"] is not None:
                allowed.remove("tenant_party_id")
            if row["status"] != "DRAFT":
                allowed = ["external_signature_status"]
        values = fields(table, payload, allowed)
        if not values and rows is None:
            invalid("更新項目を入力してください")
        merged = row | values
        owner_changed = table == "units" and merged["owner_party_id"] != row["owner_party_id"]
        if owner_changed:
            for related in ("management_contract_units", "applications", "leases", "complaints",
                            "work_orders", "inspections", "settlement_lines"):
                if db.execute(f"SELECT 1 FROM {related} WHERE tenant_id=? AND unit_id=? LIMIT 1",
                              (TENANT_ID, row_id)).fetchone():
                    invalid("業務履歴のある部屋の所有権変更は、旧管理契約の終了と新管理契約の作成で行ってください")
        validate_refs(db, table, values)
        if owner_changed:
            require_active_parties(db, table, values)
        validate_business(db, table, merged)
        affected = []
        today = datetime.now(JST).date()
        if table == "management_contracts":
            previous = assignments(db, row_id)
            affected = [item["unit_id"] for item in [*previous, *(rows or [])]]
            unit_locks(db, affected)
            if rows is None:
                check_assignments(db, merged, previous)
            else:
                keys = {assignment_key(item) for item in rows}
                omitted = [item for item in previous if assignment_key(item) not in keys]
                cutoff = today - timedelta(days=1)
                if row["end_date"]:
                    cutoff = min(cutoff, row["end_date"])
                rows.extend(close_assignments(omitted, cutoff, draft=row["status"] == "DRAFT"))
                check_assignments(db, merged, rows)
                save_assignments(db, actor, row_id, rows, previous, draft=row["status"] == "DRAFT")
                # Assignment-only edits also advance the contract version.
                values.setdefault("end_date", row["end_date"])
        if table == "leases" and row["status"] == "DRAFT":
            require_active_parties(db, table, merged)
            check_lease_period(db, merged)
            if values.keys() & {"deposit_amount", "start_date"}:
                sync_expected_deposit(db, actor, row_id, merged)
        update(db, actor, table, row, values)
        if affected and (rows is not None or "end_date" in values):
            refresh_management(db, actor, affected, today)
        audit(db, actor.user_id, f"rental.{table}.updated", table, row_id, "更新")
        return detail(db, table, row_id)

    transitions = {
        "parties": {"inactivate": (("ACTIVE",), "INACTIVE", ())},
        "fee_plans": {
            "activate": (("DRAFT",), "ACTIVE", ()),
            "retire": (("ACTIVE",), "RETIRED", ()),
        },
        "management_contracts": {
            "activate": (("DRAFT",), "ACTIVE", ()),
            "end": (("ACTIVE",), "ENDED", ("end_date", "termination_reason")),
            "cancel": (("DRAFT",), "CANCELLED", ()),
        },
        "applications": {
            "screen": (("RECEIVED",), "SCREENING", ("notes",)),
            "approve": (("SCREENING",), "APPROVED", ("notes",)),
            "reject": (("SCREENING",), "REJECTED", ("cancellation_reason",)),
            "withdraw": (("RECEIVED", "SCREENING", "APPROVED"), "WITHDRAWN", ("cancellation_reason",)),
        },
        "leases": {
            "sign": (("DRAFT",), "SIGNED", ("signed_date",)),
            "cancel": (("DRAFT", "SIGNED"), "CANCELLED", ("cancellation_reason",)),
            "move-in": (("SIGNED",), "OCCUPIED", ("actual_move_in_date",)),
            "notice": (("OCCUPIED",), "TERMINATION_PENDING",
                       ("termination_notice_date", "scheduled_move_out_date", "termination_reason")),
            "move-out": (("TERMINATION_PENDING",), "ENDED", ("actual_move_out_date",)),
        },
    }

    def lease_transition(db, row, action, values, today):
        if action == "sign":
            values.setdefault("signed_date", today)
        elif action == "move-in":
            values.setdefault("actual_move_in_date", today)
        elif action == "notice":
            values.setdefault("termination_notice_date", today)
            if not values.get("scheduled_move_out_date"):
                invalid("退去予定日を入力してください")
        elif action == "move-out":
            values.setdefault("actual_move_out_date", today)
        merged = row | values
        for key in ("signed_date", "actual_move_in_date", "termination_notice_date", "actual_move_out_date"):
            if key in values and (values[key] is None or values[key] > today):
                invalid(f"実績日は本日以前の日付を指定してください（{key}）")
        validate_business(db, "leases", merged)
        if action == "sign":
            require_active_parties(db, "leases", row)
            check_lease_period(db, merged)
        if action == "cancel":
            if not values.get("cancellation_reason"):
                invalid("賃貸借契約の取消理由を入力してください")
            values["termination_reason"] = values.pop("cancellation_reason")
        if action == "move-in":
            occupied = db.execute(
                """SELECT id FROM leases WHERE tenant_id=? AND unit_id=? AND id<>?
                   AND status IN ('OCCUPIED','TERMINATION_PENDING') LIMIT 1""",
                (TENANT_ID, row["unit_id"], row["id"]),
            ).fetchone()
            if occupied:
                conflict("同じ部屋に退去前の賃貸借契約があります")

    def transition_record(db, actor, table, row_id, action, payload):
        if table in {"applications", "leases"}:
            unit_locks(db, [get(db, table, row_id)["unit_id"]])
        row = get(db, table, row_id, lock=True)
        payload = dict(payload)
        check_version(payload, row)
        sources, target, allowed = transitions[table][action]
        if row["status"] not in sources:
            invalid(f"現在の状態（{row['status']}）から指定の操作はできません（{target}）")
        values = fields(table, payload, allowed)
        today = datetime.now(JST).date()
        if table == "parties":
            check_party_inactivation(db, row_id)
        if table == "management_contracts":
            rows = assignments(db, row_id)
            affected = [item["unit_id"] for item in rows]
            unit_locks(db, affected)
            if action == "activate":
                if not any(assignment_has_period(item) for item in rows):
                    invalid("有効化には部屋の割当が必要です")
                check_assignments(db, row, rows)
                require_active_parties(db, table, row)
                values.update(plan_snapshots(db, row["fee_plan_id"], row["start_date"]))
                for unit_id in sorted({item["unit_id"] for item in rows if assignment_has_period(item)}):
                    unit = get(db, "units", unit_id)
                    if unit["owner_party_id"] != row["owner_party_id"]:
                        update(db, actor, "units", unit, {"owner_party_id": row["owner_party_id"]})
                        audit(db, actor.user_id, "rental.unit.owner_updated", "unit", unit_id,
                              f"管理契約 {row_id}: {unit['owner_party_id']} → {row['owner_party_id']}")
            elif action == "end":
                if not values.get("termination_reason"):
                    invalid("契約の終了理由を入力してください")
                values["end_date"] = values.get("end_date") or row["end_date"] or today
                ordered_dates(row | values, "start_date", "end_date")
                save_assignments(db, actor, row_id, close_assignments(rows, values["end_date"]), rows)
        if table == "applications":
            if action in {"reject", "withdraw"} and not values.get("cancellation_reason"):
                invalid("却下または取下げの理由を入力してください")
            if action in {"approve", "reject"}:
                values["screening_result"] = target
        if table == "leases":
            lease_transition(db, row, action, values, today)
        update(db, actor, table, row, dict(values, status=target))
        if table == "management_contracts" and action in {"activate", "end"}:
            refresh_management(db, actor, affected, today)
        if table in {"applications", "leases"}:
            refresh_occupancy(db, actor, row["unit_id"])
        audit(db, actor.user_id, f"rental.{table}.{action}", table, row_id, f"{row['status']} → {target}")
        return detail(db, table, row_id)

    def generate_lease(db, actor, row_id, payload):
        unit_locks(db, [get(db, "applications", row_id)["unit_id"]])
        row = get(db, "applications", row_id, lock=True)
        if db.execute("SELECT id FROM leases WHERE tenant_id=? AND application_id=?", (TENANT_ID, row_id)).fetchone():
            conflict("この申込から賃貸借契約は既に作成されています")
        payload = dict(payload)
        check_version(payload, row)
        if row["status"] != "APPROVED":
            invalid("承認された申込からのみ賃貸借契約を作成できます")
        copied = {
            "unit_id": row["unit_id"], "tenant_party_id": row["applicant_party_id"],
            "start_date": row["desired_move_in_date"].isoformat(),
            "rent_amount": row["proposed_rent"], "common_fee_amount": row["proposed_common_fee"],
        }
        if payload.keys() & copied.keys():
            invalid("部屋・申込者・入居希望日・申込金額は申込から引き継ぎます")
        lease = create_record(db, actor, "leases", copied | payload, application=row)
        update(db, actor, "applications", row, {"status": "CONTRACTED"})
        audit(db, actor.user_id, "rental.applications.contracted", "applications", row_id, f"賃貸借契約 {lease['id']}")
        return lease

    def list_records(table, limit, offset, status, owner_only, building_id, occupancy_status):
        filters = ["t.tenant_id=?"]
        args = [TENANT_ID]
        if status is not None:
            if table == "units":
                invalid("部屋は occupancy_status で絞り込んでください")
            filters.append("t.status=?")
            args.append(status)
        if table == "parties" and owner_only:
            filters.append(
                "EXISTS (SELECT 1 FROM management_contracts mc WHERE mc.tenant_id=t.tenant_id AND mc.owner_party_id=t.id)"
            )
        select, join = "t.*", ""
        select_args = ()
        if table == "units":
            select += """, b.building_name, EXISTS (
                SELECT 1 FROM management_contract_units cu JOIN management_contracts mc
                  ON mc.tenant_id=cu.tenant_id AND mc.id=cu.management_contract_id
                WHERE cu.tenant_id=t.tenant_id AND cu.unit_id=t.id AND mc.status IN ('ACTIVE','ENDED')
                  AND cu.valid_from<=? AND (cu.valid_to IS NULL OR cu.valid_to>=?)
                  AND mc.start_date<=? AND (mc.end_date IS NULL OR mc.end_date>=?)
            ) AS currently_managed"""
            select_args = (datetime.now(JST).date(),) * 4
            join = "JOIN buildings b ON b.tenant_id=t.tenant_id AND b.id=t.building_id"
            for column, value in (("building_id", building_id), ("occupancy_status", occupancy_status)):
                if value is not None:
                    filters.append(f"t.{column}=?")
                    args.append(value)
        if table in {"applications", "leases"}:
            party = "applicant_party_id" if table == "applications" else "tenant_party_id"
            select += ", p.display_name, u.unit_number, b.building_name"
            join = f"""JOIN parties p ON p.tenant_id=t.tenant_id AND p.id=t.{party}
                       JOIN units u ON u.tenant_id=t.tenant_id AND u.id=t.unit_id
                       JOIN buildings b ON b.tenant_id=u.tenant_id AND b.id=u.building_id"""
        if table == "management_contracts":
            select += ", p.display_name"
            join = "JOIN parties p ON p.tenant_id=t.tenant_id AND p.id=t.owner_party_id"
        with connect() as db:
            if table == "units" and building_id is not None:
                get(db, "buildings", building_id)
            rows = db.execute(
                f"SELECT {select} FROM {table} t {join} WHERE {' AND '.join(filters)} ORDER BY t.id LIMIT ? OFFSET ?",
                (*select_args, *args, limit, offset),
            ).fetchall()
            if table == "units":
                for row in rows:
                    row["management_status"] = "MANAGED" if row.pop("currently_managed") else "UNMANAGED"
            return [decode(row) for row in rows]

    @router.get("/staff", dependencies=[Depends(require_staff)])
    def staff(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
        with connect() as db:
            return db.execute(
                """SELECT id, COALESCE(display_name,name) AS display_name FROM users
                   WHERE account_status='ACTIVE' AND role IN
                   ('executive','administrator','hq_staff','store_manager','advisor','finance')
                   ORDER BY id LIMIT ? OFFSET ?""", (limit, offset),
            ).fetchall()

    @router.get("/charge-types", dependencies=[Depends(require_staff)])
    def charge_types(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
        with connect() as db:
            return db.execute(
                """SELECT id, charge_code, charge_name FROM charge_types
                   WHERE tenant_id=? AND status='ACTIVE' ORDER BY id LIMIT ? OFFSET ?""", (TENANT_ID, limit, offset),
            ).fetchall()

    def register_resource(table):
        dependencies = [Depends(require_staff)]
        path = "/" + table.replace("_", "-")

        @router.get(path, dependencies=dependencies, name=f"rental_{table}_list")
        def listing(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                    status: str = None, owner_only: bool = False, building_id: int = None,
                    occupancy_status: str = None):
            return list_records(table, limit, offset, status, owner_only, building_id, occupancy_status)

        @router.get(f"{path}/{{row_id}}", dependencies=dependencies, name=f"rental_{table}_detail")
        def read(row_id: int):
            with connect() as db:
                return detail(db, table, row_id)

        @router.post(path, status_code=201, name=f"rental_{table}_create")
        def create(payload: dict, actor=Depends(require_staff)):
            return write(lambda db: create_record(db, actor, table, payload))

        @router.put(f"{path}/{{row_id}}", name=f"rental_{table}_update")
        def edit(row_id: int, payload: dict, actor=Depends(require_staff)):
            return write(lambda db: edit_record(db, actor, table, row_id, payload))

        def register_transition(action):
            @router.post(f"{path}/{{row_id}}/{action}", name=f"rental_{table}_{action}")
            def change(row_id: int, payload: dict, actor=Depends(require_staff)):
                return write(lambda db: transition_record(db, actor, table, row_id, action, payload))

        for action in transitions.get(table, {}):
            register_transition(action)

    for table in editable:
        if table != "management_contract_units":
            register_resource(table)

    @router.post("/applications/{row_id}/create-lease", status_code=201)
    def create_lease(row_id: int, payload: dict, actor=Depends(require_staff)):
        return write(lambda db: generate_lease(db, actor, row_id, payload))

    def money_values(table, payload, allowed, *, required=()):
        values = fields(table, payload, allowed.split())
        for key in required:
            if values.get(key) is None or values[key] == "":
                invalid(f"必須項目を入力してください（{key}）")
        if "amount" in values and (values["amount"] is None or values["amount"] <= 0):
            invalid("金額は正の整数円を入力してください")
        return values

    def money_version(payload, row, key="version"):
        # Existing records always use update()'s version check. A client can
        # also supply its last read version to check for intervening changes.
        if key in payload:
            check_version({"version": payload.pop(key)}, row)

    def allocation_versions(payload, *keys):
        versions = {key: payload.get(key) for key in keys}
        for key, version in versions.items():
            if type(version) is not int or version < 1:
                invalid(f"正の整数の version を指定してください（{key}）")
        return versions

    def month_value(value):
        if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}(-01)?", value):
            try:
                month = date.fromisoformat(value[:7] + "-01")
                if month.year >= 1000:
                    return month
            except ValueError:
                pass
        invalid("所属月は YYYY-MM または月初日で指定してください")

    def month_end(month):
        return month.replace(day=monthrange(month.year, month.month)[1])

    def today_jst():
        return datetime.now(JST).date()

    def require_open_period(db, day):
        period = day.strftime("%Y-%m")
        # Use the same period key as close preparation and lock existing snapshots
        # before testing their state, including a snapshot pending approval.
        db.execute(
            "INSERT INTO month_close_period_locks(period) VALUES (?) ON DUPLICATE KEY UPDATE period=period",
            (period,),
        )
        closes = db.execute("SELECT status FROM month_closes WHERE period=? FOR UPDATE", (period,)).fetchall()
        if any(row["status"] in {"CLOSED", "REOPEN_REQUESTED"} for row in closes):
            raise HTTPException(423, f"{period} は月次締め済みです")

    def management_for_period(db, unit_id, start, end, *, full_coverage=False):
        # The caller holds the unit lock, which also guards management assignments.
        rows = db.execute(
            """SELECT mc.*, cu.valid_from AS assigned_from, cu.valid_to AS assigned_to
               FROM management_contract_units cu JOIN management_contracts mc
                 ON mc.tenant_id=cu.tenant_id AND mc.id=cu.management_contract_id
               WHERE cu.tenant_id=? AND cu.unit_id=? AND mc.status IN ('ACTIVE','ENDED')
                 AND cu.valid_from<=? AND (cu.valid_to IS NULL OR cu.valid_to>=?)
                 AND mc.start_date<=? AND (mc.end_date IS NULL OR mc.end_date>=?)""",
            (TENANT_ID, unit_id, end, start, end, start),
        ).fetchall()
        eligible = []
        for row in rows:
            first = max(start, row["start_date"], row["assigned_from"])
            last = min(end, row["end_date"] or end, row["assigned_to"] or end)
            if first <= last:
                eligible.append((first, row["id"], last, row))
        if not eligible:
            return None
        eligible.sort(key=lambda item: item[:2])
        if full_coverage:
            if len({row_id for _, row_id, _, _ in eligible}) > 1:
                return "MANAGEMENT_CHANGED_MIDMONTH"
            covered_until = start.toordinal() - 1
            for first, _, last, _ in eligible:
                if first.toordinal() > covered_until + 1:
                    break
                covered_until = max(covered_until, last.toordinal())
            if covered_until < end.toordinal():
                return "PARTIAL_MANAGEMENT_COVERAGE"
        return decode(eligible[0][3])

    def sync_expected_deposit(db, actor, lease_id, lease):
        existing = db.execute(
            "SELECT * FROM deposits WHERE tenant_id=? AND lease_id=? ORDER BY id FOR UPDATE",
            (TENANT_ID, lease_id),
        ).fetchall()
        amount = lease["deposit_amount"]
        if existing and any(row["received_amount"] or row["refunded_amount"] or row["transferred_amount"]
                            for row in existing):
            if sum(row["agreed_amount"] for row in existing) != amount:
                invalid("受領済みの敷金額は変更できません")
            return
        if not amount and not existing:
            return
        contract = None
        if amount:
            start = lease["start_date"]
            contract = management_for_period(db, lease["unit_id"], start, start)
            if contract is None:
                invalid("敷金を登録するには契約開始日に有効な管理契約が必要です")
        values = {
            "agreed_amount": amount, "status": "EXPECTED" if amount else "CLOSED",
        }
        if contract:
            values.update(management_contract_id=contract["id"], custodian_type=contract["deposit_custodian"])
        if existing:
            row = existing[0]
            if any(row[key] != value for key, value in values.items()):
                update(db, actor, "deposits", row, values)
                audit(db, actor.user_id, "rental.deposits.expected_updated", "deposits", row["id"], f"約定額 {amount} 円")
        else:
            deposit_id = insert(db, actor, "deposits", dict(
                values, lease_id=lease_id, received_amount=0, refunded_amount=0, transferred_amount=0,
            ))
            audit(db, actor.user_id, "rental.deposits.expected", "deposits", deposit_id, f"約定額 {amount} 円")

    def charge_values(lease, contract, charge_type, month, amount, source, first=None, last=None, due=None):
        code = charge_type["charge_code"]
        rule = contract["charge_rule_snapshot"].get(code)
        if not rule or rule["id"] != charge_type["id"] or rule["beneficiary_type"] not in {"OWNER", "COMPANY"}:
            return None
        snapshot = dict(rule)
        if snapshot["beneficiary_type"] == "OWNER":
            snapshot["owner_party_id"] = contract["owner_party_id"]
        tax_amount = 0
        if rule["tax_category"] == "TAXABLE":
            configured_rate = rule.get("tax_rate")
            rate = Decimal("0.10") if configured_rate is None else Decimal(str(configured_rate))
            # Exact arithmetic preserves floor rounding even for BIGINT amounts.
            numerator, denominator = rate.as_integer_ratio()
            tax_amount = amount * numerator // (denominator + numerator)
            snapshot["tax_rate"] = str(rate)
        key = uuid.uuid4().hex
        return dict(
            charge_code=f"C-{key}", lease_id=lease["id"], management_contract_id=contract["id"],
            charge_type_id=charge_type["id"], service_month=month, service_from=first, service_to=last,
            due_date=due or month.replace(day=min(lease["payment_due_day"], month_end(month).day)),
            amount=amount, tax_category=rule["tax_category"], tax_amount=tax_amount,
            beneficiary_snapshot=json.dumps(snapshot), source_type=source,
            source_reference=key, status="UNPAID",
        )

    def lease_service_period(lease, month, last_day):
        first = max(month, lease["actual_move_in_date"] or lease["start_date"])
        last = min(last_day, lease["actual_move_out_date"] or lease["scheduled_move_out_date"]
                   or lease["scheduled_end_date"] or last_day)
        return first, last

    @router.post("/charges/generate")
    def generate_charges(payload: dict, actor=Depends(require_staff)):
        if payload.keys() != {"service_month"}:
            invalid("所属月を指定してください（service_month）")
        month = month_value(payload["service_month"])
        last_day = month_end(month)

        def operation(db):
            require_open_period(db, month)
            leases = db.execute(
                """SELECT id, unit_id FROM leases WHERE tenant_id=?
                   AND status IN ('SIGNED','OCCUPIED','TERMINATION_PENDING','ENDED')
                   AND COALESCE(actual_move_in_date, start_date)<=?
                   AND COALESCE(actual_move_out_date, scheduled_move_out_date, scheduled_end_date, ?)>=?
                   ORDER BY unit_id, id LIMIT 5001""",
                (TENANT_ID, last_day, last_day, month),
            ).fetchall()
            if len(leases) > 5000:
                invalid("月次生成の対象が上限（5,000契約）を超えています")
            unit_locks(db, [lease["unit_id"] for lease in leases])
            types = db.execute(
                """SELECT id, charge_code FROM charge_types WHERE tenant_id=?
                   AND charge_code IN ('RENT','COMMON_FEE') ORDER BY id""", (TENANT_ID,),
            ).fetchall()
            duplicates = {
                (row["lease_id"], row["charge_type_id"]) for row in db.execute(
                    """SELECT lease_id, charge_type_id FROM rent_charges
                       WHERE tenant_id=? AND service_month=? AND source_type='MONTHLY_RECURRING'""",
                    (TENANT_ID, month),
                ).fetchall()
            }
            generated = []
            reasons = dict.fromkeys(
                ("ALREADY_EXISTS", "NO_MANAGEMENT_CONTRACT", "NO_CHARGE_RULE",
                 "MANAGEMENT_CHANGED_MIDMONTH", "PARTIAL_MANAGEMENT_COVERAGE"), 0,
            )
            excluded_leases = 0
            for candidate in leases:
                lease = get(db, "leases", candidate["id"], lock=True)
                if lease["status"] not in {"SIGNED", "OCCUPIED", "TERMINATION_PENDING", "ENDED"}:
                    continue
                first, last = lease_service_period(lease, month, last_day)
                if first > last:
                    continue
                pending = [row for row in types if (lease["id"], row["id"]) not in duplicates]
                reasons["ALREADY_EXISTS"] += len(types) - len(pending)
                if not pending:
                    continue
                contract = management_for_period(db, lease["unit_id"], first, last, full_coverage=True)
                if contract is None:
                    excluded_leases += 1
                    reasons["NO_MANAGEMENT_CONTRACT"] += len(pending)
                    continue
                if isinstance(contract, str):
                    reasons[contract] += len(pending)
                    continue
                for charge_type in pending:
                    amount = lease["rent_amount" if charge_type["charge_code"] == "RENT" else "common_fee_amount"]
                    if lease["proration_rule"] == "ACTUAL_DAYS_FLOOR":
                        amount = amount * ((last - first).days + 1) // last_day.day
                    values = charge_values(lease, contract, charge_type, month, amount, "MONTHLY_RECURRING", first, last)
                    if values is None:
                        reasons["NO_CHARGE_RULE"] += 1
                    else:
                        generated.append(insert(db, actor, "rent_charges", values))
            result = {"service_month": month, "generated_count": len(generated),
                      "skipped_count": sum(reasons.values()), "skip_reasons": reasons,
                      "leases_without_management_contract": excluded_leases}
            if generated:
                audit(db, actor.user_id, "rental.charges.generated", "rent_charges", None,
                      f"{month:%Y-%m} {len(generated)} 件 / 請求ID {generated[0]}〜{generated[-1]}")
            return result

        return write(operation)

    @router.post("/charges", status_code=201)
    def create_charge(payload: dict, actor=Depends(require_staff)):
        options = dict(payload)
        month = month_value(options.pop("service_month", None))
        values = money_values("rent_charges", options, "lease_id charge_type_id amount due_date",
                              required=("lease_id", "charge_type_id", "amount"))

        def operation(db):
            require_open_period(db, month)
            unit_locks(db, [get(db, "leases", values["lease_id"])["unit_id"]])
            lease = get(db, "leases", values["lease_id"], lock=True)
            if lease["status"] in {"DRAFT", "CANCELLED"}:
                invalid("署名済みの賃貸借契約を指定してください")
            charge_type = get(db, "charge_types", values["charge_type_id"])
            if charge_type["status"] != "ACTIVE" or charge_type["recurring"] or charge_type["charge_code"] == "DEPOSIT":
                invalid("有効な一回性の費目を指定してください。敷金は敷金台帳で管理します")
            contract = management_for_period(db, lease["unit_id"], month, month_end(month))
            if contract is None:
                invalid("対象月に有効な管理契約がありません")
            charge = charge_values(lease, contract, charge_type, month, values["amount"], "MANUAL",
                                   due=values.get("due_date"))
            if charge is None:
                invalid("管理契約に使用可能な費目ルールがありません")
            row_id = insert(db, actor, "rent_charges", charge)
            audit(db, actor.user_id, "rental.charges.created", "rent_charges", row_id, f"{values['amount']} 円")
            return charge_detail(db, row_id)

        return write(operation)

    allocation_sign = "CASE WHEN reversal_of_id IS NULL THEN amount ELSE -ABS(amount) END"

    def allocated_amount(db, key, row_id):
        return int(db.execute(
            f"""SELECT COALESCE(SUM({allocation_sign}),0) AS total
                FROM payment_allocations WHERE tenant_id=? AND {key}=?""", (TENANT_ID, row_id),
        ).fetchone()["total"])

    def allocations_for(db, key, row_id, limit=None, offset=0):
        filters = "a.tenant_id=?"
        args = [TENANT_ID]
        if row_id is not None:
            filters += f" AND a.{key}=?"
            args.append(row_id)
        pagination = ""
        if limit is not None:
            pagination = " LIMIT ? OFFSET ?"
            args.extend((limit, offset))
        return db.execute(
            f"""SELECT a.*, c.charge_code, c.version AS charge_version, p.payment_code,
                       (SELECT r.id FROM payment_allocations r WHERE r.tenant_id=a.tenant_id
                        AND r.reversal_of_id=a.id LIMIT 1) AS reversed_by_id
                FROM payment_allocations a JOIN rent_charges c ON c.tenant_id=a.tenant_id AND c.id=a.charge_id
                JOIN payments p ON p.tenant_id=a.tenant_id AND p.id=a.payment_id
                WHERE {filters} ORDER BY a.id DESC{pagination}""", tuple(args),
        ).fetchall()

    def query_charges(db, *, month=None, lease_id=None, status=None, row_id=None, contract_id=None,
                      available=False, limit=50, offset=0):
        restrictions = ["c.tenant_id=?"]
        args = [TENANT_ID]
        for column, value in (("service_month", month), ("lease_id", lease_id), ("status", status),
                              ("id", row_id), ("management_contract_id", contract_id)):
            if value is not None:
                restrictions.append(f"c.{column}=?")
                args.append(value)
        if available:
            restrictions.append("c.status IN ('UNPAID','PARTIALLY_PAID') AND c.amount>0")
        rows = db.execute(
            f"""SELECT c.*, t.charge_code AS charge_type_code, t.charge_name, l.lease_code,
                       p.display_name AS tenant_name, COALESCE((SELECT SUM({allocation_sign})
                         FROM payment_allocations a WHERE a.tenant_id=c.tenant_id AND a.charge_id=c.id),0)
                         AS allocated_amount
                FROM rent_charges c
                JOIN charge_types t ON t.tenant_id=c.tenant_id AND t.id=c.charge_type_id
                JOIN leases l ON l.tenant_id=c.tenant_id AND l.id=c.lease_id
                JOIN parties p ON p.tenant_id=l.tenant_id AND p.id=l.tenant_party_id
                WHERE {' AND '.join(restrictions)}
                ORDER BY c.service_month DESC, c.id LIMIT ? OFFSET ?""",
            (*args, limit, offset),
        ).fetchall()
        today = today_jst()
        for row in rows:
            row.pop("recurring_month", None)
            row["allocated_amount"] = int(row["allocated_amount"])
            row["remaining_amount"] = 0 if row["status"] == "CANCELLED" else row["amount"] - row["allocated_amount"]
            row["overdue_days"] = max(0, (today - row["due_date"]).days) if row["remaining_amount"] > 0 else 0
            row["beneficiary_snapshot"] = decode(row)["beneficiary_snapshot"]
        return rows

    def charge_detail(db, row_id):
        rows = query_charges(db, row_id=row_id)
        if not rows:
            raise HTTPException(404, "請求が見つかりません")
        return dict(rows[0], allocations=allocations_for(db, "charge_id", row_id))

    @router.get("/charges", dependencies=[Depends(require_staff)])
    def charges(month: str = None, service_month: str = None, lease_id: int = None, status: str = None,
                payment_id: int = None, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
        month = month_value(month or service_month) if month or service_month else None
        with connect() as db:
            contract_id = None
            if payment_id is not None:
                payment = get(db, "payments", payment_id)
                if payment["status"] in {"ALLOCATED", "REVERSED"}:
                    return []
                contract_id = effective_payment_contract(db, payment)
            return query_charges(db, month=month, lease_id=lease_id, status=status, contract_id=contract_id,
                                 available=payment_id is not None, limit=limit, offset=offset)

    @router.get("/charges/overdue", dependencies=[Depends(require_staff)])
    def overdue_charges(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
        today = today_jst()
        with connect() as db:
            rows = db.execute(
                f"""SELECT l.id AS lease_id, l.lease_code, p.display_name AS tenant_name,
                           SUM(c.amount - COALESCE((SELECT SUM({allocation_sign})
                               FROM payment_allocations a WHERE a.tenant_id=c.tenant_id AND a.charge_id=c.id),0))
                               AS remaining_amount,
                           MIN(c.due_date) AS oldest_due_date, COUNT(*) AS charge_count
                    FROM rent_charges c JOIN leases l ON l.tenant_id=c.tenant_id AND l.id=c.lease_id
                    JOIN parties p ON p.tenant_id=l.tenant_id AND p.id=l.tenant_party_id
                    WHERE c.tenant_id=? AND c.status IN ('UNPAID','PARTIALLY_PAID') AND c.due_date<?
                    GROUP BY l.id,l.lease_code,p.display_name HAVING remaining_amount>0
                    ORDER BY oldest_due_date,l.id LIMIT ? OFFSET ?""", (TENANT_ID, today, limit, offset),
            ).fetchall()
            for row in rows:
                row["remaining_amount"] = int(row["remaining_amount"])
                due = row["oldest_due_date"]
                if isinstance(due, str):
                    due = date.fromisoformat(due)
                row["overdue_days"] = (today - due).days
            return rows

    @router.get("/charges/{row_id}", dependencies=[Depends(require_staff)])
    def read_charge(row_id: int):
        with connect() as db:
            return charge_detail(db, row_id)

    @router.post("/charges/{row_id}/cancel")
    def cancel_charge(row_id: int, payload: dict, actor=Depends(require_staff)):
        if payload.get("version") is None:
            invalid("version を指定してください")
        reason = reversal_reason(payload)

        def operation(db):
            require_open_period(db, get(db, "rent_charges", row_id)["service_month"])
            charge = get(db, "rent_charges", row_id, lock=True)
            options = dict(payload)
            options.pop("reason")
            money_version(options, charge)
            money_values("reasons", options, "")
            if charge["status"] == "CANCELLED":
                conflict("この請求は取消済みです")
            if allocated_amount(db, "charge_id", row_id):
                invalid("消込済みの請求です。先に消込を取り消してください")
            update(db, actor, "rent_charges", charge, {"status": "CANCELLED", "cancellation_reason": reason})
            audit(db, actor.user_id, "rental.charges.cancelled", "rent_charges", row_id, reason)
            return charge_detail(db, row_id)

        return write(operation)
    def by_key(db, table, key):
        return db.execute(f"SELECT * FROM {table} WHERE tenant_id=? AND idempotency_key=?",
                          (TENANT_ID, key)).fetchone()

    def payment_pool(payment):
        return "UNIDENTIFIED" if payment["management_contract_id"] is None else "UNALLOCATED"

    def effective_payment_contract(db, payment):
        if payment["management_contract_id"] is not None:
            return payment["management_contract_id"]
        row = db.execute(
            """SELECT c.management_contract_id FROM payment_allocations a
               JOIN rent_charges c ON c.tenant_id=a.tenant_id AND c.id=a.charge_id
               WHERE a.tenant_id=? AND a.payment_id=? AND a.reversal_of_id IS NULL AND NOT EXISTS (
                 SELECT 1 FROM payment_allocations r WHERE r.tenant_id=a.tenant_id AND r.reversal_of_id=a.id
               ) LIMIT 1""", (TENANT_ID, payment["id"]),
        ).fetchone()
        return row["management_contract_id"] if row else None

    def ledger_entry(db, actor, *, account_id, contract_id, category, entry_type, direction,
                     amount, posting, source_type, source_id, group, reversal_of_id=None, reason=None):
        return insert(db, actor, "fund_ledger_entries", dict(
            entry_code=f"L-{uuid.uuid4().hex}", transaction_group_id=group,
            fund_account_id=account_id, management_contract_id=contract_id, fund_category=category,
            entry_type=entry_type, direction=direction, amount=amount, posting_date=posting,
            accounting_month=posting.replace(day=1), source_type=source_type, source_id=source_id,
            reversal_of_id=reversal_of_id, reason=reason,
        ))

    def require_fund_account(account):
        if account["status"] != "ACTIVE" or not account["is_simulated"] or account["currency"] != "JPY":
            invalid("有効な円建ての模擬口座を指定してください")
        return account

    def fund_account_by_code(db, code):
        account = db.execute("SELECT * FROM fund_accounts WHERE tenant_id=? AND account_code=?",
                             (TENANT_ID, code)).fetchone()
        if account is None:
            invalid("指定された資金口座がありません")
        return require_fund_account(account)

    def payment_balance(row):
        row["allocated_amount"] = int(row["allocated_amount"])
        row["remaining_amount"] = 0 if row["status"] == "REVERSED" else row["amount"] - row["allocated_amount"]
        row["unallocated_amount"] = row["remaining_amount"]
        row["unallocated_category"] = payment_pool(row)
        return row

    def payment_detail(db, row_id):
        row = get(db, "payments", row_id)
        return dict(payment_balance(dict(row, allocated_amount=allocated_amount(db, "payment_id", row_id))),
                    effective_management_contract_id=effective_payment_contract(db, row),
                    allocations=allocations_for(db, "payment_id", row_id))

    @router.get("/payments", dependencies=[Depends(require_staff)])
    def payments(status: str = None, available: bool = False,
                 limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
        filters = ["p.tenant_id=?"]
        args = [TENANT_ID]
        if status:
            filters.append("p.status=?")
            args.append(status)
        if available:
            filters.append("p.status IN ('UNALLOCATED','PARTIALLY_ALLOCATED')")
        with connect() as db:
            rows = db.execute(
                f"""SELECT p.*, COALESCE((SELECT SUM({allocation_sign}) FROM payment_allocations a
                        WHERE a.tenant_id=p.tenant_id AND a.payment_id=p.id),0) AS allocated_amount
                    FROM payments p WHERE {' AND '.join(filters)}
                    ORDER BY received_date DESC, id DESC LIMIT ? OFFSET ?""", (*args, limit, offset),
            ).fetchall()
            return [payment_balance(row) for row in rows]

    @router.get("/payments/{row_id}", dependencies=[Depends(require_staff)])
    def read_payment(row_id: int):
        with connect() as db:
            return payment_detail(db, row_id)

    @router.post("/payments", status_code=201)
    def create_payment(payload: dict, actor=Depends(require_staff)):
        required = "received_date amount payer_name payment_source fund_account_id idempotency_key"
        values = money_values("payments", payload,
                              required + " management_contract_id payer_party_id external_reference notes",
                              required=required.split())

        parameters = dict.fromkeys(("management_contract_id", "payer_party_id", "external_reference", "notes")) | values

        def operation(db):
            existing = by_key(db, "payments", values["idempotency_key"])
            if existing:
                return idempotent_result(db, "payments", existing, parameters)
            posting = values["received_date"]
            if posting > today_jst():
                invalid("入金日は本日以前の日付を指定してください")
            require_open_period(db, posting)
            account = get(db, "fund_accounts", values["fund_account_id"], lock=True)
            existing = by_key(db, "payments", values["idempotency_key"])
            if existing:
                return idempotent_result(db, "payments", existing, parameters)
            require_fund_account(account)
            if account["account_code"] != "ESCROW":
                invalid("入金は預り金口座にのみ登録できます")
            validate_refs(db, "payments", values)
            contract_id = values.get("management_contract_id")
            if contract_id is not None and get(db, "management_contracts", contract_id)["status"] not in {"ACTIVE", "ENDED"}:
                invalid("有効または終了済みの管理契約を指定してください")
            code = f"P-{uuid.uuid4().hex}"
            row_id = insert(db, actor, "payments", dict(values, payment_code=code, status="UNALLOCATED"))
            ledger_entry(db, actor, account_id=account["id"], contract_id=contract_id, category=payment_pool(
                         {"management_contract_id": contract_id}), entry_type="RECEIPT", direction="IN",
                         amount=values["amount"], posting=posting, source_type="payment", source_id=row_id, group=code)
            audit(db, actor.user_id, "rental.payments.created", "payments", row_id, f"{values['amount']} 円")
            return payment_detail(db, row_id)

        return idempotent_write(operation, "payments", parameters)

    def idempotent_result(db, table, existing, parameters):
        if any(existing[key] != value for key, value in parameters.items()):
            conflict("同じ冪等キーで異なる内容が指定されています")
        return payment_detail(db, existing["id"]) if table == "payments" else existing

    def idempotent_write(operation, table, parameters):
        try:
            return write(operation)
        except HTTPException as error:
            if error.status_code != 409:
                raise
            # A unique-key race across different parent rows or posting months
            # rolls back the losing transaction before reading the winner.
            with connect() as db:
                existing = by_key(db, table, parameters["idempotency_key"])
                if existing:
                    return idempotent_result(db, table, existing, parameters)
            raise

    def charge_category(charge):
        snapshot = decode(charge)["beneficiary_snapshot"]
        if snapshot["beneficiary_type"] == "COMPANY":
            return "COMPANY_FUNDS"
        if snapshot["beneficiary_type"] != "OWNER":
            invalid("この請求には消込可能な資金区分が設定されていません")
        code = charge["charge_type_code"]
        return "OWNER_RENT" if code == "RENT" else "OWNER_OTHER"

    def move_allocation_funds(db, actor, payment, charge, allocation_id, amount, posting, *, original=None, reason=None):
        group = f"A-{uuid.uuid4().hex}"
        account = payment["fund_account_id"]
        if original is None:
            category = charge_category(charge)
            contract_id = charge["management_contract_id"]
            legs = [(account, payment["management_contract_id"], payment_pool(payment), "OUT", None),
                    (account, contract_id, category, "IN", None)]
            if category == "COMPANY_FUNDS":
                # Reclassify in escrow, then transfer the full amount out of escrow.
                company = fund_account_by_code(db, "COMPANY")
                legs.extend([
                    (account, contract_id, category, "OUT", None),
                    (company["id"], contract_id, category, "IN", None),
                ])
        else:
            prior = ledger_for_source(db, "payment_allocation", original["id"])
            if not prior or any(row["amount"] != amount for row in prior) or (
                len(prior) in (1, 2) and any(row["fund_account_id"] != account for row in prior)
            ):
                conflict("元の消込と台帳が一致しません")
            legs = [(row["fund_account_id"], row["management_contract_id"], row["fund_category"],
                     "OUT" if row["direction"] == "IN" else "IN", row["id"]) for row in prior]
            if len(prior) == 1 and prior[0]["direction"] == "IN":
                # Historic seed rows booked cash directly to the final category.
                legs.append((account, payment["management_contract_id"], payment_pool(payment), "IN", None))
            elif len(prior) not in (2, 4) or sum(row["direction"] == "IN" for row in prior) * 2 != len(prior):
                conflict("元の消込台帳を確認できません")
        for account, contract_id, category, direction, reversed_id in legs:
            ledger_entry(db, actor, account_id=account, contract_id=contract_id, category=category,
                         entry_type="ALLOCATION_REVERSAL" if original else "ALLOCATION",
                         direction=direction, amount=amount, posting=posting, source_type="payment_allocation",
                         source_id=allocation_id, group=group, reversal_of_id=reversed_id, reason=reason)

    def ledger_for_source(db, source, row_id):
        return db.execute(
            """SELECT * FROM fund_ledger_entries WHERE tenant_id=? AND source_type=? AND source_id=?
               ORDER BY id""", (TENANT_ID, source, row_id),
        ).fetchall()

    def update_allocation_status(db, actor, payment, charge, paid, collected):
        charge_status = "PAID" if collected == charge["amount"] else "PARTIALLY_PAID" if collected else "UNPAID"
        payment_status = "ALLOCATED" if paid == payment["amount"] else "PARTIALLY_ALLOCATED" if paid else "UNALLOCATED"
        update(db, actor, "rent_charges", charge, {"status": charge_status})
        update(db, actor, "payments", payment, {"status": payment_status})

    @router.post("/payments/{row_id}/allocate", status_code=201)
    def allocate_payment(row_id: int, payload: dict, actor=Depends(require_staff)):
        versions = allocation_versions(payload, "payment_version", "charge_version")
        required = "charge_id amount idempotency_key"
        values = money_values("payment_allocations", {key: value for key, value in payload.items() if key not in versions},
                              required, required=required.split())

        parameters = dict(values, payment_id=row_id, reversal_of_id=None)

        def operation(db):
            key = values["idempotency_key"]
            existing = by_key(db, "payment_allocations", key)
            if existing:
                return idempotent_result(db, "payment_allocations", existing, parameters)
            posting = today_jst()
            require_open_period(db, posting)
            payment = get(db, "payments", row_id, lock=True)
            existing = by_key(db, "payment_allocations", key)
            if existing:
                return idempotent_result(db, "payment_allocations", existing, parameters)
            if get(db, "fund_accounts", payment["fund_account_id"])["account_code"] != "ESCROW":
                invalid("預り金口座の入金のみ消込できます")
            charge = get(db, "rent_charges", values["charge_id"], lock=True)
            check_version({"version": versions["payment_version"]}, payment)
            check_version({"version": versions["charge_version"]}, charge)
            if payment["status"] == "REVERSED" or charge["status"] == "CANCELLED":
                invalid("取消済みの入金または請求は消し込めません")
            if payment["received_date"] > posting:
                invalid("入金日以降に消込してください")
            contract_id = effective_payment_contract(db, payment)
            if contract_id is not None and contract_id != charge["management_contract_id"]:
                invalid("同じ管理契約の請求にのみ消込できます")
            amount = values["amount"]
            paid = allocated_amount(db, "payment_id", row_id) + amount
            if paid > payment["amount"]:
                invalid("消込額が入金の未消込残高を超えています")
            collected = allocated_amount(db, "charge_id", charge["id"]) + amount
            if collected > charge["amount"]:
                invalid("消込額が請求の未収残高を超えています")
            allocation_id = insert(db, actor, "payment_allocations", dict(
                values, payment_id=row_id, allocation_date=posting, allocated_by=actor.user_id,
            ))
            charge["charge_type_code"] = get(db, "charge_types", charge["charge_type_id"])["charge_code"]
            move_allocation_funds(db, actor, payment, charge, allocation_id, amount, posting)
            update_allocation_status(db, actor, payment, charge, paid, collected)
            audit(db, actor.user_id, "rental.allocations.created", "payment_allocations", allocation_id,
                  f"入金 {row_id} / 請求 {charge['id']} / {amount} 円")
            return get(db, "payment_allocations", allocation_id)

        return idempotent_write(operation, "payment_allocations", parameters)

    def reversal_reason(payload):
        return money_values("reasons", {"reason": payload.get("reason")}, "reason", required=("reason",))["reason"]

    @router.post("/payment_allocations/{row_id}/reverse")
    def reverse_allocation(row_id: int, payload: dict, actor=Depends(require_staff)):
        versions = allocation_versions(payload, "allocation_version", "payment_version", "charge_version")
        values = money_values("payment_allocations", {key: value for key, value in payload.items() if key not in versions},
                              "reason idempotency_key", required=("reason",))
        reason = values["reason"]
        key = values.get("idempotency_key", f"REV-{uuid.uuid4().hex}")
        parameters = {"idempotency_key": key, "reversal_of_id": row_id, "reason": reason}

        def operation(db):
            existing = by_key(db, "payment_allocations", key)
            if existing:
                return idempotent_result(db, "payment_allocations", existing, parameters)
            posting = today_jst()
            require_open_period(db, posting)
            original = get(db, "payment_allocations", row_id)
            payment = get(db, "payments", original["payment_id"], lock=True)
            charge = get(db, "rent_charges", original["charge_id"], lock=True)
            existing = by_key(db, "payment_allocations", key)
            if existing:
                return idempotent_result(db, "payment_allocations", existing, parameters)
            check_version({"version": versions["allocation_version"]}, original)
            check_version({"version": versions["payment_version"]}, payment)
            check_version({"version": versions["charge_version"]}, charge)
            if original["reversal_of_id"] is not None or db.execute(
                "SELECT 1 FROM payment_allocations WHERE tenant_id=? AND reversal_of_id=? LIMIT 1",
                (TENANT_ID, row_id),
            ).fetchone():
                conflict("この消込は取消済み、または取消記録です")
            if original["allocation_date"] > posting:
                invalid("消込日以降に取消してください")
            amount = original["amount"]
            paid = allocated_amount(db, "payment_id", payment["id"]) - amount
            collected = allocated_amount(db, "charge_id", charge["id"]) - amount
            if min(paid, collected) < 0:
                conflict("有効消込残高と取消額が一致しません")
            reversing_id = insert(db, actor, "payment_allocations", dict(
                payment_id=payment["id"], charge_id=charge["id"], allocation_date=posting, amount=amount,
                allocated_by=actor.user_id, idempotency_key=key,
                reversal_of_id=row_id, reason=reason,
            ))
            move_allocation_funds(db, actor, payment, charge, reversing_id, amount, posting, original=original, reason=reason)
            update_allocation_status(db, actor, payment, charge, paid, collected)
            audit(db, actor.user_id, "rental.allocations.reversed", "payment_allocations", reversing_id,
                  f"元の消込 {row_id} / {amount} 円 / {reason}")
            return get(db, "payment_allocations", reversing_id)

        return idempotent_write(operation, "payment_allocations", parameters)

    @router.post("/payments/{row_id}/reverse")
    def reverse_payment(row_id: int, payload: dict, actor=Depends(require_staff)):
        if payload.get("version") is None:
            invalid("version を指定してください")
        reason = reversal_reason(payload)

        def operation(db):
            posting = today_jst()
            require_open_period(db, posting)
            payment = get(db, "payments", row_id, lock=True)
            options = dict(payload)
            options.pop("reason")
            money_version(options, payment)
            money_values("reasons", options, "")
            if payment["status"] == "REVERSED":
                conflict("この入金は取消済みです")
            if payment["received_date"] > posting:
                invalid("入金日以降に取消してください")
            if allocated_amount(db, "payment_id", row_id):
                invalid("消込済みの金額があります。先に消込を取り消してください")
            receipts = [row for row in ledger_for_source(db, "payment", row_id) if row["direction"] == "IN"]
            ledger_entry(db, actor, account_id=payment["fund_account_id"], contract_id=payment["management_contract_id"],
                         category=payment_pool(payment), entry_type="PAYMENT_REVERSAL", direction="OUT",
                         amount=payment["amount"], posting=posting, source_type="payment", source_id=row_id,
                         group=f"P-{uuid.uuid4().hex}", reversal_of_id=receipts[0]["id"] if receipts else None, reason=reason)
            update(db, actor, "payments", payment, {"status": "REVERSED"})
            audit(db, actor.user_id, "rental.payments.reversed", "payments", row_id, reason)
            return payment_detail(db, row_id)

        return write(operation)

    @router.get("/payment_allocations", dependencies=[Depends(require_staff)])
    def payment_allocations(payment_id: int = None, charge_id: int = None,
                            limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
        if payment_id is not None and charge_id is not None:
            invalid("入金または請求のいずれか一方で絞り込んでください")
        with connect() as db:
            return allocations_for(db, "charge_id" if charge_id is not None else "payment_id",
                                   charge_id if charge_id is not None else payment_id, limit, offset)
    @router.get("/deposits", dependencies=[Depends(require_staff)])
    def deposits(lease_id: int = None, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
        with connect() as db:
            return db.execute(
                """SELECT d.*, l.lease_code FROM deposits d
                   JOIN leases l ON l.tenant_id=d.tenant_id AND l.id=d.lease_id
                   WHERE d.tenant_id=? AND (? IS NULL OR d.lease_id=?)
                   ORDER BY d.id DESC LIMIT ? OFFSET ?""", (TENANT_ID, lease_id, lease_id, limit, offset),
            ).fetchall()

    @router.get("/deposits/{row_id}", dependencies=[Depends(require_staff)])
    def read_deposit(row_id: int):
        with connect() as db:
            deposit = get(db, "deposits", row_id)
            lease = get(db, "leases", deposit["lease_id"])
            return dict(deposit, lease_code=lease["lease_code"], lease_status=lease["status"],
                        ledger_entries=ledger_for_source(db, "deposit", row_id))

    def deposit_operation(db, actor, row_id, payload, receive):
        date_key = "received_date" if receive else "refunded_date"
        note_key = "payer_name" if receive else "reason"
        options = dict(payload)
        version = {"version": options.pop("version", None)}
        if version["version"] is None:
            invalid("version を指定してください")
        values = money_values("deposit_event", options, f"amount {date_key} {note_key}",
                              required=("amount", date_key, note_key))
        posting = values[date_key]
        if posting > today_jst():
            invalid("実績日は本日以前の日付を指定してください")
        require_open_period(db, posting)
        if receive:
            lease_id = get(db, "deposits", row_id)["lease_id"]
            lease = get(db, "leases", lease_id, lock=True)
        deposit = get(db, "deposits", row_id, lock=True)
        money_version(version, deposit)
        if deposit["custodian_type"] != "COMPANY":
            invalid("自社保管の敷金のみ受領・返還できます")
        if receive and lease["status"] == "CANCELLED":
            invalid("取消済みの賃貸借契約の敷金は受領できません")
        entries = ledger_for_source(db, "deposit", row_id)
        if any(entry["posting_date"] > posting for entry in entries):
            invalid("敷金の直近の台帳日付以降の日付を指定してください")
        amount = values["amount"]
        received, refunded, transferred = (deposit[key] for key in (
            "received_amount", "refunded_amount", "transferred_amount",
        ))
        if receive:
            if deposit["status"] not in {"EXPECTED", "PARTIALLY_HELD", "HELD"}:
                invalid("返還を開始した敷金には受領を追加できません")
            received += amount
            if received > deposit["agreed_amount"]:
                invalid("受領額が敷金の約定額を超えています")
            status = "HELD" if received == deposit["agreed_amount"] else "PARTIALLY_HELD"
        else:
            refunded += amount
            if refunded + transferred > received:
                invalid("返還額が敷金の預り残高を超えています")
            status = "CLOSED" if refunded + transferred == received else "PARTIALLY_RETURNED"
        if not receive and sum(entry["amount"] if entry["direction"] == "IN" else -entry["amount"]
                               for entry in entries) < amount:
            invalid("返還日の敷金預り残高が不足しています")
        escrow = fund_account_by_code(db, "ESCROW")
        note = f"支払者 {values[note_key]}" if receive else values[note_key]
        ledger_entry(db, actor, account_id=escrow["id"], contract_id=deposit["management_contract_id"],
                     category="DEPOSIT", entry_type="RECEIPT" if receive else "REFUND",
                     direction="IN" if receive else "OUT", amount=amount, posting=posting,
                     source_type="deposit", source_id=row_id, group=f"D-{uuid.uuid4().hex}", reason=note)
        update(db, actor, "deposits", deposit, {"received_amount": received, "refunded_amount": refunded, "status": status})
        action = "received" if receive else "refunded"
        audit(db, actor.user_id, f"rental.deposits.{action}", "deposits", row_id, f"{amount} 円 / {note}")
        return get(db, "deposits", row_id)

    @router.post("/deposits/{row_id}/receive")
    def receive_deposit(row_id: int, payload: dict, actor=Depends(require_staff)):
        return write(lambda db: deposit_operation(db, actor, row_id, payload, True))

    @router.post("/deposits/{row_id}/refund")
    def refund_deposit(row_id: int, payload: dict, actor=Depends(require_staff)):
        return write(lambda db: deposit_operation(db, actor, row_id, payload, False))

    fund_categories = ("OWNER_RENT", "OWNER_OTHER", "DEPOSIT", "UNALLOCATED", "UNIDENTIFIED", "COMPANY_FUNDS")
    signed_entry = "CASE WHEN e.direction='IN' THEN e.amount WHEN e.direction='OUT' THEN -e.amount ELSE 0 END"

    def reconcile_business_sources(db):
        # Keep each contract and each business source independent so differences cannot offset.
        rows = db.execute(
            f"""WITH contract_ids AS (
                    SELECT id FROM management_contracts WHERE tenant_id=?
                ), active_allocations AS (
                    SELECT a.payment_id, a.charge_id, a.amount
                    FROM payment_allocations a
                    WHERE a.tenant_id=? AND a.reversal_of_id IS NULL AND NOT EXISTS (
                        SELECT 1 FROM payment_allocations r
                        WHERE r.tenant_id=a.tenant_id AND r.reversal_of_id=a.id
                    )
                ), payment_usage AS (
                    SELECT payment_id, SUM(amount) AS used_amount FROM active_allocations GROUP BY payment_id
                ), business_amounts AS (
                    SELECT p.management_contract_id AS contract_id,
                           CASE WHEN p.management_contract_id IS NULL THEN 'unidentified' ELSE 'unallocated' END AS source,
                           p.amount-COALESCE(u.used_amount,0) AS amount
                    FROM payments p LEFT JOIN payment_usage u ON u.payment_id=p.id
                    WHERE p.tenant_id=? AND p.status<>'REVERSED'
                    UNION ALL
                    SELECT management_contract_id, 'deposit', received_amount-refunded_amount-transferred_amount
                    FROM deposits WHERE tenant_id=?
                    UNION ALL
                    SELECT c.management_contract_id, 'owner_allocation', a.amount
                    FROM active_allocations a JOIN rent_charges c ON c.id=a.charge_id AND c.tenant_id=?
                    WHERE JSON_UNQUOTE(JSON_EXTRACT(c.beneficiary_snapshot,'$.beneficiary_type'))='OWNER'
                    UNION ALL
                    SELECT NULL, 'company_funds', a.amount
                    FROM active_allocations a JOIN rent_charges c ON c.id=a.charge_id AND c.tenant_id=?
                    WHERE JSON_UNQUOTE(JSON_EXTRACT(c.beneficiary_snapshot,'$.beneficiary_type'))='COMPANY'
                ), totals AS (
                    SELECT contract_id, source, SUM(amount) AS business_amount, 0 AS ledger_amount
                    FROM business_amounts GROUP BY contract_id,source
                    UNION ALL
                    SELECT e.management_contract_id,
                           CASE WHEN e.fund_category IN ('UNALLOCATED','UNIDENTIFIED') THEN 'unallocated'
                                WHEN e.fund_category='DEPOSIT' THEN 'deposit' ELSE 'owner_allocation' END,
                           0, SUM({signed_entry})
                    FROM fund_ledger_entries e JOIN fund_accounts f
                      ON f.tenant_id=e.tenant_id AND f.id=e.fund_account_id AND f.account_code='ESCROW'
                    WHERE e.tenant_id=? AND e.management_contract_id IS NOT NULL
                      AND e.fund_category IN ('UNALLOCATED','UNIDENTIFIED','DEPOSIT','OWNER_RENT','OWNER_OTHER')
                    GROUP BY e.management_contract_id, 2
                    UNION ALL
                    SELECT NULL, 'unidentified', 0, COALESCE(SUM({signed_entry}),0)
                    FROM fund_ledger_entries e
                    WHERE e.tenant_id=? AND e.management_contract_id IS NULL AND e.fund_category='UNIDENTIFIED'
                    UNION ALL
                    SELECT NULL, 'company_funds', 0, COALESCE(SUM({signed_entry}),0)
                    FROM fund_ledger_entries e JOIN fund_accounts f
                      ON f.tenant_id=e.tenant_id AND f.id=e.fund_account_id AND f.account_code='COMPANY'
                    WHERE e.tenant_id=? AND e.fund_category='COMPANY_FUNDS'
                )
                SELECT c.id AS management_contract_id, t.source,
                       SUM(t.business_amount) AS business_amount, SUM(t.ledger_amount) AS ledger_amount
                FROM contract_ids c LEFT JOIN totals t ON t.contract_id=c.id
                GROUP BY c.id,t.source
                UNION ALL
                SELECT NULL, source, SUM(business_amount), SUM(ledger_amount)
                FROM totals WHERE contract_id IS NULL GROUP BY source
                ORDER BY management_contract_id""",
            (TENANT_ID,) * 9,
        ).fetchall()
        contracts = {}
        independent = {}
        for row in rows:
            contract_id = row["management_contract_id"]
            checks = independent if contract_id is None else contracts.setdefault(contract_id, {
                source: {"business_amount": 0, "ledger_amount": 0, "difference": 0}
                for source in ("unallocated", "deposit", "owner_allocation")
            })
            if row["source"] is not None:
                business, ledger = int(row["business_amount"]), int(row["ledger_amount"])
                checks[row["source"]] = {"business_amount": business, "ledger_amount": ledger,
                                         "difference": business - ledger}
        contract_checks = [dict(checks, management_contract_id=contract_id) for contract_id, checks in contracts.items()]
        return contract_checks, independent

    @router.get("/funds/summary", dependencies=[Depends(require_staff)])
    def funds_summary():
        with connect() as db:
            rows = db.execute(
                f"""SELECT f.id, f.account_code, f.account_name, f.status, e.fund_category,
                           COALESCE(SUM({signed_entry}),0) AS balance
                    FROM fund_accounts f LEFT JOIN fund_ledger_entries e
                      ON e.tenant_id=f.tenant_id AND e.fund_account_id=f.id
                    WHERE f.tenant_id=?
                    GROUP BY f.id,f.account_code,f.account_name,f.status,e.fund_category ORDER BY f.id""",
                (TENANT_ID,),
            ).fetchall()
            reconciliation, independent = reconcile_business_sources(db)
        accounts = {}
        for row in rows:
            account = accounts.setdefault(row["id"], {
                key: row[key] for key in ("id", "account_code", "account_name", "status")
            } | {"balance": 0, "categories": {}})
            balance = int(row["balance"])
            account["balance"] += balance
            if row["fund_category"] is not None:
                account["categories"][row["fund_category"]] = balance
        escrow = next((row for row in accounts.values() if row["account_code"] == "ESCROW"), None)
        categories = dict.fromkeys(fund_categories, 0)
        if escrow:
            categories.update({key: value for key, value in escrow["categories"].items() if key in categories})
        return {"accounts": list(accounts.values()), "escrow_categories": categories,
                "reconciliation_difference": (escrow["balance"] if escrow else 0) - sum(categories.values()),
                "business_reconciliation": reconciliation, "independent_reconciliation": independent}

    @router.get("/funds/ledger", dependencies=[Depends(require_staff)])
    def funds_ledger(fund_account_id: int = None, category: str = None, month: str = None,
                     limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
        filters = ["tenant_id=?"]
        args = [TENANT_ID]
        for column, value in (("fund_account_id", fund_account_id), ("fund_category", category),
                              ("accounting_month", month_value(month) if month else None)):
            if value is not None:
                filters.append(f"{column}=?")
                args.append(value)
        with connect() as db:
            return db.execute(
                f"""SELECT * FROM fund_ledger_entries WHERE {' AND '.join(filters)}
                    ORDER BY posting_date DESC,id DESC LIMIT ? OFFSET ?""", (*args, limit, offset),
            ).fetchall()

    @router.get("/funds/by-contract", dependencies=[Depends(require_staff)])
    def funds_by_contract(month: str, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
        service_month = month_value(month)
        with connect() as db:
            rows = db.execute(
                f"""SELECT mc.id AS management_contract_id, mc.contract_code,
                    SUM(CASE WHEN e.fund_category IN ('OWNER_RENT','OWNER_OTHER') AND e.accounting_month<? THEN {signed_entry} ELSE 0 END) AS opening_balance,
                    SUM(CASE WHEN e.fund_category IN ('OWNER_RENT','OWNER_OTHER') AND e.accounting_month=? AND e.direction='IN' THEN e.amount ELSE 0 END) AS monthly_in,
                    SUM(CASE WHEN e.fund_category IN ('OWNER_RENT','OWNER_OTHER') AND e.accounting_month=? AND e.direction='OUT' THEN e.amount ELSE 0 END) AS monthly_out,
                    SUM(CASE WHEN e.fund_category='DEPOSIT' AND e.accounting_month<? THEN {signed_entry} ELSE 0 END) AS deposit_opening_balance,
                    SUM(CASE WHEN e.fund_category='DEPOSIT' AND e.accounting_month=? AND e.direction='IN' THEN e.amount ELSE 0 END) AS deposit_monthly_in,
                    SUM(CASE WHEN e.fund_category='DEPOSIT' AND e.accounting_month=? AND e.direction='OUT' THEN e.amount ELSE 0 END) AS deposit_monthly_out
                    FROM management_contracts mc LEFT JOIN fund_ledger_entries e
                      ON e.tenant_id=mc.tenant_id AND e.management_contract_id=mc.id AND e.accounting_month<=?
                      AND e.fund_category IN ('OWNER_RENT','OWNER_OTHER','DEPOSIT')
                    WHERE mc.tenant_id=? AND mc.status IN ('ACTIVE','ENDED')
                      AND (mc.start_date<=? OR e.id IS NOT NULL)
                    GROUP BY mc.id,mc.contract_code ORDER BY mc.id LIMIT ? OFFSET ?""",
                (*([service_month] * 7), TENANT_ID, month_end(service_month), limit, offset),
            ).fetchall()
        for row in rows:
            for prefix in ("", "deposit_"):
                keys = [prefix + key for key in ("opening_balance", "monthly_in", "monthly_out")]
                opening, incoming, outgoing = (int(row[key]) for key in keys)
                row.update(zip(keys, (opening, incoming, outgoing)))
                row[prefix + "closing_balance"] = opening + incoming - outgoing
        return {"month": service_month, "basis": "CASH_FLOW", "items": rows}

    case_location = "building_id unit_id"
    case_fields = "category urgency description assigned_user_id"
    inspection_fields = "inspection_type inspection_date result findings next_inspection_date"
    approval_actions = {"approve", "reapprove"}
    work_actions = {
        "estimate": (("RECEIVED",), "ESTIMATED", "estimated_amount cost_bearer", ("estimated_amount",)),
        "approve": (("ESTIMATED",), "APPROVED", "approved_amount", ("approved_amount",)),
        "arrange": (("APPROVED",), "ARRANGED", "contractor_party_id scheduled_date",
                    ("contractor_party_id", "scheduled_date")),
        "complete": (("ARRANGED",), "COMPLETED", "completed_date actual_amount", ("completed_date", "actual_amount")),
        "inspect": (("COMPLETED",), "INSPECTED", "inspected_date", ("inspected_date",)),
        "confirm-cost": (("INSPECTED",), "COST_CONFIRMED", "actual_amount", ("actual_amount",)),
        "reapprove": (("COMPLETED", "INSPECTED"), None, "approved_amount", ("approved_amount",)),
        "close": (("COST_CONFIRMED",), "CLOSED", "", ()),
        "cancel": (("RECEIVED", "ESTIMATED", "APPROVED", "ARRANGED"), "CANCELLED", "", ()),
    }
    complaint_actions = {
        "start": ("OPEN", "IN_PROGRESS"),
        "resolve": ("IN_PROGRESS", "RESOLVED"),
        "close": ("RESOLVED", "CLOSED"),
    }

    def case_data(table, payload, allowed, required):
        return money_values(table, payload, allowed, required=required.split())

    def check_location(db, values):
        if values.get("unit_id") is not None:
            unit = get(db, "units", values["unit_id"], lock=True)
            if unit["building_id"] != values["building_id"]:
                invalid("指定した部屋はこの建物に属していません")

    def linked_work_order(db, complaint_id):
        return db.execute(
            """SELECT id, work_order_code, status FROM work_orders
               WHERE tenant_id=? AND complaint_id=? ORDER BY id LIMIT 1""",
            (TENANT_ID, complaint_id),
        ).fetchone()

    def insert_case(db, actor, table, values):
        row_id = insert(db, actor, table, values)
        note = f"修繕 {values['work_order_id']} の検収" if values.get("work_order_id") else "登録"
        audit(db, actor.user_id, f"rental.{table}.created", table, row_id, note)
        return get(db, table, row_id)

    def create_work_order_record(db, actor, values, complaint):
        if complaint is not None:
            if linked_work_order(db, complaint["id"]):
                conflict("この苦情には既に修繕が登録されています")
            if complaint["building_id"] != values["building_id"] or (
                complaint["unit_id"] is not None and values.get("unit_id") not in (None, complaint["unit_id"])
            ):
                invalid("修繕の建物・部屋が苦情と一致しません")
            if values.get("unit_id") is None:
                values["unit_id"] = complaint["unit_id"]

        check_location(db, values)
        if values.get("unit_id") is not None:
            received = values["received_date"]
            management = management_for_period(db, values["unit_id"], received, received)
            contract_id = management["id"] if management else None
            if values.get("management_contract_id") not in (None, contract_id):
                invalid("指定した管理契約は受付日にこの部屋を管理していません")
            values["management_contract_id"] = contract_id
        elif values.get("management_contract_id") is not None:
            invalid("建物単位の修繕には管理契約を指定できません")
        validate_refs(db, "work_orders", values)
        return insert_case(db, actor, "work_orders", dict(
            values, work_order_code=f"WO-{uuid.uuid4().hex}", status="RECEIVED",
        ))

    @router.post("/work-orders", status_code=201)
    def create_work_order(payload: dict, actor=Depends(require_staff)):
        if "complaint_id" in payload:
            invalid("苦情との紐付けは苦情の修繕化から行ってください")
        values = case_data(
            "work_orders", payload,
            f"{case_location} {case_fields} received_date management_contract_id cost_bearer",
            f"building_id {case_fields} received_date",
        )

        def operation(db):
            return create_work_order_record(db, actor, values, None)

        return write(operation)

    @router.post("/complaints", status_code=201)
    def create_complaint(payload: dict, actor=Depends(require_staff)):
        values = case_data(
            "complaints", payload, f"{case_location} {case_fields} reporter_party_id received_at",
            f"building_id {case_fields} received_at",
        )

        def operation(db):
            validate_refs(db, "complaints", values)
            check_location(db, values)
            return insert_case(db, actor, "complaints", dict(
                values, complaint_code=f"CMP-{uuid.uuid4().hex}", status="OPEN",
            ))

        return write(operation)

    @router.post("/inspections", status_code=201)
    def create_inspection(payload: dict, actor=Depends(require_staff)):
        values = case_data(
            "inspections", payload, f"{case_location} {inspection_fields}",
            "building_id inspection_type inspection_date result",
        )
        values["inspected_by"] = actor.user_id
        ordered_dates(values, "inspection_date", "next_inspection_date")

        def operation(db):
            validate_refs(db, "inspections", values)
            check_location(db, values)
            return insert_case(db, actor, "inspections", values)

        return write(operation)

    def change_case(db, actor, table, row, action, values, note=""):
        update(db, actor, table, row, values)
        target = values.get("status", row["status"])
        audit(db, actor.user_id, f"rental.{table}.{action}", table, row["id"],
              f"{row['status']} → {target}{note}")
        return get(db, table, row["id"])

    def has_work_order_management_contract(db, row):
        if row["unit_id"] is None or row["management_contract_id"] is None:
            return False
        received = row["received_date"]
        contract = management_for_period(db, row["unit_id"], received, received)
        return contract is not None and contract["id"] == row["management_contract_id"]

    @router.post("/work-orders/{row_id}/{action}")
    def transition_work_order(row_id: int, action: str, payload: dict, actor=Depends(require_staff)):
        if action not in work_actions:
            raise HTTPException(404, "指定された修繕操作が見つかりません")
        if action in approval_actions and actor.account_role not in {
            "executive", "finance", "store_manager", "administrator",
        }:
            raise HTTPException(403, "修繕を承認する権限がありません")
        sources, target, allowed, required = work_actions[action]

        def operation(db):
            row = get(db, "work_orders", row_id, lock=True)
            data = dict(payload)
            check_version(data, row)
            if row["status"] not in sources:
                invalid("現在の修繕状態ではこの操作はできません")
            findings = None
            if action == "inspect":
                findings = fields("inspections", {"findings": data.pop("findings", None)}, ("findings",))["findings"]
            note = ""
            if action == "cancel":
                reason = data.pop("cancellation_reason", None)
                if not isinstance(reason, str) or not reason.strip() or len(reason) > 16000:
                    invalid("取消理由を入力してください（16,000文字以内）")
                note = f" / 取消理由: {reason.strip()}"
            values = money_values("work_orders", data, allowed, required=required)
            if action == "estimate":
                if not values.get("cost_bearer", row["cost_bearer"]):
                    invalid("見積時に費用負担者を指定してください")
            if action in approval_actions:
                values["approved_by"] = actor.user_id
            if action == "complete":
                if values["completed_date"] < row["received_date"]:
                    invalid("完了日は受付日以後にしてください")
                if values["completed_date"] > today_jst():
                    invalid("完了日に未来日は指定できません")
            if action == "inspect":
                if row["completed_date"] is None or values["inspected_date"] < row["completed_date"]:
                    invalid("検収日は作業完了日以後にしてください")
                if values["inspected_date"] > today_jst():
                    invalid("検収日に未来日は指定できません")
                values["inspected_by"] = actor.user_id
            validate_refs(db, "work_orders", values)
            if action == "inspect":
                inspection = insert_case(db, actor, "inspections", {
                    "building_id": row["building_id"], "unit_id": row["unit_id"], "work_order_id": row_id,
                    "inspection_type": "REPAIR_ACCEPTANCE", "inspection_date": values["inspected_date"],
                    "inspected_by": values["inspected_by"], "result": "PASS", "findings": findings,
                })
                note = f" / 検収記録 {inspection['id']}"
            if action == "confirm-cost":
                if row["cost_bearer"] == "OWNER":
                    if row["unit_id"] is not None:
                        get(db, "units", row["unit_id"], lock=True)
                    if not has_work_order_management_contract(db, row):
                        invalid("オーナー負担の費用確定には有効な管理契約が必要です")
                if row["approved_amount"] is None or values["actual_amount"] > row["approved_amount"]:
                    invalid("実費が承認額を超えています。先に再承認（reapprove）してください")
                now = datetime.now(timezone.utc)
                require_open_period(db, now.astimezone(JST).date())
                values["cost_confirmed_at"] = now.replace(tzinfo=None)
                note = f" / 確定実費 {values['actual_amount']} 円"
            if "approved_amount" in values:
                note = f" / 承認額 {values['approved_amount']} 円 / 承認者 {values['approved_by']}"
            if target:
                values["status"] = target
            return change_case(db, actor, "work_orders", row, action, values, note)

        return write(operation)

    @router.post("/complaints/{row_id}/create-work-order", status_code=201)
    def convert_complaint(row_id: int, payload: dict, actor=Depends(require_staff)):
        def operation(db):
            row = get(db, "complaints", row_id, lock=True)
            data = dict(payload)
            check_version(data, row)
            if linked_work_order(db, row_id):
                conflict("この苦情には既に修繕が登録されています")
            if row["status"] not in {"OPEN", "IN_PROGRESS"}:
                invalid("受付または対応中の苦情のみ修繕化できます")
            values = case_data(
                "work_orders", data, f"{case_fields} received_date management_contract_id cost_bearer", "",
            )
            for key in case_fields.split():
                values.setdefault(key, row[key])
            received = row["received_at"]
            values.setdefault("received_date", received.replace(tzinfo=timezone.utc).astimezone(JST).date())
            order = create_work_order_record(db, actor, dict(
                values, building_id=row["building_id"], unit_id=row["unit_id"], complaint_id=row_id,
            ), row)
            change_case(db, actor, "complaints", row, "create-work-order",
                        {"status": "IN_PROGRESS"}, f" / 修繕 {order['id']}")
            return order

        return write(operation)

    @router.post("/complaints/{row_id}/{action}")
    def transition_complaint(row_id: int, action: str, payload: dict, actor=Depends(require_staff)):
        if action not in complaint_actions:
            raise HTTPException(404, "指定された苦情操作が見つかりません")
        source, target = complaint_actions[action]

        def operation(db):
            row = get(db, "complaints", row_id, lock=True)
            data = dict(payload)
            check_version(data, row)
            if row["status"] != source:
                invalid("現在の苦情状態ではこの操作はできません")
            if action == "resolve":
                summary = re.sub(r"^\\s+|\\s+$", "", data.get("resolution_summary", "")) if isinstance(
                    data.get("resolution_summary"), str) else ""
                values = case_data("complaints", dict(data, resolution_summary=summary),
                                   "resolution_summary", "resolution_summary")
                values["resolved_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
                if values["resolved_at"] < row["received_at"]:
                    invalid("解決日時は受付日時以後にしてください")
            else:
                values = fields("complaints", data, ())
            return change_case(db, actor, "complaints", row, action, dict(values, status=target))

        return write(operation)

    def case_rows(db, table, filters, args, limit, offset=0):
        return db.execute(
            f"""SELECT t.*, b.building_name, u.unit_number
                FROM {table} t JOIN buildings b ON b.tenant_id=t.tenant_id AND b.id=t.building_id
                LEFT JOIN units u ON u.tenant_id=t.tenant_id AND u.id=t.unit_id
                WHERE t.tenant_id=? AND {' AND '.join(filters)} ORDER BY t.id DESC LIMIT ? OFFSET ?""",
            (TENANT_ID, *args, limit, offset),
        ).fetchall()

    def register_case_reads(table):
        path = "/" + table.replace("_", "-")
        dependencies = [Depends(require_staff)]

        @router.get(path, dependencies=dependencies, name=f"rental_{table}_list")
        def listing(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                    status: str = None, urgency: str = None, building_id: int = None):
            conditions = {"building_id": building_id}
            if table != "inspections":
                conditions.update(status=status, urgency=urgency)
            filters, args = ["1=1"], []
            for column, value in conditions.items():
                if value is not None:
                    filters.append(f"t.{column}=?")
                    args.append(value)
            with connect() as db:
                return case_rows(db, table, filters, args, limit, offset)

        @router.get(path + "/{row_id}", dependencies=dependencies, name=f"rental_{table}_detail")
        def detail(row_id: int):
            with connect() as db:
                rows = case_rows(db, table, ["t.id=?"], (row_id,), 1)
                if not rows:
                    raise HTTPException(404, "指定されたデータが見つかりません")
                row = rows[0]
                if table == "work_orders":
                    row["inspections"] = case_rows(db, "inspections", ["t.work_order_id=?"], (row_id,), 100)
                    row["complaint"] = (
                        get(db, "complaints", row["complaint_id"]) if row["complaint_id"] else None
                    )
                    row["settlement_eligible"] = (
                        row["status"] in {"COST_CONFIRMED", "CLOSED"} and row["cost_bearer"] == "OWNER"
                        and row["actual_amount"] is not None and row["cost_confirmed_at"] is not None
                        and bool(row["inspections"]) and has_work_order_management_contract(db, row)
                    )
                    row["settlement_participated"] = db.execute(
                        """SELECT 1 FROM settlement_lines
                           WHERE tenant_id=? AND source_type IN ('work_order','WORK_ORDER') AND source_id=?
                           LIMIT 1""",
                        (TENANT_ID, row_id),
                    ).fetchone() is not None
                if table == "complaints":
                    row["work_order"] = linked_work_order(db, row_id)
                return row

    for case_table in ("work_orders", "complaints", "inspections"):
        register_case_reads(case_table)

    app.include_router(router)
