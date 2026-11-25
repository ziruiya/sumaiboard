import { useEffect, useState } from "react";
import { todayJst } from "./jst-date.js";

export const rentalPages = [
  ["dashboard", "ダッシュボード"],
  ["properties", "物件・部屋"],
  ["applications", "申込・契約"],
  ["rent", "家賃収納"],
  ["repairs", "修繕・苦情"],
  ["settlements", "オーナー精算"],
  ["funds", "分別管理"],
  ["owner-portal", "オーナーマイページ"],
];

const number = new Intl.NumberFormat("ja-JP");
const yen = new Intl.NumberFormat("ja-JP", { style: "currency", currency: "JPY" });
const percent = new Intl.NumberFormat("ja-JP", { style: "percent", maximumFractionDigits: 1 });
const pageSize = 50;

function useRentalData(apiBase, path) {
  const [result, setResult] = useState(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    fetch(`${apiBase}/api/rental/${path}`, { credentials: "include", signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("Rental request failed");
        return response.json();
      })
      .then((data) => {
        if (!controller.signal.aborted) setResult({ path, attempt, data });
      })
      .catch(() => {
        if (!controller.signal.aborted) setResult({ path, attempt, error: true });
      });
    return () => controller.abort();
  }, [apiBase, path, attempt]);
  return {
    ...(result?.path === path && result.attempt === attempt ? result : {}),
    retry: () => setAttempt((current) => current + 1),
  };
}

function RentalResult({ result, children }) {
  if (result.error) return <div className="panel" role="alert">
    データを取得できませんでした。
    <button className="secondary-btn" type="button" onClick={result.retry}>再試行</button>
  </div>;
  if (!result.data) return <p role="status">読み込み中…</p>;
  return children(result.data);
}

function RentalDashboard({ apiBase, onNavigate }) {
  const result = useRentalData(apiBase, "summary");
  return <RentalResult result={result}>{(data) => <div className="rental-stack">
    <p className="muted">集計月 {data.service_month.slice(0, 7)}</p>
    <div className="rental-metrics">
      <button type="button" className="secondary-btn rental-metric rental-metric-action"
        onClick={() => onNavigate("rent", "請求")}>
        <span>当月請求分未収</span>
        <strong>{yen.format(data.outstanding_amount)}</strong>
        <span>{number.format(data.outstanding_charge_count)} 件</span>
      </button>
      <button type="button" className="secondary-btn rental-metric rental-metric-action"
        onClick={() => onNavigate("rent", "入金")}>
        <span>未消込入金</span><strong>{number.format(data.unallocated_payment_count)} 件</strong>
      </button>
      <button type="button" className="secondary-btn rental-metric rental-metric-action"
        onClick={() => onNavigate("settlements")}>
        <span>精算承認待ち</span><strong>{number.format(data.pending_settlement_approval_count)} 件</strong>
      </button>
      <div className="panel rental-metric">
        <span>緊急の修繕・苦情</span>
        <button type="button" className="secondary-btn" onClick={() => onNavigate("repairs", "work-orders")}>
          修繕 {number.format(data.urgent_work_order_count)} 件
        </button>
        <button type="button" className="secondary-btn" onClick={() => onNavigate("repairs", "complaints")}>
          苦情 {number.format(data.urgent_complaint_count)} 件
        </button>
      </div>
    </div>
    <div className="rental-metrics">
      {[
        ["当月請求額", yen.format(data.billed_amount)],
        ["当月請求分消込額", yen.format(data.allocated_amount)],
        ["物件数", `${number.format(data.building_count)} 棟`],
        ["部屋数", `${number.format(data.unit_count)} 室`],
        ["入居率", percent.format(data.occupancy_rate)],
      ].map(([label, value]) => <div className="panel rental-metric" key={label}>
        <span>{label}</span><strong>{value}</strong>
        {label === "入居率" && <small>{data.occupied_unit_count} / {data.managed_unit_count} 管理戸数</small>}
      </div>)}
    </div>
  </div>}</RentalResult>;
}

export default function RentalPage({ page, apiBase, accountRole, userId, view, onNavigate }) {
  const title = rentalPages.find(([id]) => id === page)?.[1];
  if (!title) return null;
  return <section className="rental-page">
    <h1>{page === "dashboard" ? "管理業務ダッシュボード" : title}</h1>
    {page === "dashboard" ? <RentalDashboard apiBase={apiBase} onNavigate={onNavigate}/>
      : page === "properties" ? <RentalProperties apiBase={apiBase}/>
        : page === "applications" ? <RentalPipeline apiBase={apiBase}/>
          : page === "rent" ? <RentalRent apiBase={apiBase} initialView={view === "入金" ? view : "請求"}/>
            : page === "repairs" ? <RentalRepairs apiBase={apiBase} initialTab={view === "complaints" ? view : "work-orders"}/>
            : page === "settlements" ? <RentalSettlements apiBase={apiBase} accountRole={accountRole} userId={userId}/>
              : page === "funds" ? <RentalFunds apiBase={apiBase}/>
              : accountRole === "owner" ? <OwnerPortal apiBase={apiBase}/> : null}
  </section>;
}

const statuses = {
  ACTIVE: "有効", INACTIVE: "無効", DRAFT: "下書き", RETIRED: "廃止", ENDED: "終了", CANCELLED: "取消",
  VACANT: "空室", APPLYING: "申込中", CONTRACTING: "契約手続中", OCCUPIED: "入居中",
  TERMINATION_PENDING: "解約予定", MANAGED: "管理中", UNMANAGED: "管理対象外",
  RECEIVED: "受付", SCREENING: "審査中", APPROVED: "承認", CONTRACTED: "契約作成済み",
  REJECTED: "却下", WITHDRAWN: "取下げ", SIGNED: "署名記録済み", PENDING: "未確定",
  NOT_STARTED_SAMPLE: "未着手（サンプル）", IN_PROGRESS_SAMPLE: "手続き中（サンプル）",
  RECORDED_SAMPLE: "記録済み（サンプル）", CASH_COLLECTED: "実収納基準",
  FLOOR: "切捨て", ACTUAL_DAYS_FLOOR: "当月の実日数・円未満切捨て",
  OWN_SALE: "自社売買", OTHER_PURCHASE: "他社購入", INHERITANCE: "相続",
  MANAGEMENT_TRANSFER: "管理移管", OTHER: "その他", COMPANY: "管理会社", OWNER: "オーナー",
  individual: "個人", company: "法人", STANDARD: "普通借家", FIXED_TERM: "定期借家",
  APARTMENT: "共同住宅", HOUSE: "戸建て", SAMPLE: "サンプル受付",
  RENT: "家賃", COMMON_FEE: "共益費", KEY_MONEY: "礼金", DEPOSIT: "敷金",
  RENEWAL: "更新料", RENEWAL_ADMIN: "更新事務手数料", BROKERAGE: "仲介手数料",
  MANAGEMENT: "管理料", REPAIR: "修繕費",
  ESTIMATED: "見積済み", ARRANGED: "手配済み", COMPLETED: "作業完了", INSPECTED: "検収済み",
  COST_CONFIRMED: "費用確定", CLOSED: "終了", OPEN: "受付", IN_PROGRESS: "対応中", RESOLVED: "解決済み",
  URGENT: "緊急", HIGH: "高", NORMAL: "通常", LOW: "低", TENANT: "入居者",
  EQUIPMENT: "設備", NOISE: "騒音", REPAIR_ACCEPTANCE: "修繕検収", ROUTINE: "通常点検",
  PASS: "合格", FAIL: "要対応",
};

const unitStates = [["management_status", "管理状態"], ["occupancy_status", "入居状態"]];
const cancelLease = ["cancel", "契約を取り消す", [["cancellation_reason", "取消理由"]]];
const occupation = ["VACANT", "APPLYING", "CONTRACTING", "OCCUPIED", "TERMINATION_PENDING"];
const outside = ["NOT_STARTED_SAMPLE", "IN_PROGRESS_SAMPLE", "RECORDED_SAMPLE"];
const disclaimer = "本画面は外部サービスの利用を想定したデモです。実際のAPI連携・電子署名は行っていません。";
const resources = {
  buildings: {
    label: "建物", name: (row) => row.building_name, summary: (row) => row.address,
    fields: [
      ["building_code", "物件コード"], ["building_name", "建物名"], ["address", "住所"],
      ["building_type", "建物種別", ["APARTMENT", "HOUSE", "OTHER"]], ["postal_code", "郵便番号", "optional"],
      ["structure_type", "構造", "optional"], ["construction_month", "建築年月", "month"],
      ["floor_count", "階数", "optionalInteger"], ["management_start_date", "管理開始日", "optionalDate"],
      ["status", "状態", ["ACTIVE", "INACTIVE"]], ["notes", "備考", "notes"],
    ],
  },
  units: {
    label: "部屋", name: (row) => `${row.building_name || ""} ${row.unit_number}号室`.trim(),
    summary: (row) => yen.format(row.advertised_rent),
    fields: [
      ["building_id", "建物", "@buildings"], ["unit_number", "部屋番号"], ["owner_party_id", "オーナー", "@parties"],
      ["advertised_rent", "募集家賃（円）", "integer"], ["advertised_common_fee", "募集共益費（円）", "integer"],
      ["floor_number", "階", "optionalInteger"], ["floor_area", "面積（㎡）", "decimal"],
      ["layout_type", "間取り", "optional"], ["notes", "備考", "notes"],
    ],
  },
  parties: {
    label: "オーナー", name: (row) => row.display_name, summary: (row) => row.party_code,
    fields: [
      ["party_type", "区分", ["individual", "company"]], ["display_name", "氏名・名称"],
      ["name_kana", "フリガナ", "optional"], ["postal_code", "郵便番号", "optional"],
      ["address", "住所", "optional"], ["phone", "電話番号", "optional"], ["email", "メールアドレス", "optional"],
      ["contact_person", "担当者", "optional"], ["remittance_destination_ref", "送金先参照", "optional"], ["notes", "備考", "notes"],
    ],
  },
  "management-contracts": {
    label: "管理契約", name: (row) => row.contract_code, summary: (row) => row.display_name,
    fields: [
      ["contract_code", "管理契約コード"], ["owner_party_id", "オーナー", "@parties"],
      ["principal_party_id", "委託者", "@parties"], ["payee_party_id", "送金先関係者", "@parties"],
      ["acquisition_channel", "受託経路", ["OWN_SALE", "OTHER_PURCHASE", "INHERITANCE", "MANAGEMENT_TRANSFER", "OTHER"]],
      ["accepted_date", "受託日", "date"], ["acquired_date", "取得日", "optionalDate"],
      ["start_date", "開始日", "date"], ["end_date", "終了日", "optionalDate"],
      ["previous_manager_name", "前管理会社", "optional"], ["assigned_user_id", "担当者", "@staff"],
      ["remittance_day", "送金日", "integer"], ["deposit_custodian", "敷金保管者", ["COMPANY", "OWNER", "OTHER"]],
      ["fee_plan_id", "管理料プラン", "@fee-plans"], ["notes", "備考", "notes"],
    ],
  },
  "fee-plans": {
    label: "管理料プラン", name: (row) => row.plan_name,
    summary: (row) => `${row.plan_code} · ${percent.format(row.rate)}`,
    fields: [
      ["plan_code", "プランコード"], ["plan_name", "プラン名"], ["plan_version", "プラン版", "integer"],
      ["rate", "管理料率（5% は 0.05）", "decimal"], ["calculation_basis", "計算基準", ["CASH_COLLECTED"]],
      ["included_charge_types", "対象費目", "charges"], ["tax_inclusive", "税込", "boolean"],
      ["tax_rate", "消費税率（10% は 0.10）", "decimal"], ["vacancy_exempt", "空室免除", "boolean"],
      ["rounding_rule", "端数処理", ["FLOOR"]], ["minimum_fee", "最低管理料（円）", "integer"],
      ["effective_from", "適用開始日", "date"], ["effective_to", "適用終了日", "optionalDate"],
    ],
  },
  applications: {
    label: "申込", name: (row) => row.application_code,
    summary: (row) => `${row.display_name} · ${row.building_name} ${row.unit_number}号室`,
    fields: [
      ["application_code", "申込コード"], ["unit_id", "部屋", "@units"], ["applicant_party_id", "申込者", "@parties"],
      ["application_date", "受付日", "date"], ["application_channel", "受付経路"],
      ["desired_move_in_date", "入居希望日", "date"], ["proposed_rent", "申込家賃（円）", "integer"],
      ["proposed_common_fee", "申込共益費（円）", "integer"], ["assigned_user_id", "担当者", "@staff"],
      ["external_procedure_status", "外部手続きの状況", outside], ["external_reference", "外部参照", "optional"],
      ["notes", "備考", "notes"],
    ],
  },
  leases: {
    label: "賃貸借契約", name: (row) => row.lease_code,
    summary: (row) => `${row.display_name} · ${row.building_name} ${row.unit_number}号室`,
    fields: [
      ["lease_code", "賃貸借契約コード"], ["unit_id", "部屋", "@units"], ["tenant_party_id", "入居者", "@parties"],
      ["guarantor_party_id", "保証人・保証会社", "@parties?"], ["contract_type", "契約種別", ["STANDARD", "FIXED_TERM", "OTHER"]],
      ["start_date", "開始日", "date"], ["scheduled_end_date", "満了予定日", "optionalDate"],
      ["rent_amount", "家賃（円）", "integer"], ["common_fee_amount", "共益費（円）", "integer"],
      ["deposit_amount", "敷金（円）", "integer"], ["key_money_amount", "礼金（円）", "integer"],
      ["payment_due_day", "支払日", "integer"], ["proration_rule", "日割", ["ACTUAL_DAYS_FLOOR"]],
      ["external_signature_status", "外部署名手続きの状況", outside],
    ],
  },
  staff: { name: (row) => row.display_name },
};

const actionSpec = {
  parties: { ACTIVE: [["inactivate", "無効化"]] },
  "fee-plans": { DRAFT: [["activate", "有効化"]], ACTIVE: [["retire", "廃止"]] },
  "management-contracts": {
    DRAFT: [["activate", "有効化"], ["cancel", "下書き取消"]],
    ACTIVE: [["end", "契約を終了", [["end_date", "終了日", "optionalDate"], ["termination_reason", "終了理由"]]]],
  },
  applications: {
    RECEIVED: [["screen", "審査を開始", [["notes", "審査記録", "notes"]]], ["withdraw", "取下げ", [["cancellation_reason", "取下げ理由"]]]],
    SCREENING: [["approve", "承認", [["notes", "審査記録", "notes"]]], ["reject", "却下", [["cancellation_reason", "却下理由"]]],
      ["withdraw", "取下げ", [["cancellation_reason", "取下げ理由"]]]],
    APPROVED: [["create-lease", "契約を作成"], ["withdraw", "取下げ", [["cancellation_reason", "取下げ理由"]]]],
  },
  leases: {
    DRAFT: [["sign", "署名日を記録", [["signed_date", "署名日", "optionalDate"]]], cancelLease],
    SIGNED: [["move-in", "入居を記録", [["actual_move_in_date", "入居日", "optionalDate"]]], cancelLease],
    OCCUPIED: [["notice", "解約予告を記録", [
      ["termination_notice_date", "解約予告日", "optionalDate"], ["scheduled_move_out_date", "退去予定日", "date"],
      ["termination_reason", "解約理由", "optional"],
    ]]],
    TERMINATION_PENDING: [["move-out", "退去を記録", [["actual_move_out_date", "退去日", "optionalDate"]]]],
  },
};
const snapshotLabels = [
  ["plan_code", "プランコード"], ["plan_version", "プラン版"], ["rate", "管理料率", "rate"],
  ["calculation_basis", "計算基準"], ["tax_inclusive", "税込"], ["tax_rate", "消費税率", "rate"],
  ["vacancy_exempt", "空室免除"], ["rounding_rule", "端数処理"], ["minimum_fee", "最低管理料", "money"],
  ["included_charge_types", "対象費目"],
];
const assignmentFields = [["unit_id", "部屋", "@units"], ["valid_from", "割当開始日", "date"], ["valid_to", "割当終了日", "optionalDate"]];
const copiedLeaseFields = ["unit_id", "tenant_party_id", "start_date", "rent_amount", "common_fee_amount"];

function showValue(value, kind) {
  if (value == null || value === "") return "—";
  if (kind === "rate") return percent.format(value);
  if (kind === "money") return yen.format(value);
  if (Array.isArray(value)) return value.map((item) => statuses[item] || item).join("、");
  if (typeof value === "boolean") return value ? "あり" : "なし";
  return statuses[value] || value;
}

function RecordValues({ row, fields }) {
  return <dl className="rental-values">{fields.map(([key, label, kind]) =>
    <div key={key}><dt>{label}</dt><dd>{showValue(row[key], kind)}</dd></div>)}</dl>;
}

function Pager({ offset, count, setOffset }) {
  if (!offset && count < pageSize) return null;
  return <div className="rental-controls">
    <button type="button" className="secondary-btn" disabled={offset === 0}
      onClick={() => setOffset(offset - pageSize)}>前へ</button>
    <button type="button" className="secondary-btn" disabled={count < pageSize}
      onClick={() => setOffset(offset + pageSize)}>次へ</button>
  </div>;
}

function ReferenceField({ apiBase, label, resource, value, setValue, optional, buildingId }) {
  const [offset, setOffset] = useState(0);
  const [selectedLabel, setSelectedLabel] = useState("");
  const filter = resource === "fee-plans" ? "&status=ACTIVE"
    : resource === "units" && buildingId ? `&building_id=${buildingId}` : "";
  const result = useRentalData(apiBase, `${resource}?limit=${pageSize}&offset=${offset}${filter}`);
  const rows = result.data || [];
  return <div>
    <label>{label}<select value={value ?? ""} required={!optional} onChange={(event) => {
      const selected = rows.find(({ id }) => id === Number(event.target.value));
      setSelectedLabel(selected ? resources[resource].name(selected) : "");
      setValue(event.target.value ? Number(event.target.value) : null);
    }}>
      <option value="">選択してください</option>
      {value && !rows.some(({ id }) => id === value) &&
        <option value={value}>{selectedLabel || `登録済み（ID ${value}）`}</option>}
      {rows.map((row) => <option key={row.id} value={row.id}>{resources[resource].name(row)}</option>)}
    </select></label>
    {result.error ? <button className="secondary-btn" type="button" onClick={result.retry}>候補の取得を再試行</button>
      : !result.data && <small role="status">候補を読み込み中…</small>}
    <Pager offset={offset} count={rows.length} setOffset={setOffset}/>
  </div>;
}

function ChargeSelection({ apiBase, value = [], setValue }) {
  const result = useRentalData(apiBase, "charge-types");
  return <RentalResult result={result}>{(rows) => <fieldset>
    <legend>対象費目</legend>
    {rows.length === 0 && <p>対象費目が登録されていません。</p>}
    {rows.map(({ charge_code: code, charge_name: name }) => <label className="rental-check" key={code}>
      <input type="checkbox" checked={value.includes(code)}
        onChange={(e) => setValue(e.target.checked ? [...value, code] : value.filter((item) => item !== code))}/>
      {name}
    </label>)}
  </fieldset>}</RentalResult>;
}

function RentalField({ apiBase, field, value, setValue, buildingId }) {
  const [, label, kind] = field;
  if (Array.isArray(kind)) return <label>{label}<select required value={value ?? ""} onChange={(e) => setValue(e.target.value)}>
    <option value="">選択してください</option>
    {value && !kind.includes(value) && <option value={value}>{showValue(value)}</option>}
    {kind.map((choice) => <option key={choice} value={choice}>{showValue(choice)}</option>)}
  </select></label>;
  if (kind?.startsWith("@")) return <ReferenceField apiBase={apiBase} label={label} resource={kind.slice(1).replace("?", "")}
    optional={kind.endsWith("?")} value={value} setValue={setValue} buildingId={buildingId}/>;
  if (kind === "charges") return <ChargeSelection apiBase={apiBase} value={value} setValue={setValue}/>;
  if (kind === "notes" || kind === "requiredNotes") return <label>{label}<textarea required={kind === "requiredNotes"} value={value ?? ""} onChange={(e) => setValue(e.target.value || null)}/></label>;
  if (kind === "boolean") return <label className="rental-check">
    <input type="checkbox" checked={Boolean(value)} onChange={(e) => setValue(e.target.checked)}/>{label}
  </label>;
  const integer = kind === "integer" || kind === "optionalInteger";
  const type = integer ? "number" : kind === "date" || kind === "optionalDate" ? "date" : kind === "month" ? "month" : kind === "datetime" ? "datetime-local" : "text";
  const required = !kind?.startsWith("optional") && kind !== "month" && (kind !== "decimal" || field[0] !== "floor_area");
  return <label>{label}<input type={type} inputMode={kind === "decimal" ? "decimal" : undefined}
    required={required} value={kind === "month" ? value?.slice(0, 7) ?? "" : value ?? ""}
    onChange={(e) => {
      const next = e.target.value;
      setValue(next ? (integer ? Number(next) : kind === "month" ? `${next}-01` : next) : null);
    }}/></label>;
}

function PlanPreview({ apiBase, planId, snapshot }) {
  if (snapshot) return <div><h3>契約に保存された管理料ルール</h3><RecordValues row={snapshot} fields={snapshotLabels}/></div>;
  if (!planId) return null;
  return <SelectedPlan apiBase={apiBase} planId={planId}/>;
}

function SelectedPlan({ apiBase, planId }) {
  const result = useRentalData(apiBase, `fee-plans/${planId}`);
  return <RentalResult result={result}>{(plan) => <div>
    <h3>契約に保存する管理料ルール</h3>
    <RecordValues row={plan} fields={snapshotLabels}/>
  </div>}</RentalResult>;
}

const newDefaults = {
  buildings: { status: "ACTIVE" },
  parties: { party_type: "individual" },
  units: { management_status: "UNMANAGED", occupancy_status: "VACANT", advertised_common_fee: 0 },
  "fee-plans": { plan_version: 1, calculation_basis: "CASH_COLLECTED", rounding_rule: "FLOOR",
    tax_inclusive: true, tax_rate: "0.10", vacancy_exempt: false, minimum_fee: 0, included_charge_types: [] },
  applications: { external_procedure_status: outside[0], proposed_common_fee: 0 },
  leases: { contract_type: "STANDARD", proration_rule: "ACTUAL_DAYS_FLOOR",
    external_signature_status: outside[0], deposit_amount: 0, key_money_amount: 0 },
};

function formFields(resource, record, action) {
  if (action) {
    if (action[0] === "create-lease") return resources.leases.fields.filter(([key]) => !copiedLeaseFields.includes(key));
    return action[2] || [];
  }
  return resources[resource].fields.filter(([key]) => {
    if (!record) return true;
    if (resource === "fee-plans") return key !== "plan_version";
    if (resource === "management-contracts") return key !== "fee_plan_id"
      && (record.status !== "ACTIVE" || !["owner_party_id", "principal_party_id", "payee_party_id", "start_date"].includes(key));
    if (resource === "applications") return ["CONTRACTED", "WITHDRAWN", "REJECTED"].includes(record.status)
      ? ["external_procedure_status", "external_reference", "notes"].includes(key)
      : !["unit_id", "applicant_party_id"].includes(key);
    if (resource === "leases") {
      if (record.status !== "DRAFT") return key === "external_signature_status";
      return key !== "unit_id" && (!record.application_id || key !== "tenant_party_id");
    }
    return true;
  });
}

function RentalForm({ apiBase, resource, record, action, preset, onSaved, onCancel, onReload }) {
  const fields = formFields(resource, record, action);
  const [values, setValues] = useState(() => action?.[0] === "create-lease"
    ? { ...newDefaults.leases, lease_code: `LEASE-${record.id}` }
    : action ? Object.fromEntries(fields.filter(([key]) => record[key] != null).map(([key]) => [key, record[key]]))
      : record || { ...newDefaults[resource], ...preset });
  const [assignments, setAssignments] = useState(() => (record?.units || []).filter((row) => !row.valid_to || row.valid_to >= row.valid_from).map((row) => ({
    key: row.id, unit_id: row.unit_id, valid_from: row.valid_from, valid_to: row.valid_to,
  })));
  const [failure, setFailure] = useState(null);
  const [busy, setBusy] = useState(false);
  const editingAssignments = resource === "management-contracts" && !action;
  const title = action?.[1] || `${resources[resource].label}を${record ? "編集" : "登録"}`;

  async function save(event) {
    event.preventDefault();
    setFailure(null);
    setBusy(true);
    const payload = Object.fromEntries(fields.filter(([key]) => values[key] !== undefined).map(([key]) => [key, values[key]]));
    if (record) payload.version = record.version;
    if (editingAssignments) payload.units = assignments.map(({ unit_id, valid_from, valid_to }) => ({ unit_id, valid_from, valid_to }));
    const path = record ? `${resource}/${record.id}${action ? `/${action[0]}` : ""}` : resource;
    try {
      const response = await fetch(`${apiBase}/api/rental/${path}`, {
        method: record && !action ? "PUT" : "POST", credentials: "include",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) {
        setFailure({ status: response.status, message: typeof data.detail === "string" ? data.detail : "入力内容を確認してください。" });
        return;
      }
      onSaved(data, action?.[0] === "create-lease" ? "leases" : action?.[0] === "create-work-order" ? "work-orders" : resource);
    } catch {
      setFailure({ message: "保存できませんでした。通信状況を確認してください。" });
    } finally {
      setBusy(false);
    }
  }

  return <form className="panel rental-form" onSubmit={save}>
    <h2>{title}</h2>
    {resource === "units" && <RecordValues row={values} fields={unitStates}/>}
    {action?.[0] === "create-lease" && <RecordValues row={record} fields={[
      ["desired_move_in_date", "契約開始日"], ["proposed_rent", "家賃", "money"], ["proposed_common_fee", "共益費", "money"],
    ]}/>}
    <div className="rental-fields">{fields.map((field) => {
      const [key] = field;
      const caseUnit = key === "unit_id" && resource in caseResources;
      if (caseUnit && !values.building_id) return null;
      return <RentalField key={caseUnit ? `unit-${values.building_id}` : key} apiBase={apiBase} field={field}
        buildingId={caseUnit ? values.building_id : undefined} value={values[key]}
        setValue={(value) => setValues((current) => ({
          ...current, ...(key === "building_id" && resource in caseResources ? { unit_id: null } : {}), [key]: value,
        }))}/>;
    })}</div>
    {editingAssignments && <>
      <PlanPreview apiBase={apiBase} planId={values.fee_plan_id} snapshot={record?.fee_plan_snapshot}/>
      <fieldset><legend>部屋の割当</legend>
        {assignments.length === 0 && <p>割当はありません。</p>}
        {assignments.map((row) => <div className="rental-fields rental-assignment" key={row.key}>
          {assignmentFields.map((field) => <RentalField key={field[0]} apiBase={apiBase} field={field}
            value={row[field[0]]} setValue={(value) => setAssignments((current) => current.map((item) =>
              item.key === row.key ? { ...item, [field[0]]: value } : item))}/>)}
          <button type="button" className="secondary-btn" onClick={() =>
            setAssignments((current) => current.filter(({ key }) => key !== row.key))}>この割当を外す</button>
        </div>)}
        <button type="button" className="secondary-btn" disabled={assignments.length >= 100}
          onClick={() => setAssignments((current) => [...current, { key: globalThis.crypto.randomUUID(), valid_from: values.start_date }])}>
          部屋を追加
        </button>
      </fieldset>
    </>}
    {failure && <div role="alert" className="rental-error">{failure.message}
      {failure.status === 409 && record &&
        <button type="button" className="secondary-btn" onClick={onReload}>最新のデータを読み込む</button>}
    </div>}
    <div className="rental-controls">
      <button type="submit" className="primary-btn" disabled={busy}>{busy ? "保存中…" : action?.[1] || "保存"}</button>
      <button type="button" className="secondary-btn" disabled={busy} onClick={onCancel}>戻る</button>
    </div>
  </form>;
}

function RoomMatrix({ apiBase, buildingId, open }) {
  const [offset, setOffset] = useState(0);
  const result = useRentalData(apiBase, `units?building_id=${buildingId}&limit=${pageSize}&offset=${offset}`);
  return <RentalResult result={result}>{(rows) => <>
    {rows.length === 0 ? <p>表示できる部屋がありません。</p> : <div className="rental-room-grid">
      {rows.map((row) => <button type="button" key={row.id} className="rental-room"
        data-state={row.occupancy_status} onClick={() => open("units", row.id)}>
        <strong>{row.unit_number}号室</strong><span>{showValue(row.occupancy_status)}</span>
      </button>)}
    </div>}
    <Pager offset={offset} count={rows.length} setOffset={setOffset}/>
  </>}</RentalResult>;
}

function RecordDetail({ apiBase, resource, row, open, create }) {
  const general = resources[resource].fields.filter(([key]) =>
    !["external_procedure_status", "external_reference", "external_signature_status", "notes"].includes(key))
    .map(([key, label, kind]) => [key, label.replace("（円）", ""),
      label.endsWith("（円）") ? "money" : key === "rate" || key === "tax_rate" ? "rate" : kind]);
  return <>
    <div className="panel">
      <h2>{resources[resource].name(row)}</h2>
      <RecordValues row={row} fields={resource === "units" ? [...general, ...unitStates] : general}/>
      {row.notes && resource !== "applications" && <p>{row.notes}</p>}
    </div>
    {resource === "buildings" && <div className="panel">
      <div className="rental-controls"><h3>部屋一覧（{row.unit_count}室）</h3>
        <button type="button" className="secondary-btn" onClick={() => create("units", { building_id: row.id })}>部屋を登録</button></div>
      <RecordValues row={row.occupancy_counts} fields={occupation.map((state) => [state, statuses[state]])}/>
      <RoomMatrix apiBase={apiBase} buildingId={row.id} open={open}/>
    </div>}
    {resource === "units" && <>
      <div className="panel"><h3>現在の管理契約</h3>
        {row.current_management_contract ? <>
          <button className="secondary-btn" type="button" onClick={() => open("management-contracts", row.current_management_contract.id)}>
            {row.current_management_contract.contract_code}
          </button>
          <RecordValues row={row.current_management_contract} fields={[["status", "状態"], ["start_date", "開始日"], ["end_date", "終了日"]]}/>
        </> : <p>現在有効な管理契約はありません。</p>}
      </div>
      <div className="panel"><h3>現在の賃貸借契約</h3>
        {row.current_lease ? <>
          <button className="secondary-btn" type="button" onClick={() => open("leases", row.current_lease.id)}>{row.current_lease.lease_code}</button>
          <RecordValues row={row.current_lease} fields={[["status", "状態"], ["start_date", "開始日"], ["rent_amount", "家賃", "money"]]}/>
        </> : <p>現在の賃貸借契約はありません。</p>}
      </div>
      <div className="panel"><h3>直近の修繕履歴</h3>
        {row.recent_repairs.length ? <ul>{row.recent_repairs.map((item) => <li key={item.id}>
          {item.received_date}　{item.work_order_code}　{item.description}
        </li>)}</ul> : <p>修繕履歴はありません。</p>}
      </div>
    </>}
    {resource === "management-contracts" && <div className="panel">
      <PlanPreview apiBase={apiBase} snapshot={row.fee_plan_snapshot}/>
      <h3>部屋の割当</h3>
      {row.units.length ? <ul>{row.units.map((item) => <li key={item.id}>
        <button type="button" className="secondary-btn" onClick={() => open("units", item.unit_id)}>{resources.units.name(item)}</button>
        {" "}{item.valid_to && item.valid_to < item.valid_from ? "有効期間なし" : `${item.valid_from} ～ ${item.valid_to || "期限なし"}`}
      </li>)}</ul> : <p>割当はありません。</p>}
      {row.termination_reason && <RecordValues row={row} fields={[["termination_reason", "終了理由"]]}/>}
    </div>}
    {resource === "applications" && <>
      <div className="panel"><h3>審査記録</h3>
        <RecordValues row={row} fields={[["screening_result", "審査結果"], ["notes", "記録"], ["cancellation_reason", "却下・取下げ理由"]]}/>
      </div>
      <div className="panel"><h3>外部手続き記録</h3>
        <RecordValues row={row} fields={[["external_procedure_status", "手続きの状況"], ["external_reference", "外部参照"]]}/>
      </div>
      {row.lease && <button type="button" className="secondary-btn"
        onClick={() => open("leases", row.lease.id)}>{row.lease.lease_code} を開く</button>}
    </>}
    {resource === "leases" && <>
      <div className="panel"><h3>契約履行記録</h3>
        <RecordValues row={row} fields={[
          ["signed_date", "署名日"], ["actual_move_in_date", "入居日"], ["termination_notice_date", "解約予告日"],
          ["scheduled_move_out_date", "退去予定日"], ["actual_move_out_date", "退去日"], ["termination_reason", row.status === "CANCELLED" ? "取消理由" : "解約理由"],
        ]}/>
      </div>
      <div className="panel"><h3>外部手続き記録</h3>
        <RecordValues row={row} fields={[["external_signature_status", "署名手続きの状況"]]}/>
      </div>
      {row.application_id && <button type="button" className="secondary-btn" onClick={() => open("applications", row.application_id)}>元の申込を開く</button>}
    </>}
  </>;
}

function RentalDetail({ apiBase, view, onSaved, open, create }) {
  const { resource, id } = view;
  const result = useRentalData(apiBase, `${resource}/${id}`);
  const [form, setForm] = useState(null);
  return <RentalResult result={result}>{(row) => form ? <RentalForm apiBase={apiBase} resource={resource}
    record={row} action={form.action} onSaved={(...args) => { setForm(null); result.retry(); onSaved(...args); }}
    onCancel={() => setForm(null)} onReload={() => { setForm(null); result.retry(); }}/>
    : <div className="rental-stack">
      <div className="rental-controls">
        {row.status && <strong>{showValue(row.status)}</strong>}
        {!(resource === "management-contracts" && ["ENDED", "CANCELLED"].includes(row.status)) &&
          <button type="button" className="secondary-btn" onClick={() => setForm({})}>編集</button>}
        {(actionSpec[resource]?.[row.status] || []).map((action) => <button key={action[0]} type="button"
          className="secondary-btn" onClick={() => setForm({ action })}>{action[1]}</button>)}
      </div>
      <RecordDetail apiBase={apiBase} resource={resource} row={row} open={open} create={create}/>
    </div>}</RentalResult>;
}

const pipelineStates = {
  applications: ["RECEIVED", "SCREENING", "APPROVED", "CONTRACTED", "REJECTED", "WITHDRAWN"],
  leases: ["DRAFT", "SIGNED", "OCCUPIED", "TERMINATION_PENDING", "ENDED"],
};

function RentalList({ apiBase, resource, open, create, createApplicant }) {
  const [offset, setOffset] = useState(0);
  const [state, setState] = useState("");
  const filters = resource === "units" ? occupation : pipelineStates[resource];
  const query = new URLSearchParams({ limit: pageSize, offset });
  if (state) query.set(resource === "units" ? "occupancy_status" : "status", state);
  if (resource === "parties") query.set("owner_only", "true");
  const result = useRentalData(apiBase, `${resource}?${query}`);
  const config = resources[resource];
  return <div className="rental-stack">
    <div className="rental-controls">
      <button type="button" className="primary-btn" onClick={() => create(resource)}>{config.label}を登録</button>
      {resource === "applications" && <button type="button" className="secondary-btn" onClick={createApplicant}>申込者を登録</button>}
      {filters && <label>状態 <select value={state} onChange={(e) => { setState(e.target.value); setOffset(0); }}>
        <option value="">すべて</option>{filters.map((status) =>
          <option key={status} value={status}>{showValue(status)}</option>)}
      </select></label>}
    </div>
    <RentalResult result={result}>{(rows) => <>
      {rows.length ? <ul className="panel rental-list">{rows.map((row) => <li key={row.id}>
        <button type="button" className="rental-list-button" onClick={() => open(resource, row.id)}>
          <span><strong>{config.name(row)}</strong><small>{config.summary(row)}</small></span>
          <span>{showValue(row.occupancy_status || row.status)}</span>
        </button>
      </li>)}</ul> : <p>表示できるデータがありません。</p>}
      <Pager offset={offset} count={rows.length} setOffset={setOffset}/>
    </>}</RentalResult>
  </div>;
}

function RentalWorkspace({ apiBase, tabs, pipeline }) {
  const [tab, setTab] = useState(tabs[0]);
  const [history, setHistory] = useState([]);
  const view = history.at(-1);
  const open = (resource, id) => setHistory((current) => [...current, { resource, id }]);
  const create = (resource, preset) => setHistory((current) => [...current, { resource, preset }]);
  const back = () => setHistory((current) => current.slice(0, -1));
  const saved = (row, resource) => setHistory((current) => {
    if (current.at(-1)?.applicant) {
      return [...current.slice(0, -1), { resource: "applications", preset: { applicant_party_id: row.id } }];
    }
    if (current.at(-1)?.id && current.at(-1)?.resource !== resource) return [...current, { resource, id: row.id }];
    return [...current.slice(0, -1), { resource, id: row.id }];
  });
  return <div className="rental-stack">
    {(pipeline || pipelineStates[view?.resource]) && <p className="panel rental-disclaimer">{disclaimer}</p>}
    <nav className="rental-controls" aria-label="表示対象">{tabs.map((resource) =>
      <button className="secondary-btn" type="button" key={resource} aria-pressed={!view && resource === tab}
        onClick={() => { setTab(resource); setHistory([]); }}>{resources[resource].label}</button>)}</nav>
    {view?.id && <div><button className="secondary-btn" type="button" onClick={back}>戻る</button></div>}
    {view ? view.id ? <RentalDetail key={`${view.resource}:${view.id}`} apiBase={apiBase}
      view={view} onSaved={saved} open={open} create={create}/>
      : <RentalForm key={view.resource} apiBase={apiBase} resource={view.resource} preset={view.preset}
        onSaved={saved} onCancel={back}/>
      : <RentalList key={tab} apiBase={apiBase} resource={tab} open={open} create={create}
        createApplicant={() => setHistory([{ resource: "parties", applicant: true }])}/>}
  </div>;
}

function RentalProperties({ apiBase }) {
  return <RentalWorkspace apiBase={apiBase} tabs={["buildings", "units", "parties", "management-contracts", "fee-plans"]}/>;
}

function RentalPipeline({ apiBase }) {
  return <RentalWorkspace apiBase={apiBase} tabs={["applications", "leases"]} pipeline/>;
}

const moneyStatuses = {
  UNPAID: "未収", PARTIALLY_PAID: "一部入金", PAID: "入金済み", CANCELLED: "取消済み",
  UNALLOCATED: "未消込", PARTIALLY_ALLOCATED: "一部消込", ALLOCATED: "消込済み", REVERSED: "取消済み",
};

const fundCategoryNames = {
  OWNER_RENT: "オーナー家賃", OWNER_OTHER: "オーナーその他収入", DEPOSIT: "敷金預り",
  UNALLOCATED: "未消込", UNIDENTIFIED: "未識別", COMPANY_FUNDS: "自社資金",
};

function useMoneyAction(apiBase) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(path, payload, done) {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/api/rental/${path}`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) {
        setError(typeof data.detail === "string" ? data.detail : "入力内容を確認してください。");
        return;
      }
      done(data);
    } catch {
      setError("通信状況を確認して再試行してください。");
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, submit };
}

function MoneyError({ action, refresh }) {
  if (!action.error) return null;
  return <p role="alert" className="rental-error">{action.error}
    {refresh && <button type="button" className="secondary-btn" onClick={refresh}>再読み込み</button>}
  </p>;
}

function MoneyList({ rows, render, empty = "表示できるデータがありません。" }) {
  return rows.length ? <ul className="panel rental-list">{rows.map((row) =>
    <li key={row.id ?? row.lease_id}>{render(row)}</li>)}</ul> : <p>{empty}</p>;
}

function MoneyRow({ title, description, balance, onClick, selected, actionLabel }) {
  const contents = <>
    <span><strong>{title}</strong><small>{description}</small></span><span>{balance}{onClick && actionLabel && <small>{actionLabel}</small>}</span>
  </>;
  return onClick
    ? <button type="button" className="rental-list-button" onClick={onClick} aria-pressed={selected}>{contents}</button>
    : <div className="rental-money-row">{contents}</div>;
}

function MoneyReasonForm({ apiBase, path, title, versions, saved, close, refresh, idempotent = false }) {
  const action = useMoneyAction(apiBase);
  const [reason, setReason] = useState("");
  const [retry, setRetry] = useState(null);
  return <form className="panel rental-form" onSubmit={(event) => {
    event.preventDefault();
    const payload = { ...versions, reason: reason.trim() };
    if (idempotent) {
      const key = retry?.reason === payload.reason ? retry.key : crypto.randomUUID();
      setRetry({ reason: payload.reason, key });
      payload.idempotency_key = key;
    }
    action.submit(path, payload, saved);
  }}>
    <h3>{title}</h3>
    <div className="rental-fields">
      <label>取消理由<input required value={reason} onChange={(event) => setReason(event.target.value)}/></label>
    </div>
    <MoneyError action={action} refresh={refresh}/>
    <div className="rental-controls">
      <button className="primary-btn" disabled={action.busy || !reason.trim()}>取消を確定</button>
      <button type="button" className="secondary-btn" disabled={action.busy} onClick={close}>戻る</button>
    </div>
  </form>;
}

function RentCharges({ apiBase }) {
  const [month, setMonth] = useState(() => todayJst().slice(0, 7));
  const [offset, setOffset] = useState(0);
  const [generated, setGenerated] = useState(null);
  const [cancel, setCancel] = useState(null);
  const action = useMoneyAction(apiBase);
  const data = useRentalData(apiBase, `charges?month=${month}&offset=${offset}`);
  return <div className="rental-stack">
    <div className="rental-controls">
      <label>所属月 <input type="month" value={month} onChange={(event) => {
        setMonth(event.target.value);
        setOffset(0);
        setGenerated(null);
        setCancel(null);
      }}/></label>
      <button type="button" className="primary-btn" disabled={!month || action.busy}
        onClick={() => action.submit("charges/generate", { service_month: month }, (result) => {
          setGenerated(result);
          data.retry();
        })}>月次請求を生成</button>
    </div>
    {generated?.service_month.slice(0, 7) === month && <p role="status">
      {generated.generated_count} 件生成・{generated.skipped_count} 件スキップ
      {generated.leases_without_management_contract > 0 && `（管理契約のない賃貸借契約 ${generated.leases_without_management_contract} 件）`}
      {generated.skip_reasons.MANAGEMENT_CHANGED_MIDMONTH > 0 &&
        `（月中に管理契約が変更 ${generated.skip_reasons.MANAGEMENT_CHANGED_MIDMONTH} 件）`}
      {generated.skip_reasons.PARTIAL_MANAGEMENT_COVERAGE > 0 &&
        `（管理期間が一部のみ ${generated.skip_reasons.PARTIAL_MANAGEMENT_COVERAGE} 件）`}
    </p>}
    <MoneyError action={action}/>
    {cancel && <MoneyReasonForm key={cancel.id} apiBase={apiBase}
      path={`charges/${cancel.id}/cancel`} title={`請求取消 ${cancel.charge_code}`}
      versions={{ version: cancel.version }} close={() => setCancel(null)}
      refresh={() => { setCancel(null); data.retry(); }}
      saved={() => { setCancel(null); data.retry(); }}/>}
    {month && <RentalResult result={data}>{(rows) => <>
      <MoneyList rows={rows} render={(row) => <MoneyRow
        title={`${row.tenant_name} · ${row.charge_name}`}
        description={`${row.lease_code} · 期限 ${row.due_date} · 請求 ${yen.format(row.amount)} · ${moneyStatuses[row.status]}`}
        balance={`未収 ${yen.format(row.remaining_amount)}`}
        onClick={!row.allocated_amount && row.status === "UNPAID" ? () => setCancel(row) : undefined}
        selected={cancel?.id === row.id}
        actionLabel="請求を取り消す"
      />}/>
      <Pager offset={offset} count={rows.length} setOffset={setOffset}/>
    </>}</RentalResult>}
  </div>;
}

function RentPaymentRegistration({ apiBase, saved }) {
  const funds = useRentalData(apiBase, "funds/summary");
  const action = useMoneyAction(apiBase);
  const [contract, setContract] = useState(null);
  const [retry, setRetry] = useState(null);
  return <RentalResult result={funds}>{({ accounts }) => <form className="panel rental-form" onSubmit={(event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form));
    const payload = { ...values, amount: Number(values.amount), fund_account_id: Number(values.fund_account_id),
      management_contract_id: contract };
    const signature = JSON.stringify(payload);
    const key = retry?.signature === signature ? retry.key : crypto.randomUUID();
    setRetry({ signature, key });
    action.submit("payments", { ...payload, idempotency_key: key }, (payment) => {
      setRetry(null);
      setContract(null);
      form.reset();
      saved(payment);
    });
  }}>
    <h2>入金登録</h2>
    <div className="rental-fields">
      <label>入金日<input type="date" name="received_date" required defaultValue={todayJst()}/></label>
      <label>入金額（円）<input type="number" name="amount" min="1" max={Number.MAX_SAFE_INTEGER} required/></label>
      <label>支払者<input name="payer_name" maxLength="200" required/></label>
      <label>入金元<select name="payment_source">
        <option value="TENANT">入居者</option><option value="GUARANTOR_COMPANY">保証会社</option><option value="OTHER">その他</option>
      </select></label>
      <label>入金口座<select name="fund_account_id" required
        defaultValue={accounts.find((account) => account.account_code === "ESCROW")?.id}>
        {accounts.filter((account) => account.status === "ACTIVE" && account.account_code === "ESCROW").map((account) =>
          <option key={account.id} value={account.id}>{account.account_name}</option>)}
      </select></label>
      <ReferenceField apiBase={apiBase} label="管理契約（未識別の場合は空欄）" resource="management-contracts"
        optional value={contract} setValue={setContract}/>
    </div>
    <MoneyError action={action}/>
    <button className="primary-btn" disabled={action.busy}>入金を登録</button>
  </form>}</RentalResult>;
}

function RentPayments({ apiBase, selected, select }) {
  const [offset, setOffset] = useState(0);
  const [registered, setRegistered] = useState(null);
  const result = useRentalData(apiBase, `payments?offset=${offset}`);
  return <div className="rental-stack">
    {!select && <RentPaymentRegistration apiBase={apiBase} saved={(row) => {
      setRegistered(row);
      setOffset(0);
      result.retry();
    }}/>}
    {registered && <p role="status">{registered.payer_name}の入金 {yen.format(registered.amount)} を登録しました。</p>}
    <RentalResult result={result}>{(rows) => <>
      <MoneyList rows={rows} render={(row) => <MoneyRow title={row.payer_name}
        description={`${row.received_date} · ${yen.format(row.amount)} · ${moneyStatuses[row.status]}`}
        balance={`未消込 ${yen.format(row.remaining_amount)}`}
        onClick={select ? () => select(row.id) : undefined} selected={selected === row.id}/>}/>
      <Pager offset={offset} count={rows.length} setOffset={setOffset}/>
    </>}</RentalResult>
  </div>;
}

function RentAllocationForm({ apiBase, payment, charge, saved }) {
  const action = useMoneyAction(apiBase);
  const [retry, setRetry] = useState(null);
  const cap = Math.min(payment.remaining_amount, charge.remaining_amount, Number.MAX_SAFE_INTEGER);
  return <form className="panel rental-form" onSubmit={(event) => {
    event.preventDefault();
    const amount = Number(new FormData(event.currentTarget).get("amount"));
    const key = retry?.amount === amount ? retry.key : crypto.randomUUID();
    setRetry({ amount, key });
    action.submit(`payments/${payment.id}/allocate`, { charge_id: charge.id, amount, idempotency_key: key,
      payment_version: payment.version, charge_version: charge.version }, saved);
  }}>
    <h3>{charge.tenant_name} · {charge.charge_name}</h3>
    <p>入金の未消込 {yen.format(payment.remaining_amount)} · 請求の未収 {yen.format(charge.remaining_amount)}</p>
    <div className="rental-fields">
      <label>消込額（円）<input name="amount" type="number" required min="1" max={cap}/></label>
    </div>
    <MoneyError action={action} refresh={saved}/>
    <button className="primary-btn" disabled={action.busy || cap <= 0}>消込を登録</button>
  </form>;
}

function RentAllocationDetail({ apiBase, paymentId, close }) {
  const [offset, setOffset] = useState(0);
  const [charge, setCharge] = useState(null);
  const [reversal, setReversal] = useState(null);
  const payment = useRentalData(apiBase, `payments/${paymentId}`);
  const charges = useRentalData(apiBase, `charges?payment_id=${paymentId}&offset=${offset}`);
  function refresh() {
    setCharge(null);
    setReversal(null);
    payment.retry();
    charges.retry();
  }
  return <RentalResult result={payment}>{(row) => <div className="rental-stack">
    <button type="button" className="secondary-btn" onClick={close}>入金一覧に戻る</button>
    <div className="panel">
      <h2>{row.payer_name}</h2>
      <p>{row.received_date} · {moneyStatuses[row.status]} · 未消込 <strong>{yen.format(row.remaining_amount)}</strong></p>
    </div>
    {row.remaining_amount > 0 && <>
      <h3>消込可能な請求</h3>
      <RentalResult result={charges}>{(rows) => <>
        <MoneyList rows={rows} empty="消込可能な請求がありません。" render={(item) => <MoneyRow
          title={`${item.tenant_name} · ${item.charge_name}`}
          description={`${item.lease_code} · ${item.service_month.slice(0, 7)} · 期限 ${item.due_date}`}
          balance={`未収 ${yen.format(item.remaining_amount)}`}
          onClick={() => { setCharge(item); setReversal(null); }} selected={charge?.id === item.id}/>}/>
        <Pager offset={offset} count={rows.length} setOffset={setOffset}/>
      </>}</RentalResult>
    </>}
    {charge && <RentAllocationForm key={charge.id} apiBase={apiBase} payment={row} charge={charge} saved={refresh}/>}
    <h3>消込履歴</h3>
    <MoneyList rows={row.allocations} empty="消込履歴がありません。" render={(item) => <MoneyRow title={item.charge_code}
      description={`${item.allocation_date} · ${item.reversal_of_id ? "取消記録" : item.reversed_by_id ? "取消済み" : "消込済み"}`}
      balance={yen.format(item.reversal_of_id ? -item.amount : item.amount)}
      onClick={!item.reversal_of_id && !item.reversed_by_id ? () => { setReversal(item); setCharge(null); } : undefined}
      selected={reversal?.id === item.id}/>}/>
    {row.status === "UNALLOCATED" && <button type="button" className="secondary-btn"
      onClick={() => { setReversal(row); setCharge(null); }}>入金を取り消す</button>}
    {reversal && <MoneyReasonForm key={reversal.charge_id ? reversal.id : "payment"} apiBase={apiBase}
      path={!reversal.charge_id ? `payments/${row.id}/reverse`
        : `payment_allocations/${reversal.id}/reverse`}
      title={reversal.charge_id ? "消込取消" : "入金取消"}
      idempotent={Boolean(reversal.charge_id)}
      versions={reversal.charge_id ? { allocation_version: reversal.version, payment_version: row.version,
        charge_version: reversal.charge_version } : { version: row.version }}
      saved={refresh} refresh={refresh} close={() => setReversal(null)}/>}
  </div>}</RentalResult>;
}

function RentAllocation({ apiBase }) {
  const [paymentId, setPaymentId] = useState(null);
  return paymentId === null ? <RentPayments apiBase={apiBase} select={setPaymentId}/>
    : <RentAllocationDetail key={paymentId} apiBase={apiBase} paymentId={paymentId} close={() => setPaymentId(null)}/>;
}

function RentOverdue({ apiBase }) {
  const [offset, setOffset] = useState(0);
  const result = useRentalData(apiBase, `charges/overdue?offset=${offset}`);
  return <RentalResult result={result}>{(rows) => <>
    <MoneyList rows={rows} empty="期限超過の未収請求はありません。" render={(row) => <MoneyRow
      title={`${row.tenant_name} · ${row.lease_code}`}
      description={`最も古い期限から ${row.overdue_days} 日超過 · ${row.charge_count} 件`}
      balance={yen.format(row.remaining_amount)}/>}/>
    <Pager offset={offset} count={rows.length} setOffset={setOffset}/>
  </>}</RentalResult>;
}

const depositStatuses = {
  EXPECTED: "受領待ち", PARTIALLY_HELD: "一部受領", HELD: "預り中",
  PARTIALLY_RETURNED: "一部返還", CLOSED: "完了",
};

const depositCustodians = { COMPANY: "自社", OWNER: "オーナー", OTHER: "その他" };

function DepositEventForm({ apiBase, row, receive, cap, saved, close }) {
  const action = useMoneyAction(apiBase);
  const label = receive ? "受領" : "返還";
  const dateField = receive ? "received_date" : "refunded_date";
  const noteField = receive ? "payer_name" : "reason";
  const latestDate = row.ledger_entries.reduce((latest, entry) =>
    entry.posting_date > latest ? entry.posting_date : latest, "");
  return <form className="panel rental-form" onSubmit={(event) => {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    action.submit(`deposits/${row.id}/${receive ? "receive" : "refund"}`, {
      ...values, amount: Number(values.amount), version: row.version,
    }, saved);
  }}>
    <h3>敷金{label}</h3>
    <div className="rental-fields">
      <label>{label}日<input type="date" name={dateField} required defaultValue={todayJst()}
        min={latestDate || undefined} max={todayJst()}/></label>
      <label>{label}額（円）<input type="number" name="amount" min="1" max={cap} required/></label>
      <label>{receive ? "支払者" : "返還理由"}<input name={noteField} required/></label>
    </div>
    <MoneyError action={action} refresh={saved}/>
    <div className="rental-controls">
      <button className="primary-btn" disabled={action.busy}>{label}を登録</button>
      <button type="button" className="secondary-btn" onClick={close} disabled={action.busy}>戻る</button>
    </div>
  </form>;
}

function RentDepositDetail({ apiBase, depositId, close }) {
  const result = useRentalData(apiBase, `deposits/${depositId}`);
  const [event, setEvent] = useState(null);
  return <div className="rental-stack">
    <div><button type="button" className="secondary-btn" onClick={close}>敷金一覧に戻る</button></div>
    <RentalResult result={result}>{(row) => {
      const balance = row.received_amount - row.refunded_amount - row.transferred_amount;
      const canReceive = row.custodian_type === "COMPANY" && row.lease_status !== "CANCELLED" &&
        ["EXPECTED", "PARTIALLY_HELD"].includes(row.status) && row.agreed_amount > row.received_amount;
      const canRefund = row.custodian_type === "COMPANY" && balance > 0;
      return <>
        <div className="panel">
          <h2>敷金 · {row.lease_code}</h2>
          <p>{depositStatuses[row.status]} · 保管者 {depositCustodians[row.custodian_type]}</p>
          <RecordValues row={{ ...row, balance }} fields={[
            ["agreed_amount", "約定額", "money"], ["received_amount", "受領額", "money"],
            ["refunded_amount", "返還額", "money"], ["balance", "預り残高", "money"],
          ]}/>
        </div>
        <div className="rental-controls">
          {canReceive && <button type="button" className="secondary-btn" onClick={() => setEvent("receive")}>受領する</button>}
          {canRefund && <button type="button" className="secondary-btn" onClick={() => setEvent("refund")}>返還する</button>}
        </div>
        {(event === "receive" ? canReceive : event === "refund" && canRefund) &&
          <DepositEventForm key={event} apiBase={apiBase} row={row} receive={event === "receive"}
            cap={Math.min(event === "receive" ? row.agreed_amount - row.received_amount : balance, Number.MAX_SAFE_INTEGER)}
            close={() => setEvent(null)} saved={() => { setEvent(null); result.retry(); }}/>}
        <h3>台帳履歴</h3>
        <MoneyList rows={[...row.ledger_entries].reverse()} empty="台帳履歴がありません。" render={(entry) =>
          <MoneyRow title={entry.direction === "IN" ? "受領" : "返還"}
            description={[entry.posting_date, entry.reason].filter(Boolean).join(" · ")}
            balance={yen.format(entry.direction === "IN" ? entry.amount : -entry.amount)}/>}/>
      </>;
    }}</RentalResult>
  </div>;
}

function RentDeposits({ apiBase }) {
  const [offset, setOffset] = useState(0);
  const [depositId, setDepositId] = useState(null);
  const result = useRentalData(apiBase, `deposits?offset=${offset}`);
  if (depositId !== null) return <RentDepositDetail key={depositId} apiBase={apiBase} depositId={depositId}
    close={() => { setDepositId(null); result.retry(); }}/>;
  return <RentalResult result={result}>{(rows) => <>
    <MoneyList rows={rows} empty="敷金の記録がありません。" render={(row) => <MoneyRow
      title={row.lease_code} description={`${depositStatuses[row.status]} · 保管者 ${depositCustodians[row.custodian_type]}`}
      balance={yen.format(row.agreed_amount)} onClick={() => setDepositId(row.id)} actionLabel="敷金詳細"/>}/>
    <Pager offset={offset} count={rows.length} setOffset={setOffset}/>
  </>}</RentalResult>;
}

function RentalRent({ apiBase, initialView }) {
  const [view, setView] = useState(initialView);
  const views = { "請求": RentCharges, "入金": RentPayments, "消込": RentAllocation, "滞納": RentOverdue, "敷金": RentDeposits };
  const View = views[view];
  return <div className="rental-stack">
    <nav className="rental-controls" aria-label="家賃収納の表示対象">
      {Object.keys(views).map((label) => <button type="button" className="secondary-btn"
        key={label} aria-pressed={view === label} onClick={() => setView(label)}>{label}</button>)}
    </nav>
    <View apiBase={apiBase}/>
  </div>;
}

const settlementStatuses = {
  DRAFT: "下書き", SUBMITTED: "承認待ち", APPROVED: "承認済み", FINALIZED: "確定済み", CANCELLED: "取消済み",
};
const settlementLineLabels = {
  OPENING: "期首残高の収納", INCOME: "収納", MANAGEMENT_FEE: "管理料", REPAIR: "修繕控除", ADJUSTMENT: "調整",
};
const settlementActions = {
  DRAFT: [["submit", "提出"], ["cancel", "取消"]],
  SUBMITTED: [["approve", "承認"], ["reject", "差戻し"], ["cancel", "取消"]],
  APPROVED: [["finalize", "確定"], ["cancel", "取消"]],
};
const remittanceStatuses = {
  SCHEDULED: "予定", SIMULATED_REMITTED: "模擬送金済み", FAILED: "失敗", CANCELLED: "取消済み",
};

function SettlementSource({ apiBase, source, back, openSettlement }) {
  const path = { payment_allocation: "payment_allocations", settlement_line: "settlement-lines" }[source.type];
  const result = useRentalData(apiBase, `${path}/${source.id}`);
  return <div className="rental-stack">
    <button type="button" className="secondary-btn" onClick={back}>精算明細に戻る</button>
    <RentalResult result={result}>{(row) => <div className="panel">
      <h2>{source.type === "payment_allocation" ? "消込記録" : "訂正元の精算明細"}</h2>
      <RecordValues row={row} fields={source.type === "payment_allocation"
        ? [["payment_code", "入金コード"], ["charge_code", "請求コード"], ["allocation_date", "消込日"], ["amount", "消込額", "money"]]
        : [["description", "内容"], ["source_month", "所属月"], ["amount", "金額", "money"]]}/>
      {row.settlement_id && <button type="button" className="secondary-btn" onClick={() => openSettlement(row.settlement_id)}>
        元の精算を開く
      </button>}
    </div>}</RentalResult>
  </div>;
}

const settlementFinanceRoles = ["finance", "executive", "administrator"];
const settlementApprovalRoles = ["executive", "store_manager", "administrator"];

function SettlementDetails({ apiBase, id, back, openSettlement, onChange, accountRole, userId }) {
  const canFinance = settlementFinanceRoles.includes(accountRole);
  const canApprove = settlementApprovalRoles.includes(accountRole);
  const result = useRentalData(apiBase, `settlements/${id}`);
  const action = useMoneyAction(apiBase);
  const [source, setSource] = useState(null);
  const [scheduled, setScheduled] = useState(todayJst());
  if (source?.type === "work_order") return <CaseDetails apiBase={apiBase} resource="work-orders" id={source.id}
    back={() => setSource(null)} open={(resource, sourceId) => setSource({ type: resource, id: sourceId })}/>;
  if (source?.type === "inspections" || source?.type === "complaints") return <CaseDetails apiBase={apiBase}
    resource={source.type} id={source.id} back={() => setSource(null)}
    open={(resource, sourceId) => setSource({ type: resource === "work-orders" ? "work_order" : resource, id: sourceId })}/>;
  if (source) return <SettlementSource apiBase={apiBase} source={source} back={() => setSource(null)}
    openSettlement={openSettlement}/>;
  function submit(operation, data) {
    action.submit(`settlements/${id}/${operation}`, data, () => {
      result.retry();
      onChange();
    });
  }
  return <div className="rental-stack">
    <button type="button" className="secondary-btn" onClick={back}>精算一覧に戻る</button>
    <MoneyError action={action} refresh={result.retry}/>
    <RentalResult result={result}>{(row) => {
      const remitted = row.remittances.find((item) => item.status === "SIMULATED_REMITTED");
      const pending = row.remittances.find((item) => item.status === "SCHEDULED");
      const { carry_in: carryIn } = row.calculation_snapshot;
      const carryOut = row.carry_out;
      return <>
        <div className="panel">
          <h2>{row.contract_code} · {row.settlement_month.slice(0, 7)}</h2>
          <p>{settlementStatuses[row.status]}</p>
          <RecordValues row={{ ...row, actual: remitted?.actual_amount, fee_due: row.calculation_snapshot.fee.amount }}
            fields={[
              ["opening_available_balance", "期首残高", "money"], ["collected_income", "収納額", "money"],
              ["fee_due", "当月管理料（税込）", "money"], ["management_fee", "管理料控除", "money"],
              ["approved_expenses", "修繕控除", "money"], ["outstanding_expense_balance", "繰越未控除額", "money"],
              ["adjustment_amount", "調整（正は控除）", "money"], ["payable_amount", "模擬送金予定額", "money"],
              ["actual", "模擬送金実績", "money"], ["closing_available_balance", "期末残高", "money"],
            ]}/>
          <div className="rental-controls">{(settlementActions[row.status] || [])
            .filter(([operation]) => ["approve", "reject"].includes(operation)
              ? canApprove && row.submitted_by !== userId : canFinance)
            .map(([operation, label]) =>
            <button key={operation} type="button" className="secondary-btn" disabled={action.busy}
              onClick={() => submit(operation, { version: row.version })}>{label}</button>)}</div>
        </div>
        {(carryIn || carryOut) && <div className="panel rental-stack">
          <h3>模擬送金の繰越</h3>
          {carryIn && <div>
            前回からの繰越 {yen.format(carryIn.amount)}　
            <button type="button" className="secondary-btn" onClick={() => openSettlement(carryIn.settlement_id)}>繰越元の精算</button>
          </div>}
          {carryOut && <div>
            当初予定額 {yen.format(carryOut.original_scheduled_amount)} · 繰越額 {yen.format(carryOut.amount)}　
            <button type="button" className="secondary-btn" onClick={() => openSettlement(carryOut.settlement_id)}>繰越先の精算</button>
          </div>}
        </div>}
        <h3>精算明細</h3>
        <MoneyList rows={row.lines} empty="明細がありません。" render={(line) => {
          const linked = ["payment_allocation", "work_order", "settlement_line"].includes(line.source_type);
          return <MoneyRow title={`${settlementLineLabels[line.line_type]} · ${line.description}`}
            description={[`明細 ID ${line.id}`, line.source_month?.slice(0, 7),
              line.rule_snapshot?.carried ? "繰越分" : null].filter(Boolean).join(" · ")}
            balance={yen.format(line.amount)}
            onClick={linked ? () => setSource({ type: line.source_type, id: line.source_id }) : undefined}
            actionLabel={line.adjustment_of_id ? "訂正元を開く" : "原始記録を開く"}/>;
        }}/>
        <h3>繰越未控除</h3>
        <MoneyList rows={row.calculation_snapshot.outstanding.map((item) => ({ ...item, id: `${item.source_type}-${item.source_id}` }))}
          empty="繰越未控除はありません。" render={(item) => <MoneyRow title={item.description}
            description={item.source_month.slice(0, 7)} balance={yen.format(item.amount)}
            onClick={item.source_type === "work_order" ? () => setSource({ type: item.source_type, id: item.source_id }) : undefined}/>}/>
        {canFinance && row.status === "DRAFT" && <form className="panel rental-stack" onSubmit={(event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          const original = form.get("original");
          submit("adjustments", { version: row.version, amount: Number(form.get("amount")), description: form.get("description"),
            adjustment_of_id: Number(original) });
        }}>
          <h3>調整を追加</h3>
          <label>調整額（円、収納の訂正は正、控除の訂正は負）<input name="amount" type="number" step="1" required/></label>
          <label>理由<input name="description" required maxLength={255}/></label>
          <label>訂正元の精算明細 ID<input name="original" type="number" min="1" required/></label>
          <button className="secondary-btn" disabled={action.busy}>調整を登録</button>
        </form>}
        <h3>模擬送金</h3>
        <MoneyList rows={row.remittances} empty="模擬送金の記録はありません。" render={(item) =>
          <MoneyRow title={`模擬送金 · ${item.carried_forward ? "後続精算へ繰越" : remittanceStatuses[item.status]}`}
            description={`予定日 ${item.scheduled_date}${item.remitted_date ? ` · 実行日 ${item.remitted_date}` : ""}`}
            balance={yen.format(item.actual_amount ?? item.scheduled_amount)}/>}/>
        {canFinance && row.status === "FINALIZED" && !remitted && !carryOut && <form className="panel rental-stack" onSubmit={(event) => {
          event.preventDefault();
          submit("remit", { version: row.version, scheduled_date: pending?.scheduled_date ?? scheduled });
        }}>
          <label>模擬送金予定日<input type="date" value={pending?.scheduled_date ?? scheduled} required
            disabled={!!pending} onChange={(event) => setScheduled(event.target.value)}/></label>
          <div className="rental-controls">
            <button className="primary-btn" disabled={action.busy}>模擬送金を実行</button>
            {pending ? <button type="button" className="secondary-btn" disabled={action.busy}
              onClick={() => submit(`remittances/${pending.id}/cancel`, { version: pending.version })}>模擬送金予定を取消</button>
              : <button type="button" className="secondary-btn" disabled={action.busy || !scheduled}
                onClick={() => submit("remittances", { version: row.version, scheduled_date: scheduled })}>模擬送金を予定</button>}
          </div>
        </form>}
      </>;
    }}</RentalResult>
  </div>;
}

function RentalPeriod({ apiBase, month, accountRole, userId }) {
  const result = useRentalData(apiBase, `periods/${month}`);
  const action = useMoneyAction(apiBase);
  const canPrepare = settlementFinanceRoles.includes(accountRole);
  const canClose = canPrepare || settlementApprovalRoles.includes(accountRole);
  const labels = { OPEN: "未締め", PREPARED: "準備済み", CLOSED: "締め済み",
    REOPEN_REQUESTED: "締め済み", REOPENED: "未締め" };
  return <section className="panel rental-stack">
    <h2>賃貸月次締め</h2>
    <MoneyError action={action} refresh={result.retry}/>
    <RentalResult result={result}>{(row) => <>
      <p>{labels[row.status]}</p>
      {row.snapshot && <dl>{Object.entries({
        charges: "請求", payments: "入金", allocations: "消込", settlements: "精算",
      }).map(([key, label]) => <div key={key}>
        <dt>{label}</dt><dd>{number.format(row.snapshot[key].count)} 件 · {yen.format(row.snapshot[key].amount)}</dd>
      </div>)}</dl>}
      <div className="rental-controls">
        {canPrepare && ["OPEN", "PREPARED", "REOPENED"].includes(row.status) &&
          <button type="button" className="secondary-btn" disabled={action.busy}
            onClick={() => action.submit(`periods/${month}/prepare`, undefined, result.retry)}>
            {row.status === "PREPARED" ? "締めを再準備" : "締めを準備"}
          </button>}
        {canClose && row.status === "PREPARED" && row.snapshot && row.prepared_by !== userId &&
          <button type="button" className="primary-btn" disabled={action.busy}
            onClick={() => action.submit(`periods/${month}/close`, { id: row.id, version: row.version }, result.retry)}>締めを確定</button>}
        {row.status === "PREPARED" && row.snapshot && row.prepared_by === userId && <small>別のユーザーによる確定待ち</small>}
      </div>
    </>}</RentalResult>
  </section>;
}

function RentalSettlements({ apiBase, accountRole, userId }) {
  const canFinance = settlementFinanceRoles.includes(accountRole);
  const [month, setMonth] = useState(todayJst().slice(0, 7));
  const [contract, setContract] = useState(null);
  const [offset, setOffset] = useState(0);
  const [id, setId] = useState(null);
  const data = useRentalData(apiBase, `settlements?month=${month}&offset=${offset}`);
  const action = useMoneyAction(apiBase);
  if (id) return <SettlementDetails key={id} apiBase={apiBase} id={id} back={() => setId(null)}
    openSettlement={setId} onChange={data.retry} accountRole={accountRole} userId={userId}/>;
  return <div className="rental-stack">
    <form className="panel rental-stack" onSubmit={(event) => {
      event.preventDefault();
      action.submit("settlements/generate", { settlement_month: month, management_contract_id: contract }, (row) => {
        data.retry();
        setId(row.id);
      });
    }}>
      <label>精算月<input type="month" required value={month} onChange={(event) => {
        setMonth(event.target.value);
        setOffset(0);
      }}/></label>
      {canFinance && <>
        <ReferenceField apiBase={apiBase} label="生成する管理契約" resource="management-contracts"
          value={contract} setValue={setContract}/>
        <button className="primary-btn" disabled={action.busy || !contract}>精算を生成</button>
      </>}
    </form>
    {month && <RentalPeriod key={month} apiBase={apiBase} month={month} accountRole={accountRole} userId={userId}/>}
    <MoneyError action={action} refresh={data.retry}/>
    {month && <RentalResult result={data}>{(rows) => <>
      <MoneyList rows={rows} empty="この月の精算はありません。" render={(row) => <MoneyRow title={row.contract_code}
        description={settlementStatuses[row.status]} balance={`模擬送金予定 ${yen.format(row.payable_amount)}`}
        onClick={() => setId(row.id)}/>}/>
      <Pager offset={offset} count={rows.length} setOffset={setOffset}/>
    </>}</RentalResult>}
  </div>;
}

function ContractFunds({ apiBase, contract }) {
  const [month, setMonth] = useState(todayJst().slice(0, 7));
  const result = useRentalData(apiBase, `funds/by-contract?month=${month || todayJst().slice(0, 7)}&management_contract_id=${contract}`);
  return <>
    <h3>オーナー資金の月次残高</h3>
    <label>所属月<input type="month" value={month} onChange={(event) => setMonth(event.target.value)}/></label>
    {month && <RentalResult result={result}>{({ items }) => items.length
      ? <RecordValues row={items[0]} fields={[
        ["opening_balance", "期首", "money"], ["monthly_in", "入金", "money"], ["monthly_out", "出金", "money"],
        ["closing_balance", "期末", "money"],
      ]}/>
      : <p>この月の資金記録はありません。</p>}</RentalResult>}
  </>;
}

function RentalFunds({ apiBase }) {
  const [contract, setContract] = useState("");
  const result = useRentalData(apiBase, "funds/summary");
  return <RentalResult result={result}>{(data) => {
    const checks = {
      unallocated: "未消込", deposit: "敷金", owner_allocation: "オーナー費目消込",
      settlement_fee_escrow: "管理料（預り金口座 OUT）", settlement_fee_company: "管理料（自社資金口座 IN）",
      settlement_repair: "修繕控除（預り金口座 OUT）", settlement_adjustment: "精算調整（預り金口座）",
      settlement_remittance: "模擬送金（預り金口座 OUT）", settlement_adjustment_company: "精算調整（自社資金口座）",
    };
    const selected = data.business_reconciliation.find((row) => String(row.management_contract_id) === contract);
    const differences = data.business_reconciliation.flatMap((row) =>
      Object.entries(checks).filter(([key]) => row[key].difference !== 0).map(([key, label]) => ({
        id: `${row.management_contract_id}-${key}`, contractId: row.management_contract_id,
        label, amount: row[key].difference,
      })));
    const independentChecks = { unidentified: "未識別資金", company_funds: "自社資金" };
    for (const [key, label] of Object.entries(independentChecks)) {
      const { difference } = data.independent_reconciliation[key];
      if (difference !== 0) differences.push({ id: key, label, amount: difference });
    }
    return <div className="rental-stack">
      <div className="rental-metrics">
        {data.accounts.map((account) => <div className="panel rental-metric" key={account.id}>
          <span>{account.account_name}</span><strong>{yen.format(account.balance)}</strong>
        </div>)}
        <div className={`panel rental-metric${data.reconciliation_difference ? " rental-error" : ""}`}
          role={data.reconciliation_difference ? "alert" : undefined}>
          <span>照合差額</span><strong>{yen.format(data.reconciliation_difference)}</strong>
        </div>
      </div>
      {data.accounts.map((account) => <div className="panel" key={account.id}>
        <h2>{account.account_name}の内訳</h2>
        <RecordValues row={account.categories}
          fields={Object.entries(fundCategoryNames).filter(([key]) => key in account.categories)
            .map(([key, label]) => [key, label, "money"])}/>
      </div>)}
      <div className="panel">
        <h2>業務データとの照合</h2>
        <label>管理契約<select value={contract} onChange={(event) => setContract(event.target.value)}>
          <option value="">契約を選択</option>
          {data.business_reconciliation.map((row) => <option key={row.management_contract_id} value={row.management_contract_id}>
            {row.contract_code}
          </option>)}
        </select></label>
        {selected && <>
          <ContractFunds apiBase={apiBase} contract={contract}/>
          <MoneyList rows={Object.entries(checks).map(([id, label]) => ({ id, label, ...selected[id] }))}
          render={(check) => <MoneyRow title={check.label}
            description={`業務 ${yen.format(check.business_amount)} · 台帳 ${yen.format(check.ledger_amount)}`}
            balance={`差額 ${yen.format(check.difference)}`}/>}/>
        </>}
        {differences.length ? <ul className="rental-error" role="alert">{differences.map((row) =>
          <li key={row.id}>{row.contractId && `管理契約 ID ${row.contractId} · `}{row.label}の差額 {yen.format(row.amount)}</li>)}</ul>
          : <p>全 {data.business_reconciliation.length} 契約・未識別資金・自社資金の照合差額 {yen.format(0)}</p>}
      </div>
    </div>;
  }}</RentalResult>;
}

const cancellableRepairStates = ["RECEIVED", "ESTIMATED", "APPROVED", "ARRANGED"];
const repairStates = [...cancellableRepairStates, "COMPLETED", "INSPECTED", "COST_CONFIRMED", "CLOSED", "CANCELLED"];
const complaintStates = ["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"];
const urgencies = ["URGENT", "HIGH", "NORMAL", "LOW"];
const bearers = ["OWNER", "COMPANY", "TENANT"];
const placeFields = [["building_id", "建物", "@buildings"], ["unit_id", "部屋", "@units?"]];
const caseFields = [
  ["category", "分類", ["EQUIPMENT", "NOISE", "OTHER"]], ["urgency", "緊急度", urgencies],
  ["description", "内容", "requiredNotes"], ["assigned_user_id", "担当者", "@staff"],
];
const inspectionFields = [
  ["inspection_type", "点検種別", ["ROUTINE", "OTHER"]], ["inspection_date", "点検日", "date"],
  ["result", "判定", ["PASS", "FAIL"]],
  ["findings", "所見", "notes"], ["next_inspection_date", "次回点検日", "optionalDate"],
];
const caseResources = {
  "work-orders": {
    label: "修繕", name: (row) => row.work_order_code,
    fields: [...placeFields, ["received_date", "受付日", "date"], ...caseFields],
  },
  complaints: {
    label: "苦情", name: (row) => row.complaint_code,
    fields: [...placeFields, ["reporter_party_id", "申出者", "@parties?"],
      ["received_at", "受付日時（日本時間）", "datetime"], ...caseFields],
  },
  inspections: {
    label: "点検", name: (row) => showValue(row.inspection_type),
    fields: [...placeFields, ...inspectionFields],
  },
};
Object.assign(resources, caseResources);

const reapproveRepair = ["reapprove", "再承認", [["approved_amount", "再承認額（円）", "integer"]]];
const cancelRepair = ["cancel", "修繕を取り消す", [["cancellation_reason", "取消理由", "requiredNotes"]]];
const repairActions = {
  RECEIVED: [["estimate", "見積を記録", [["estimated_amount", "見積額（円）", "integer"], ["cost_bearer", "費用負担者", bearers]]]],
  ESTIMATED: [["approve", "承認", [["approved_amount", "承認額（円）", "integer"]]]],
  APPROVED: [["arrange", "手配", [["contractor_party_id", "協力会社", "@parties"], ["scheduled_date", "作業予定日", "date"]]]],
  ARRANGED: [["complete", "作業完了", [["completed_date", "完了日", "date"], ["actual_amount", "暫定実費（円）", "integer"]]]],
  COMPLETED: [["inspect", "検収", [["inspected_date", "検収日", "date"], ["findings", "所見", "notes"]]], reapproveRepair],
  INSPECTED: [["confirm-cost", "費用確定", [["actual_amount", "実費（円）", "integer"]]], reapproveRepair],
  COST_CONFIRMED: [["close", "修繕を終了", []]],
};
const convertComplaint = ["create-work-order", "修繕化", []];
const complaintActions = {
  OPEN: [["start", "対応開始", []]],
  IN_PROGRESS: [["resolve", "解決", [["resolution_summary", "対応結果", "requiredNotes"]]]],
  RESOLVED: [["close", "苦情を終了", []]],
};

const formatJstTimestamp = new Intl.DateTimeFormat("ja-JP", {
  timeZone: "Asia/Tokyo", dateStyle: "medium", timeStyle: "short",
});
function caseTimestamp(value) {
  return value ? formatJstTimestamp.format(new Date(/(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : value + "Z")) : null;
}
function casePlace(row) {
  return [row.building_name, row.unit_number && `${row.unit_number}号室`].filter(Boolean).join(" ");
}

function CaseList({ apiBase, tab, open, create }) {
  const [filters, setFilters] = useState({});
  const [offset, setOffset] = useState(0);
  const query = new URLSearchParams({ offset, ...filters });
  const result = useRentalData(apiBase, `${tab}?${query}`);
  const resource = caseResources[tab];
  const states = tab === "work-orders" ? repairStates : complaintStates;

  function filter(key, value) {
    setFilters((current) => {
      const next = { ...current };
      if (value) next[key] = value;
      else delete next[key];
      return next;
    });
    setOffset(0);
  }

  return <>
    <div className="panel rental-form">
      <div className="rental-fields">
        {tab !== "inspections" && [
          ["urgency", "緊急度", urgencies], ["status", "状態", states],
        ].map(([key, label, options]) => <label key={key}>{label}
          <select value={filters[key] || ""} onChange={(event) => filter(key, event.target.value)}>
            <option value="">すべて</option>
            {options.map((option) => <option key={option} value={option}>{showValue(option)}</option>)}
          </select>
        </label>)}
        <ReferenceField apiBase={apiBase} label="建物" resource="buildings" optional
          value={filters.building_id} setValue={(value) => filter("building_id", value)}/>
      </div>
      <div className="rental-controls">
        <button type="button" className="primary-btn" onClick={create}>{resource.label}を登録</button>
      </div>
    </div>
    <RentalResult result={result}>{(rows) => <>
      <MoneyList rows={rows} render={(row) => {
        const urgent = tab === "work-orders" && row.urgency === "URGENT" &&
          cancellableRepairStates.includes(row.status);
        const days = urgent ? Math.max(0, (Date.parse(todayJst()) - Date.parse(row.received_date)) / 86400000) : null;
        return <button type="button" className="rental-list-button" onClick={() => open(tab, row.id)}>
          <strong>{resource.name(row)}</strong>
          <small>{[casePlace(row), row.description, row.inspection_date, row.urgency && showValue(row.urgency),
            (row.status || row.result) && showValue(row.status || row.result)].filter(Boolean).join(" · ")}</small>
          {urgent && <strong className="rental-error">緊急 · 受付から {days} 日</strong>}
        </button>;
      }}/>
      <Pager offset={offset} count={rows.length} setOffset={setOffset}/>
    </>}</RentalResult>
  </>;
}

function CaseDetails({ apiBase, resource, id, back, open }) {
  const result = useRentalData(apiBase, `${resource}/${id}`);
  return <>
    <div className="rental-controls">
      <button type="button" className="secondary-btn" onClick={back}>戻る</button>
    </div>
    <RentalResult result={result}>{(row) => <CaseRecord key={`${id}:${row.version}`}
      apiBase={apiBase} resource={resource} row={row} reload={result.retry} open={open}/>}</RentalResult>
  </>;
}

function CaseRecord({ apiBase, resource, row, reload, open }) {
  const [action, setAction] = useState(null);
  const repair = resource === "work-orders";
  const complaint = resource === "complaints";
  const actions = [...((repair ? repairActions : complaintActions)[row.status] || [])];
  if (repair && cancellableRepairStates.includes(row.status)) actions.push(cancelRepair);
  if (complaint && !row.work_order && ["OPEN", "IN_PROGRESS"].includes(row.status)) actions.push(convertComplaint);
  if (action) return <RentalForm apiBase={apiBase} resource={resource} record={row} action={action}
    onCancel={() => setAction(null)} onReload={reload}
    onSaved={(saved, target) => {
      if (target === resource) reload();
      else open(target, saved.id);
    }}/>;

  const details = repair ? [
    ["received_date", "受付日"], ["estimated_amount", "見積額", "money"], ["approved_amount", "承認額", "money"],
    ["actual_amount", row.cost_confirmed_at ? "確定実費" : "暫定実費", "money"],
    ["cost_bearer", "費用負担者"], ["settlement_eligibility", "精算参加可否"], ["settlement_state", "精算参加状況"],
    ["cost_confirmed_at", "費用確定日時"], ["approved_by", "承認者 ID"], ["contractor_party_id", "協力会社 ID"],
    ["scheduled_date", "作業予定日"], ["completed_date", "完了日"], ["inspected_date", "検収日"],
    ["inspected_by", "検収者 ID"], ["management_contract_id", "管理契約 ID"],
  ] : complaint ? [
    ["received_at", "受付日時"], ["reporter_party_id", "申出者 ID"], ["resolved_at", "解決日時"],
    ["resolution_summary", "対応結果"],
  ] : [...inspectionFields.map(([key, label]) => [key, label]), ["inspected_by", "点検者 ID"]];

  return <div className="panel rental-form">
    <h2>{caseResources[resource].name(row)}</h2>
    <RecordValues row={{
      ...row, location: casePlace(row), received_at: caseTimestamp(row.received_at),
      resolved_at: caseTimestamp(row.resolved_at), cost_confirmed_at: caseTimestamp(row.cost_confirmed_at),
      settlement_eligibility: row.settlement_eligible ? "対象" : "対象外",
      settlement_state: row.settlement_participated ? "参加済み" : "未精算",
    }} fields={[
      ["location", "建物・部屋"], ...(repair || complaint ? [
        ["status", "状態"], ["urgency", "緊急度"], ["category", "分類"], ["description", "内容"],
        ["assigned_user_id", "担当者 ID"],
      ] : []), ...details,
    ]}/>
    <div className="rental-controls">
      {actions.map((item) => <button type="button" key={item[0]} className="secondary-btn"
        onClick={() => setAction(item)}>{item[1]}</button>)}
      {row.complaint && <button type="button" className="secondary-btn" onClick={() => open("complaints", row.complaint.id)}>
        苦情 {row.complaint.complaint_code}
      </button>}
      {(row.work_order || row.work_order_id) && <button type="button" className="secondary-btn"
        onClick={() => open("work-orders", row.work_order?.id ?? row.work_order_id)}>
        修繕 {row.work_order?.work_order_code ?? row.work_order_id}
      </button>}
    </div>
    {repair && <div>
      <h3>検収記録</h3>
      <MoneyList rows={row.inspections} empty="検収記録はありません。" render={(inspection) =>
        <MoneyRow title={showValue(inspection.inspection_type)}
          description={`${inspection.inspection_date} · ${showValue(inspection.result)}`}
          onClick={() => open("inspections", inspection.id)}/>}/>
    </div>}
  </div>;
}

function RentalRepairs({ apiBase, initialTab }) {
  const [tab, setTab] = useState(initialTab);
  const [history, setHistory] = useState([]);
  const view = history.at(-1);
  const open = (resource, id) => setHistory((current) => [...current, { resource, id }]);
  const back = () => setHistory((current) => current.slice(0, -1));
  return <>
    <div className="rental-controls">
      {Object.entries(caseResources).map(([key, resource]) =>
        <button type="button" key={key} className="secondary-btn" aria-pressed={tab === key} onClick={() => {
          setTab(key);
          setHistory([]);
        }}>{resource.label}</button>)}
    </div>
    {view?.id ? <CaseDetails key={`${view.resource}:${view.id}`} apiBase={apiBase}
      resource={view.resource} id={view.id} back={back} open={open}/>
      : view ? <RentalForm apiBase={apiBase} resource={view.resource} onCancel={back}
        preset={{ received_date: todayJst(), inspection_date: todayJst(), urgency: "NORMAL" }}
        onSaved={(row, resource) => setHistory([{ resource, id: row.id }])}/>
        : <CaseList key={tab} apiBase={apiBase} tab={tab} open={open}
          create={() => setHistory([{ resource: tab }])}/>}
  </>;
}

function OwnerSummary({ apiBase }) {
  const result = useRentalData(apiBase, "owner/summary");
  return <RentalResult result={result}>{(data) => {
    const actual = data.latest_actual_remittance;
    const scheduled = data.latest_scheduled_remittance;
    return <section aria-labelledby="owner-summary">
      <h2 id="owner-summary">今月の模擬送金（{data.month.slice(0, 7)}）</h2>
      <div className="rental-metrics">
        <div className="panel rental-metric"><span>最新の模擬送金実績</span>
          <strong>{actual ? yen.format(actual.actual_amount) : "実績なし"}</strong>
          {actual && <small>{actual.remitted_date}</small>}
        </div>
        <div className="panel rental-metric"><span>最新の模擬送金予定</span>
          <strong>{scheduled ? yen.format(scheduled.scheduled_amount) : "予定なし"}</strong>
          {scheduled && <small>{scheduled.scheduled_date}</small>}
        </div>
        <div className="panel rental-metric"><span>年間累計の模擬送金額</span>
          <strong>{yen.format(data.annual_remitted_amount)}</strong>
        </div>
        <div className="panel rental-metric"><span>{data.cumulative_balance_label}</span>
          <strong>{yen.format(data.cumulative_balance)}</strong><small>{data.cumulative_balance_note}</small>
        </div>
        <div className="panel rental-metric"><span>管理戸数・入居率</span>
          <strong>{number.format(data.managed_unit_count)} 戸 · {percent.format(data.occupancy_rate)}</strong>
          <small>入居 {number.format(data.occupied_unit_count)} 戸</small>
        </div>
      </div>
    </section>;
  }}</RentalResult>;
}

function OwnerList({ apiBase, resource, render, empty }) {
  const [offset, setOffset] = useState(0);
  const separator = resource.includes("?") ? "&" : "?";
  const result = useRentalData(apiBase, `owner/${resource}${separator}offset=${offset}`);
  return <RentalResult result={result}>{(rows) => <>
    <MoneyList rows={rows} render={render} empty={empty}/>
    <Pager offset={offset} count={rows.length} setOffset={setOffset}/>
  </>}</RentalResult>;
}

function OwnerSettlement({ apiBase, id, openSettlement }) {
  const result = useRentalData(apiBase, `owner/settlements/${id}`);
  return <RentalResult result={result}>{(row) => <>
    <div className="panel rental-metric">
      <h3>{row.settlement_month.slice(0, 7)} · {row.contract_code}</h3>
      <RecordValues row={{
        ...row, management_fee: 0 - row.management_fee, approved_expenses: 0 - row.approved_expenses,
        adjustment_amount: 0 - row.adjustment_amount,
      }} fields={[
        ["opening_available_balance", "期首残高", "money"],
        ["collected_income", "収納額", "money"], ["management_fee", "管理料", "money"],
        ["approved_expenses", "修繕控除", "money"], ["adjustment_amount", "調整額", "money"],
        ["payable_amount", row.carry_out ? "確定時の送金可能額" : "模擬送金予定額", "money"], ["closing_available_balance", "期末残高", "money"],
        ["outstanding_expense_balance", "未控除費用", "money"],
      ]}/>
    </div>
    {row.carry_out && <MoneyRow title="後続精算へ繰越" balance={yen.format(row.carry_out.amount)}
      onClick={() => openSettlement(row.carry_out.settlement_id)} actionLabel="繰越先の精算を開く"/>}
    <h3>精算明細</h3>
    <MoneyList rows={row.lines} empty="精算明細はありません。" render={(line) => <MoneyRow
      title={settlementLineLabels[line.line_type] || line.line_type}
      description={[line.description, line.source_month?.slice(0, 7)].filter(Boolean).join(" · ")}
      balance={yen.format(["MANAGEMENT_FEE", "REPAIR", "ADJUSTMENT"].includes(line.line_type)
        ? 0 - line.amount : line.amount)}/>}/>
    <h3>模擬送金履歴</h3>
    <MoneyList rows={row.remittances} empty="模擬送金の記録はありません。" render={(item) => <MoneyRow
      title={item.carried_forward ? "後続精算へ繰越" : remittanceStatuses[item.status]} description={item.remitted_date || item.scheduled_date}
      balance={yen.format(item.carried_forward ? row.carry_out.amount : item.actual_amount ?? item.scheduled_amount)}/>}/>
  </>}</RentalResult>;
}

function OwnerPortal({ apiBase }) {
  const [settlementId, setSettlementId] = useState(null);
  const [showHistory, setShowHistory] = useState(false);
  return <div className="rental-stack owner-portal">
    <p className="rental-disclaimer">共有サンプル環境です。表示データは架空で、送金はすべて模擬送金です。</p>
    <OwnerSummary apiBase={apiBase}/>
    <section aria-labelledby="owner-properties">
      <h2 id="owner-properties">物件・入居状況</h2>
      <OwnerList apiBase={apiBase} resource="properties" empty="現在所有する部屋はありません。"
        render={(row) => <MoneyRow title={`${row.building_name} ${row.unit_number}`}
          description={statuses[row.occupancy_status]}
          balance={row.rent_amount == null ? "賃料 —" : `賃料 ${yen.format(row.rent_amount)}`}/>}/>
      <button type="button" className="secondary-btn" aria-expanded={showHistory}
        onClick={() => setShowHistory(!showHistory)}>管理契約の履歴</button>
      {showHistory && <OwnerList apiBase={apiBase} resource="properties?history=true" empty="管理契約の履歴はありません。"
        render={(row) => <MoneyRow title={`${row.building_name} ${row.unit_number}`}
          description={row.contract_code} balance={`${row.valid_from} 〜 ${row.valid_to || "—"}`}/>}/>}
    </section>
    <section aria-labelledby="owner-settlements">
      <h2 id="owner-settlements">確定済みの精算</h2>
      <div hidden={settlementId !== null}>
        <OwnerList apiBase={apiBase} resource="settlements" empty="確定済みの精算はありません。"
          render={(row) => <MoneyRow title={`${row.settlement_month.slice(0, 7)} · ${row.contract_code}`}
            description={row.settlement_code} balance={row.carry_out ? `後続精算へ繰越 ${yen.format(row.carry_out.amount)}`
              : `模擬送金予定 ${yen.format(row.payable_amount)}`}
            onClick={() => setSettlementId(row.id)} actionLabel="精算詳細"/>}/>
      </div>
      {settlementId !== null && <div className="rental-stack">
        <div className="rental-controls"><button type="button" className="secondary-btn"
          onClick={() => setSettlementId(null)}>精算一覧に戻る</button></div>
        <OwnerSettlement key={settlementId} apiBase={apiBase} id={settlementId} openSettlement={setSettlementId}/>
      </div>}
    </section>
    <section aria-labelledby="owner-repairs">
      <h2 id="owner-repairs">修繕履歴</h2>
      <OwnerList apiBase={apiBase} resource="repairs" empty="修繕履歴はありません。"
        render={(row) => <div className="owner-repair rental-metric">
          <strong>{row.building_name} {row.unit_number}</strong>
          <small>{statuses[row.category]} · {statuses[row.status]}</small>
          <RecordValues row={row} fields={[
            ["cost_bearer", "費用負担"], ["estimated_amount", "見積額", "money"],
            ["approved_amount", "承認額", "money"], ["actual_amount", "実費", "money"],
            ["completed_date", "完了日"],
          ]}/>
        </div>}/>
    </section>
  </div>;
}
