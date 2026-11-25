"""Batch A rental schema, sample data, and read-only dashboard endpoints."""

import json
import random
import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query

TENANT_ID = 1
JST = ZoneInfo("Asia/Tokyo")
LEGACY_SAMPLE_PREFIXES = (
    "/api/households", "/api/introductions", "/api/partners", "/api/referral-",
    "/api/construction", "/api/fee-", "/api/stage", "/api/negotiations", "/api/contracts",
    "/api/activities", "/api/negotiation-queue", "/api/consents", "/api/entitlements",
    "/api/data-corrections", "/api/dashboard/summary", "/api/dashboard/trends",
    "/api/management/overview", "/api/management/reports", "/api/report",
)

# Tables are declared in dependency order so reset can drop them in reverse order.
TABLE_DEFINITIONS = {
    "parties": """
        party_code VARCHAR(40) NOT NULL, party_type VARCHAR(24) NOT NULL,
        display_name VARCHAR(120) NOT NULL, name_kana VARCHAR(120), postal_code VARCHAR(20),
        address VARCHAR(255), phone VARCHAR(50), email VARCHAR(255), contact_person VARCHAR(120),
        remittance_destination_ref VARCHAR(120), status VARCHAR(24) NOT NULL, notes TEXT,
        UNIQUE (tenant_id, party_code)
    """,
    "buildings": """
        building_code VARCHAR(40) NOT NULL, building_name VARCHAR(120) NOT NULL,
        postal_code VARCHAR(20), address VARCHAR(255) NOT NULL, building_type VARCHAR(40) NOT NULL,
        structure_type VARCHAR(40), construction_month DATE, floor_count INT,
        management_start_date DATE, status VARCHAR(24) NOT NULL, notes TEXT,
        UNIQUE (tenant_id, building_code)
    """,
    "units": """
        building_id BIGINT NOT NULL, unit_number VARCHAR(24) NOT NULL, owner_party_id BIGINT NOT NULL,
        floor_number INT, floor_area DECIMAL(8,2), layout_type VARCHAR(24),
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
        start_date DATE NOT NULL, end_date DATE, previous_manager_name VARCHAR(120),
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
        payer_name VARCHAR(120) NOT NULL, payer_party_id BIGINT, payment_source VARCHAR(32) NOT NULL,
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


def ensure_rental_schema(db):
    db.executescript(RENTAL_SCHEMA)


def check_rental_reset_scope(db):
    for table in RENTAL_RESET_TABLES:
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
    if db.execute("SELECT id FROM parties WHERE tenant_id=? LIMIT 1", (TENANT_ID,)).fetchone():
        return
    if not staff:
        raise RuntimeError("Rental sample seeding requires a baseline staff account")
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
        applicant_id = party(f"APP-PARTY-{index}", f"サンプル申込者 {index}")
        insert("applications", application_code=f"APP-{index:02}", unit_id=unit_id,
               applicant_party_id=applicant_id, application_date=month, application_channel="SAMPLE",
               desired_move_in_date=_month_shift(month, 1), proposed_rent=rent, proposed_common_fee=common_fee,
               screening_result="APPROVED" if status == "APPROVED" else "PENDING",
               external_procedure_status="NOT_STARTED_SAMPLE", assigned_user_id=staff_id, status=status)

    # 19 complaints, 15 work orders (including F03), and six inspections.
    for index in range(19):
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


def register_rental_routes(app, connect, require_actor):
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

    @router.get("/buildings", dependencies=[Depends(require_staff)])
    def buildings(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
        with connect() as db:
            return db.execute(
                """SELECT id, building_code, building_name, address, building_type, status
                   FROM buildings WHERE tenant_id=? ORDER BY id LIMIT ? OFFSET ?""",
                (TENANT_ID, limit, offset),
            ).fetchall()

    @router.get("/units", dependencies=[Depends(require_staff)])
    def units(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
        with connect() as db:
            return db.execute(
                """SELECT u.id, u.building_id, b.building_name, u.unit_number, u.advertised_rent,
                          u.advertised_common_fee, u.management_status, u.occupancy_status
                   FROM units u JOIN buildings b ON b.tenant_id=u.tenant_id AND b.id=u.building_id
                   WHERE u.tenant_id=? ORDER BY u.id LIMIT ? OFFSET ?""",
                (TENANT_ID, limit, offset),
            ).fetchall()

    app.include_router(router)
