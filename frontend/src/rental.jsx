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

function RentalProperties({ apiBase }) {
  const [tab, setTab] = useState("buildings");
  const [offset, setOffset] = useState(0);
  const result = useRentalData(apiBase, `${tab}?limit=${pageSize}&offset=${offset}`);
  const buildings = tab === "buildings";
  return <>
    <div className="trend-controls" aria-label="表示対象">
      {[["buildings", "建物"], ["units", "部屋"]].map(([id, label]) =>
        <button className="secondary-btn" type="button" key={id} aria-pressed={tab === id}
          onClick={() => { setTab(id); setOffset(0); }}>{label}</button>
      )}
    </div>
    <RentalResult result={result}>{(rows) => <>
      {rows.length === 0 ? <p>表示できるデータがありません。</p> : <div className="panel table-scroll">
        <table><thead><tr>
          {(buildings ? ["物件コード", "物件名", "住所"] : ["物件名", "部屋番号", "募集家賃", "共益費", "入居状況"])
            .map((column) => <th scope="col" key={column}>{column}</th>)}
        </tr></thead><tbody>
          {rows.map((row) => buildings ? <tr key={row.id}>
            <td>{row.building_code}</td><td>{row.building_name}</td><td>{row.address}</td>
          </tr> : <tr key={row.id}>
            <td>{row.building_name}</td><td>{row.unit_number}</td>
            <td>{yen.format(row.advertised_rent)}</td><td>{yen.format(row.advertised_common_fee)}</td>
            <td>{{ OCCUPIED: "入居中", VACANT: "空室", APPLYING: "申込中", CONTRACTING: "契約手続中", TERMINATION_PENDING: "解約予定" }[row.occupancy_status] || row.occupancy_status}</td>
          </tr>)}
        </tbody></table>
      </div>}
      {(offset > 0 || rows.length === pageSize) && <div className="trend-controls">
        <button className="secondary-btn" type="button" disabled={offset === 0}
          onClick={() => setOffset(offset - pageSize)}>前へ</button>
        <button className="secondary-btn" type="button" disabled={rows.length < pageSize}
          onClick={() => setOffset(offset + pageSize)}>次へ</button>
      </div>}
    </>}</RentalResult>
  </>;
}

export default function RentalPage({ page, apiBase }) {
  const title = rentalPages.find(([id]) => id === page)?.[1];
  if (!title) return null;
  return <section className="rental-page">
    <h1>{page === "dashboard" ? "管理業務ダッシュボード" : title}</h1>
    {page === "dashboard" ? <RentalDashboard apiBase={apiBase}/>
      : page === "properties" ? <RentalProperties apiBase={apiBase}/>
        : <p className="panel">準備中</p>}
  </section>;
}
