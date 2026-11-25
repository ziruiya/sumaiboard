"""Rental schema, sample data, and staff workflows."""

import json
import random
import re
import uuid
from datetime import date, datetime, timedelta
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
           WHERE u.tenant_id=? AND u.management_status='MANAGED' AND EXISTS (
               SELECT 1 FROM management_contract_units cu
               JOIN management_contracts mc ON mc.tenant_id=cu.tenant_id AND mc.id=cu.management_contract_id
               WHERE cu.tenant_id=u.tenant_id AND cu.unit_id=u.id
                 AND cu.valid_from <= ? AND (cu.valid_to IS NULL OR cu.valid_to >= ?)
                 AND mc.start_date <= ? AND (mc.end_date IS NULL OR mc.end_date >= ?)
                 AND mc.status IN ('ACTIVE', 'ENDED')
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
    json_fields = {"included_charge_types", "fee_plan_snapshot", "charge_rule_snapshot"}
    boolean_fields = {"tax_inclusive", "vacancy_exempt", "refundable", "recurring", "settlement_eligible"}
    occupancy_states = ("VACANT", "APPLYING", "CONTRACTING", "OCCUPIED", "TERMINATION_PENDING")
    choices = {
        "party_type": ("individual", "company"),
        "management_status": ("MANAGED", "UNMANAGED"),
        "occupancy_status": occupancy_states,
        "calculation_basis": ("CASH_COLLECTED",),
        "rounding_rule": ("FLOOR",),
        "acquisition_channel": ("OWN_SALE", "OTHER_PURCHASE", "INHERITANCE", "MANAGEMENT_TRANSFER", "OTHER"),
        "deposit_custodian": ("COMPANY", "OWNER", "OTHER"),
        "proration_rule": ("ACTUAL_DAYS_FLOOR",),
        "screening_result": ("PENDING", "APPROVED", "REJECTED"),
    }
    for field in ("external_signature_status", "external_procedure_status"):
        choices[field] = ("NOT_STARTED_SAMPLE", "IN_PROGRESS_SAMPLE", "RECORDED_SAMPLE")

    # Editable fields are explicit. Column metadata keeps validation within the existing schema bounds.
    editable = {
        "parties": "party_type display_name name_kana postal_code address phone email contact_person remittance_destination_ref notes",
        "buildings": "building_code building_name postal_code address building_type structure_type construction_month floor_count management_start_date status notes",
        "units": "building_id unit_number owner_party_id floor_number floor_area layout_type advertised_rent advertised_common_fee management_status occupancy_status notes",
        "fee_plans": "plan_code plan_name rate calculation_basis included_charge_types tax_inclusive tax_rate vacancy_exempt rounding_rule minimum_fee effective_from effective_to",
        "management_contracts": "contract_code owner_party_id principal_party_id payee_party_id acquisition_channel accepted_date acquired_date start_date end_date previous_manager_name assigned_user_id remittance_day deposit_custodian notes",
        "management_contract_units": "unit_id valid_from valid_to",
        "applications": "application_code unit_id applicant_party_id application_date application_channel desired_move_in_date proposed_rent proposed_common_fee external_procedure_status external_reference assigned_user_id notes",
        "leases": "lease_code unit_id tenant_party_id guarantor_party_id contract_type start_date scheduled_end_date rent_amount common_fee_amount deposit_amount key_money_amount payment_due_day proration_rule external_signature_status",
    }
    columns = {
        table: {match[1]: (match[2], match[3], match[4], bool(match[5]))
                for match in re.finditer(
                    r"(\w+) (BIGINT|INT|TINYINT|DATE|VARCHAR|TEXT|DECIMAL|BOOLEAN|JSON)"
                    r"(?:\((\d+)(?:,(\d+))?\))?( NOT NULL)?(?=,|\s*$)", TABLE_DEFINITIONS[table], re.M)}
        for table in editable
    }
    amount_fields = {
        "advertised_rent", "advertised_common_fee", "minimum_fee", "proposed_rent",
        "proposed_common_fee", "rent_amount", "common_fee_amount", "deposit_amount", "key_money_amount",
    }
    defaults = {
        "buildings": {"status": "ACTIVE"},
        "units": {"management_status": "UNMANAGED", "occupancy_status": "VACANT"},
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

    def check_assignments(db, contract, rows, previous=()):
        unit_locks(db, [row["unit_id"] for row in [*rows, *previous]])
        checked = {}
        for row in rows:
            start, end = row["valid_from"], row.get("valid_to")
            ordered_dates(row, "valid_from", "valid_to")
            if start < contract["start_date"] or (
                contract.get("end_date") and (start > contract["end_date"] or (end and end > contract["end_date"]))
            ):
                invalid("部屋の割当期間は管理契約期間内にしてください")
            unit_id = row["unit_id"]
            if unit_id not in checked:
                existing = db.execute(
                    """SELECT cu.valid_from, cu.valid_to, mc.end_date FROM management_contract_units cu
                       JOIN management_contracts mc ON mc.tenant_id=cu.tenant_id AND mc.id=cu.management_contract_id
                       WHERE cu.tenant_id=? AND cu.unit_id=? AND mc.id<>? AND mc.status='ACTIVE'""",
                    (TENANT_ID, unit_id, contract.get("id", 0)),
                ).fetchall()
                checked[unit_id] = [(item["valid_from"], min(
                    (day for day in (item["valid_to"], item["end_date"]) if day is not None), default=None
                )) for item in existing]
            effective_end = end or contract.get("end_date")
            if any(overlaps(start, effective_end, old_start, old_end) for old_start, old_end in checked[unit_id]):
                conflict("同じ部屋の管理契約の有効期間が重複しています")
            checked[unit_id].append((start, effective_end))

    def save_assignments(db, actor, row_id, rows, previous):
        old = {(row["unit_id"], row["valid_from"]): row for row in previous}
        for values in rows:
            values = dict(values, valid_to=values.get("valid_to"))
            row = old.pop((values["unit_id"], values["valid_from"]), None)
            if row is None:
                assignment_id = insert(db, actor, "management_contract_units", dict(values, management_contract_id=row_id))
                audit(db, actor.user_id, "rental.assignment.created", "management_contract_unit", assignment_id, f"管理契約 {row_id}")
            elif row["valid_to"] != values["valid_to"]:
                update(db, actor, "management_contract_units", row, {"valid_to": values["valid_to"]})
                audit(db, actor.user_id, "rental.assignment.updated", "management_contract_unit", row["id"], f"管理契約 {row_id}")
        for row in old.values():
            db.execute("DELETE FROM management_contract_units WHERE tenant_id=? AND id=? AND version=?",
                       (TENANT_ID, row["id"], row["version"]))
            audit(db, actor.user_id, "rental.assignment.removed", "management_contract_unit", row["id"], f"管理契約 {row_id}")

    def plan_snapshots(db, plan_id):
        plan = decode(get(db, "fee_plans", plan_id))
        if plan["status"] != "ACTIVE":
            invalid("有効な管理料プランを選んでください")
        snapshot = {key: str(plan[key]) if isinstance(plan[key], Decimal) else plan[key] for key in snapshot_fields}
        rules = db.execute(
            """SELECT id, charge_code, beneficiary_type, tax_category, refundable, recurring, settlement_eligible
               FROM charge_types WHERE tenant_id=? AND status='ACTIVE' ORDER BY id""", (TENANT_ID,),
        ).fetchall()
        return {
            "fee_plan_id": plan_id, "fee_plan_version": plan["plan_version"],
            "fee_plan_snapshot": json.dumps(snapshot),
            "charge_rule_snapshot": json.dumps({rule.pop("charge_code"): decode(rule) for rule in rules}),
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
            ordered_dates(values, "start_date", "scheduled_end_date")

    def lease_period(lease):
        start = min(lease["start_date"], lease.get("actual_move_in_date") or lease["start_date"])
        actual_end = lease.get("actual_move_out_date")
        if actual_end is not None:
            return start, actual_end - timedelta(days=1)
        return start, lease.get("scheduled_move_out_date") or lease.get("scheduled_end_date")

    def check_lease_period(db, lease):
        start, end = lease_period(lease)
        if end is not None and end < start:
            return
        rows = db.execute(
            """SELECT * FROM leases WHERE tenant_id=? AND unit_id=? AND id<>?
               AND status IN ('SIGNED','OCCUPIED','TERMINATION_PENDING','ENDED')""",
            (TENANT_ID, lease["unit_id"], lease.get("id", 0)),
        ).fetchall()
        for other in rows:
            other_start, other_end = lease_period(other)
            if (other_end is None or other_end >= other_start) and overlaps(start, end, other_start, other_end):
                conflict("同じ部屋の賃貸借契約期間が重複しています")

    def refresh_occupancy(db, actor, unit_id):
        unit = get(db, "units", unit_id)
        leases = db.execute(
            "SELECT status FROM leases WHERE tenant_id=? AND unit_id=? AND status<>'ENDED'",
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
                   ORDER BY mc.status='ACTIVE' DESC, cu.valid_from DESC, mc.id DESC LIMIT 1""",
                (TENANT_ID, row_id, today, today, today, today),
            ).fetchone()
            row["building_name"] = get(db, "buildings", row["building_id"])["building_name"]
            row["current_management_contract"] = decode(contract) if contract else None
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
        elif table == "fee_plans":
            extra = dict(fields(table, {"plan_version": payload.pop("plan_version", 1)}, ("plan_version",)),
                         status="DRAFT")
        elif table == "management_contracts":
            plan = fields(table, {"fee_plan_id": payload.pop("fee_plan_id", None)}, ("fee_plan_id",))
            rows = parse_assignments(payload.pop("units", []))
            cutoff = payload.pop("settlement_cutoff_day", 31)
            if type(cutoff) is not int or cutoff != 31:
                invalid("精算締め日は月末固定です")
            extra = dict(plan_snapshots(db, plan["fee_plan_id"]), settlement_cutoff_day=31, status="DRAFT")
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
            check_assignments(db, values, rows)
        if table in {"applications", "leases"}:
            unit_locks(db, [values["unit_id"]])
        if table == "leases":
            check_lease_period(db, values)
        row_id = insert(db, actor, table, values)
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
        return [fields("management_contract_units", row, editable["management_contract_units"].split(), create=True)
                for row in raw]

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
            allowed = [key for key in allowed if key not in {"owner_party_id", "start_date"}]
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
        validate_refs(db, table, values)
        merged = row | values
        validate_business(db, table, merged)
        if table == "management_contracts":
            previous = assignments(db, row_id)
            check_assignments(db, merged, previous if rows is None else rows, previous)
            if rows is not None:
                save_assignments(db, actor, row_id, rows, previous)
                # Assignment-only edits also advance the contract version.
                values.setdefault("end_date", row["end_date"])
        if table == "leases" and row["status"] == "DRAFT":
            check_lease_period(db, merged)
        update(db, actor, table, row, values)
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
        for first, last in (
            ("signed_date", "actual_move_in_date"), ("actual_move_in_date", "termination_notice_date"),
            ("termination_notice_date", "scheduled_move_out_date"), ("termination_notice_date", "actual_move_out_date"),
            ("actual_move_in_date", "scheduled_end_date"), ("start_date", "actual_move_out_date"),
        ):
            ordered_dates(merged, first, last)
        if action == "move-in":
            occupied = db.execute(
                """SELECT id FROM leases WHERE tenant_id=? AND unit_id=? AND id<>?
                   AND status IN ('OCCUPIED','TERMINATION_PENDING') LIMIT 1""",
                (TENANT_ID, row["unit_id"], row["id"]),
            ).fetchone()
            if occupied:
                conflict("同じ部屋に退去前の賃貸借契約があります")
        check_lease_period(db, merged)

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
        if table == "management_contracts":
            rows = assignments(db, row_id)
            if action == "activate":
                if not rows:
                    invalid("有効化には部屋の割当が必要です")
                check_assignments(db, row, rows)
            elif action == "end":
                if not values.get("termination_reason"):
                    invalid("契約の終了理由を入力してください")
                values["end_date"] = values.get("end_date") or row["end_date"] or today
                ordered_dates(row | values, "start_date", "end_date")
                unit_locks(db, [item["unit_id"] for item in rows])
        if table == "applications":
            if action in {"reject", "withdraw"} and not values.get("cancellation_reason"):
                invalid("却下または取下げの理由を入力してください")
            if action in {"approve", "reject"}:
                values["screening_result"] = target
        if table == "leases":
            lease_transition(db, row, action, values, today)
        update(db, actor, table, row, dict(values, status=target))
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
        if table == "units":
            select += ", b.building_name"
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
                (*args, limit, offset),
            ).fetchall()
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
                """SELECT charge_code, charge_name FROM charge_types
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

    app.include_router(router)
