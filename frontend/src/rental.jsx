import { useEffect, useState } from "react";

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

function RentalDashboard({ apiBase }) {
  const result = useRentalData(apiBase, "summary");
  return <RentalResult result={result}>{(data) => <>
    <p className="muted">集計月 {data.service_month.slice(0, 7)}</p>
    <div className="rental-metrics">
      {[
        ["当月請求分未収額", yen.format(data.outstanding_amount)],
        ["未消込入金", `${number.format(data.unallocated_payment_count)} 件`],
        ["緊急苦情", `${number.format(data.urgent_complaint_count)} 件`],
        ["精算承認待ち", `${number.format(data.pending_settlement_approval_count)} 件`],
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
  </>}</RentalResult>;
}

export default function RentalPage({ page, apiBase }) {
  const title = rentalPages.find(([id]) => id === page)?.[1];
  if (!title) return null;
  return <section className="rental-page">
    <h1>{page === "dashboard" ? "管理業務ダッシュボード" : title}</h1>
    {page === "dashboard" ? <RentalDashboard apiBase={apiBase}/>
      : page === "properties" ? <RentalProperties apiBase={apiBase}/>
        : page === "applications" ? <RentalPipeline apiBase={apiBase}/>
          : <p className="panel">準備中</p>}
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
};

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
      ["management_status", "管理状態", ["MANAGED", "UNMANAGED"]], ["occupancy_status", "入居状態", occupation],
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
    DRAFT: [["sign", "署名日を記録", [["signed_date", "署名日", "optionalDate"]]]],
    SIGNED: [["move-in", "入居を記録", [["actual_move_in_date", "入居日", "optionalDate"]]]],
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

function ReferenceField({ apiBase, label, resource, value, setValue, optional }) {
  const [offset, setOffset] = useState(0);
  const [selectedLabel, setSelectedLabel] = useState("");
  const filter = resource === "fee-plans" ? "&status=ACTIVE" : "";
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

function RentalField({ apiBase, field, value, setValue }) {
  const [, label, kind] = field;
  if (Array.isArray(kind)) return <label>{label}<select required value={value ?? ""} onChange={(e) => setValue(e.target.value)}>
    <option value="">選択してください</option>
    {value && !kind.includes(value) && <option value={value}>{showValue(value)}</option>}
    {kind.map((choice) => <option key={choice} value={choice}>{showValue(choice)}</option>)}
  </select></label>;
  if (kind?.startsWith("@")) return <ReferenceField apiBase={apiBase} label={label} resource={kind.slice(1).replace("?", "")}
    optional={kind.endsWith("?")} value={value} setValue={setValue}/>;
  if (kind === "charges") return <ChargeSelection apiBase={apiBase} value={value} setValue={setValue}/>;
  if (kind === "notes") return <label>{label}<textarea value={value ?? ""} onChange={(e) => setValue(e.target.value || null)}/></label>;
  if (kind === "boolean") return <label className="rental-check">
    <input type="checkbox" checked={Boolean(value)} onChange={(e) => setValue(e.target.checked)}/>{label}
  </label>;
  const integer = kind === "integer" || kind === "optionalInteger";
  const type = integer ? "number" : kind === "date" || kind === "optionalDate" ? "date" : kind === "month" ? "month" : "text";
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
      && (record.status !== "ACTIVE" || !["owner_party_id", "start_date"].includes(key));
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
  const [assignments, setAssignments] = useState(() => (record?.units || []).map((row) => ({
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
      onSaved(data, action?.[0] === "create-lease" ? "leases" : resource);
    } catch {
      setFailure({ message: "保存できませんでした。通信状況を確認してください。" });
    } finally {
      setBusy(false);
    }
  }

  return <form className="panel rental-form" onSubmit={save}>
    <h2>{title}</h2>
    {action?.[0] === "create-lease" && <RecordValues row={record} fields={[
      ["desired_move_in_date", "契約開始日"], ["proposed_rent", "家賃", "money"], ["proposed_common_fee", "共益費", "money"],
    ]}/>}
    <div className="rental-fields">{fields.map((field) => <RentalField key={field[0]} apiBase={apiBase} field={field}
      value={values[field[0]]} setValue={(value) => setValues((current) => ({ ...current, [field[0]]: value }))}/>)}</div>
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
      <RecordValues row={row} fields={general}/>
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
        {" "}{item.valid_from} ～ {item.valid_to || "期限なし"}
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
          ["scheduled_move_out_date", "退去予定日"], ["actual_move_out_date", "退去日"], ["termination_reason", "解約理由"],
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
