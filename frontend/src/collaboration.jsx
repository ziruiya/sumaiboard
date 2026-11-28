import React, { useEffect, useMemo, useRef, useState } from "react";
import { apiFetch } from "./api.js";
import { todayJst } from "./jst-date.js";
import {
  ArrowLeft, CalendarDays, ChevronLeft, ChevronRight, MessageSquare, Plus, Search,
} from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE || "";
const localDate = (date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};
const weekStart = (date) => {
  const result = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  result.setDate(result.getDate() - ((result.getDay() + 6) % 7));
  return result;
};
const eventDateTime = (date, hour = 10) => {
  const value = new Date(date.getFullYear(), date.getMonth(), date.getDate(), hour);
  return `${localDate(value)}T${String(hour).padStart(2, "0")}:00`;
};
const toLocalInput = (value) => value ? String(value).slice(0, 16) : "";

async function request(path, method = "GET", body, locale = "ja") {
  const response = await apiFetch(`${API_BASE}${path}`, {
    method, credentials: "include",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || (locale === "zh" ? "操作失败，请重试。" : "操作に失敗しました。"));
  return payload;
}

function RequestFeedback({ status, t, onRetry }) {
  if (status.state === "loading") return <div className="workspace-load" role="status">
    <span className="spinner" aria-hidden="true"/>{t("loadingRecords")}
  </div>;
  if (status.state === "error") return <div className="workspace-load config-error" role="alert">
    <span>{status.message}</span>
    <button type="button" className="secondary-btn" onClick={onRetry}>{t("searchRetry")}</button>
  </div>;
  return null;
}

export default function CollaborationWorkspace({ displayDate, roleLabel, stageLabel, view, data, locale, role, t, api, onBack, onTask, onHousehold }) {
  const title = view === "calendar" ? t("schedule")
    : view === "bulletin" ? t("bulletin") : t("negotiationQueue");
  return <section className="collaboration-workspace">
    <div className="workspace-title">
      <button className="secondary-btn" onClick={onBack}><ArrowLeft size={15}/>{t("backToWorkspace")}</button>
      <div><div className="eyebrow">{t("collaboration")}</div><h1>{title}</h1></div>
    </div>
    {view === "calendar" && <CalendarView roleLabel={roleLabel} data={data} role={role} t={t} locale={locale} api={api} onTask={onTask}/>}
    {view === "bulletin" && <BulletinView displayDate={displayDate} data={data} role={role} t={t} locale={locale} api={api}/>}
    {view === "queue" && <NegotiationQueue displayDate={displayDate} stageLabel={stageLabel} data={data} locale={locale} t={t} onHousehold={onHousehold}/>}
  </section>;
}

function CalendarView({ roleLabel, data, role, t, locale, api, onTask }) {
  const [week, setWeek] = useState(() => weekStart(new Date()));
  const [calendar, setCalendar] = useState({ events: [], employees: [] });
  const [employee, setEmployee] = useState("all");
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState("");
  const [loadStatus, setLoadStatus] = useState({ state: "loading" });
  const loadRequestId = useRef(0);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState(null);
  const days = useMemo(() => Array.from({ length: 7 }, (_, index) => {
    const date = new Date(week);
    date.setDate(date.getDate() + index);
    return date;
  }), [week]);
  const rangeStart = localDate(days[0]);
  const rangeEnd = localDate(days[6]);

  async function load() {
    const requestId = ++loadRequestId.current;
    setLoadStatus({ state: "loading" });
    try {
      const result = await request(`/api/calendar?start=${rangeStart}&end=${rangeEnd}`, "GET", undefined, locale);
      if (requestId !== loadRequestId.current) return;
      setCalendar(result);
      setLoadStatus({ state: "success" });
    } catch (loadError) {
      if (requestId === loadRequestId.current) setLoadStatus({ state: "error", message: loadError.message });
    }
  }
  useEffect(() => { load(); }, [rangeStart, rangeEnd]);

  const visibleEmployees = calendar.employees.filter((item) => employee === "all" || item.id === Number(employee));
  const visibleEvents = calendar.events.filter((item) => employee === "all" || item.owner_id === Number(employee));
  const eventLabel = (event) => {
    const map = {
      meeting: "eventMeeting", business_trip: "eventTrip", personal: "eventPersonal",
      appointment: "eventAppointment", task_deadline: "eventTask",
    };
    return t(map[event.event_type] || "eventPersonal");
  };
  const visibilityLabel = (event) => ({ private: t("privateEvent"), store: t("storeEvent"), company: t("companyEvent") })[event.visibility] || "";
  function startCreate() {
    const day = new Date(days[0]);
    day.setHours(0, 0, 0, 0);
    setEditing(null);
    setForm({
      title: "", event_type: "personal", starts_at: eventDateTime(day, 10),
      ends_at: eventDateTime(day, 11), all_day: false, visibility: "private",
    });
  }
  function editEvent(event) {
    if (event.source_type !== "manual" || event.owner_id !== data.user.id) {
      if (event.task_id || event.household_id) onTask(event);
      return;
    }
    setEditing(event);
    setForm({
      title: event.title, event_type: event.event_type, starts_at: toLocalInput(event.starts_at),
      ends_at: toLocalInput(event.ends_at), all_day: Boolean(event.all_day),
      visibility: event.visibility, version: event.version,
    });
  }
  async function saveEvent(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const payload = {
        ...form, ends_at: form.ends_at || null,
        version: editing?.version,
      };
      if (editing) await api(`/api/calendar/${editing.id}`, "PUT", payload);
      else await api("/api/calendar", "POST", payload);
      setForm(null);
      setEditing(null);
      await load();
    } catch (saveError) { setError(saveError.message); }
    finally { setSaving(false); }
  }
  const eventRows = (ownerId, dayKey) => visibleEvents
    .filter((item) => item.owner_id === ownerId && String(item.starts_at).slice(0, 10) === dayKey);
  const weekLabel = `${days[0].toLocaleDateString(locale === "ja" ? "ja-JP" : "zh-CN")} – ${days[6].toLocaleDateString(locale === "ja" ? "ja-JP" : "zh-CN")}`;
  const canCompany = role !== "advisor" && data.account_role !== "finance";
  return <div className="calendar-workspace">
    <section className="panel calendar-panel">
      <div className="calendar-toolbar">
        <div><CalendarDays size={18}/><b>{weekLabel}</b></div>
        <div className="calendar-controls">
          <label>{t("queueOwner")}<select value={employee} onChange={(event) => setEmployee(event.target.value)}>
            <option value="all">{t("all")}</option>
            {calendar.employees.map((item) => <option value={item.id} key={item.id}>{item.store_name ? `${item.store_name} · ` : ""}{item.name}</option>)}
          </select></label>
          <button className="secondary-btn" onClick={() => setWeek((current) => new Date(current.getFullYear(), current.getMonth(), current.getDate() - 7))}>
            <ChevronLeft size={15}/>{t("previousWeek")}</button>
          <button className="secondary-btn" onClick={() => setWeek((current) => new Date(current.getFullYear(), current.getMonth(), current.getDate() + 7))}>
            {t("nextWeek")}<ChevronRight size={15}/></button>
          <button className="primary-btn" onClick={startCreate}><Plus size={15}/>{t("newSchedule")}</button>
        </div>
      </div>
      {error && <div className="config-error" role="alert">{error}</div>}
      {form && <form className="calendar-form" onSubmit={saveEvent}>
        <label>{t("eventTitle")}<input maxLength="255" required value={form.title}
          onChange={(event) => setForm({ ...form, title: event.target.value })}/></label>
        <label>{t("eventType")}<select value={form.event_type} onChange={(event) => setForm({ ...form, event_type: event.target.value })}>
          <option value="personal">{t("eventPersonal")}</option><option value="meeting">{t("eventMeeting")}</option>
          <option value="business_trip">{t("eventTrip")}</option></select></label>
        <label>{t("eventStart")}<input type="datetime-local" required value={form.starts_at}
          onChange={(event) => setForm({ ...form, starts_at: event.target.value })}/></label>
        <label>{t("eventEnd")}<input type="datetime-local" value={form.ends_at || ""}
          onChange={(event) => setForm({ ...form, ends_at: event.target.value })}/></label>
        <label>{t("eventVisibility")}<select value={form.visibility}
          onChange={(event) => setForm({ ...form, visibility: event.target.value })}>
          <option value="private">{t("privateEvent")}</option>
          {data.user.store_id && <option value="store">{t("storeEvent")}</option>}
          {canCompany && <option value="company">{t("companyEvent")}</option>}
        </select></label>
        <label className="calendar-all-day"><input type="checkbox" checked={form.all_day}
          onChange={(event) => setForm({ ...form, all_day: event.target.checked })}/>{t("allDay")}</label>
        <div className="calendar-form-actions">
          <button className="primary-btn" disabled={saving}>{saving ? "…" : editing ? t("updateSchedule") : t("saveSchedule")}</button>
          <button type="button" className="secondary-btn" onClick={() => { setForm(null); setEditing(null); }}>{t("cancelEdit")}</button>
        </div>
      </form>}
      <RequestFeedback status={loadStatus} t={t} onRetry={load}/>
      {loadStatus.state === "success" && <><div className="calendar-desktop" role="region" tabIndex={0} aria-label={t("schedule")}>
        <div className="calendar-week-grid">
          <div className="calendar-person-head">{t("queueOwner")}</div>
          {days.map((day) => <div className="calendar-day-head" key={localDate(day)}>
            <b>{day.toLocaleDateString(locale === "ja" ? "ja-JP" : "zh-CN", { weekday: "short" })}</b>
            <span>{day.getMonth() + 1}/{day.getDate()}</span>
          </div>)}
          {visibleEmployees.map((staff) => <React.Fragment key={staff.id}>
            <div className="calendar-person"><b>{staff.name}</b><small>{staff.store_name || roleLabel(locale, staff.role)}</small></div>
            {days.map((day) => {
              const items = eventRows(staff.id, localDate(day));
              return <div className="calendar-cell" key={`${staff.id}-${localDate(day)}`}>
                {items.map((item) => <button key={item.id} className={`calendar-event event-${item.event_type}`}
                  onClick={() => editEvent(item)} title={item.title}>
                  <b>{item.title}</b><small>{[eventLabel(item), visibilityLabel(item)].filter(Boolean).join(" · ")}</small>
                </button>)}
              </div>;
            })}
          </React.Fragment>)}
        </div>
      </div>
      <div className="calendar-mobile">
        {days.map((day) => {
          const items = visibleEvents.filter((item) => String(item.starts_at).slice(0, 10) === localDate(day));
          return <section key={localDate(day)} className="calendar-mobile-day">
            <h3>{day.toLocaleDateString(locale === "ja" ? "ja-JP" : "zh-CN", { weekday: "long", month: "numeric", day: "numeric" })}</h3>
            {items.map((item) => <button key={item.id} className={`calendar-event event-${item.event_type}`}
              onClick={() => editEvent(item)}><b>{item.title}</b><small>{[item.owner_name, eventLabel(item), visibilityLabel(item)].filter(Boolean).join(" · ")}</small></button>)}
            {!items.length && <p className="muted">{t("calendarEmpty")}</p>}
          </section>;
        })}
      </div>
      {!visibleEmployees.length ? <div className="calendar-empty">{t("calendarNoEmployees")}</div> : (!visibleEvents.length && !form && <div className="calendar-empty">{t("calendarWeekEmpty")}</div>)}</>}
    </section>
  </div>;
}

function BulletinView({ displayDate, data, role, t, locale, api }) {
  const [items, setItems] = useState([]);
  const [category, setCategory] = useState("");
  const [query, setQuery] = useState("");
  const [month, setMonth] = useState("");
  const [composer, setComposer] = useState(false);
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState("");
  const [loadStatus, setLoadStatus] = useState({ state: "loading" });
  const loadRequestId = useRef(0);
  const [saving, setSaving] = useState(false);
  const [drafts, setDrafts] = useState({});
  const [form, setForm] = useState({
    post_type: "shared", title: "", body: "", visibility: "private", status: "published",
  });
  const canBroadcast = role !== "advisor" && data.account_role !== "finance";
  const categories = canBroadcast
    ? ["daily_report", "meeting", "notice", "shared"] : ["daily_report", "shared"];

  async function load() {
    const requestId = ++loadRequestId.current;
    setLoadStatus({ state: "loading" });
    const params = new URLSearchParams();
    if (category) params.set("category", category);
    if (query.trim()) params.set("q", query.trim());
    if (month) params.set("month", month);
    try {
      const result = await request(`/api/bulletin?${params.toString()}`, "GET", undefined, locale);
      if (requestId !== loadRequestId.current) return;
      setItems(result.items || []);
      setLoadStatus({ state: "success" });
    } catch (loadError) {
      if (requestId === loadRequestId.current) setLoadStatus({ state: "error", message: loadError.message });
    }
  }
  useEffect(() => {
    const timer = setTimeout(load, query.trim() ? 250 : 0);
    return () => clearTimeout(timer);
  }, [category, month, query]);
  function startNew(postType = "shared") {
    setEditing(null);
    setForm({
      post_type: postType, title: "", body: "", visibility: "private", status: "published",
      report_date: todayJst(),
    });
    setComposer(true);
  }
  function startEdit(post) {
    setEditing(post);
    setForm({ post_type: post.post_type, title: post.title, body: post.body,
      visibility: post.visibility, status: post.status, pinned: Boolean(post.pinned) });
    setComposer(true);
  }
  async function savePost(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      if (editing) await api(`/api/bulletin/${editing.id}`, "PUT", form);
      else await api("/api/bulletin", "POST", form);
      setComposer(false);
      setEditing(null);
      await load();
    } catch (saveError) { setError(saveError.message); }
    finally { setSaving(false); }
  }
  async function archive(post) {
    if (!window.confirm(`${t("archivePost")}？`)) return;
    try { await api(`/api/bulletin/${post.id}/archive`, "POST", {}); await load(); }
    catch (archiveError) { setError(archiveError.message); }
  }
  async function addComment(post) {
    const body = drafts[post.id]?.trim();
    if (!body) return;
    try {
      await api(`/api/bulletin/${post.id}/comments`, "POST", { body });
      setDrafts({ ...drafts, [post.id]: "" });
      await load();
    } catch (commentError) { setError(commentError.message); }
  }
  function categoryLabel(key) {
    return t(({ daily_report: "postDaily", meeting: "postMeeting", notice: "postNotice", shared: "postShared" })[key]);
  }
  const filtersActive = Boolean(category || query.trim() || month);
  return <div className="bulletin-workspace">
    <section className="panel bulletin-panel">
      <div className="bulletin-toolbar">
        <label className="searchbox"><Search size={16}/><input value={query} onChange={(event) => {
          loadRequestId.current += 1;
          setLoadStatus({ state: "loading" });
          setQuery(event.target.value);
        }} aria-label={t("searchPosts")} placeholder={t("searchPosts")}/></label>
        <select aria-label={t("postCategory")} value={category} onChange={(event) => setCategory(event.target.value)}>
          <option value="">{t("all")}</option>{categories.map((item) => <option key={item} value={item}>{categoryLabel(item)}</option>)}
        </select>
        <div className="bulletin-month-control"><label>{t("postMonth")}<input type="month" value={month} onChange={(event) => setMonth(event.target.value)}/></label>{month ? <button type="button" className="text-button" onClick={() => setMonth("")}>{t("bulletinClearMonth")}</button> : <span className="bulletin-month-all">{t("bulletinAllMonths")}</span>}</div>
        <button className="primary-btn" onClick={() => startNew()}><Plus size={15}/>{t("publishPost")}</button>
        <button className="secondary-btn" onClick={() => startNew("daily_report")}>{t("dailyReportPublish")}</button>
      </div>
      {error && <div className="config-error" role="alert">{error}</div>}
      {composer && <form className="bulletin-composer" onSubmit={savePost}>
        <label>{t("postCategory")}<select value={form.post_type} disabled={Boolean(editing)}
          onChange={(event) => setForm({ ...form, post_type: event.target.value })}>
          {categories.map((item) => <option key={item} value={item}>{categoryLabel(item)}</option>)}
        </select></label>
        {form.post_type === "daily_report" ? <label>{t("reportDate")}<input type="date" value={form.report_date}
          onChange={(event) => setForm({ ...form, report_date: event.target.value })}/></label>
          : <><label>{t("postTitle")}<input maxLength="255" required value={form.title}
            onChange={(event) => setForm({ ...form, title: event.target.value })}/></label>
            <label>{t("postBody")}<textarea rows="5" maxLength="20000" required value={form.body}
              onChange={(event) => setForm({ ...form, body: event.target.value })}/></label></>}
        <label>{t("postVisibility")}<select value={form.visibility}
          onChange={(event) => setForm({ ...form, visibility: event.target.value })}>
          <option value="private">{t("privateEvent")}</option>
          {data.user.store_id && <option value="store">{t("storeEvent")}</option>}
          {canBroadcast && <option value="company">{t("companyEvent")}</option>}
        </select></label>
        {canBroadcast && <label className="bulletin-pin"><input type="checkbox" checked={Boolean(form.pinned)}
          onChange={(event) => setForm({ ...form, pinned: event.target.checked })}/>{t("pinPost") || t("postNotice")}</label>}
        <div className="calendar-form-actions">
          <button className="primary-btn" disabled={saving}>{saving ? "…" : t("publishPost")}</button>
          <button type="button" className="secondary-btn" onClick={() => { setComposer(false); setEditing(null); }}>{t("cancelEdit")}</button>
        </div>
      </form>}
      <RequestFeedback status={loadStatus} t={t} onRetry={load}/>
      {loadStatus.state === "success" && <div className="bulletin-list">
        {items.map((post) => <article className="bulletin-post" key={post.id}>
          <div className="bulletin-post-head"><div><span className="pill pill-blue">{categoryLabel(post.post_type)}</span>
            {post.pinned ? <span className="pill pill-amber">{t("pinPost") || "★"}</span> : null}
            <h2>{post.title}</h2><small>{post.author_name} · {post.store_name || t("companyEvent")} · {displayDate(post.published_at || post.created_at)}</small></div>
            {(post.author_id === data.user.id || canBroadcast) && <div className="bulletin-post-actions">
              {post.author_id === data.user.id && post.post_type !== "daily_report" && <button className="text-button" onClick={() => startEdit(post)}>{t("editPost")}</button>}
              <button className="text-button" onClick={() => archive(post)}>{t("archivePost")}</button>
            </div>}</div>
          <p className="bulletin-post-body">{post.body}</p>
          <div className="bulletin-comments"><div className="comment-list">
            {(post.comments || []).map((comment) => <p key={comment.id}><b>{comment.author_name}</b><span>{comment.body}</span></p>)}
          </div>
          {post.status === "published" && <div className="comment-input"><MessageSquare size={15}/>
            <input maxLength="4000" value={drafts[post.id] || ""} placeholder={t("comment")}
              onChange={(event) => setDrafts({ ...drafts, [post.id]: event.target.value })}/>
            <button className="secondary-btn" onClick={() => addComment(post)}>{t("addComment")}</button>
          </div>}</div>
        </article>)}
        {!items.length && <div className="empty-state">{t(filtersActive ? "bulletinNoMatchingPosts" : "bulletinNoPosts")}</div>}
      </div>}
    </section>
  </div>;
}

function NegotiationQueue({ displayDate, stageLabel, data, locale, t, onHousehold }) {
  const [items, setItems] = useState([]);
  const [drafts, setDrafts] = useState({});
  const [error, setError] = useState("");
  const [loadStatus, setLoadStatus] = useState({ state: "loading" });
  const [saving, setSaving] = useState(null);
  async function load() {
    setLoadStatus({ state: "loading" });
    try {
      const result = await request("/api/negotiation-queue", "GET", undefined, locale);
      setItems(result.items || []);
      setDrafts(Object.fromEntries((result.items || []).map((item) => [item.negotiation_id, {
        next_action: item.next_action || "", next_action_due: item.next_action_due || "",
        owner_id: item.owner_id || data.advisors?.[0]?.id || data.user.id,
        risk_level: item.risk_level || "none", version: item.version,
      }])));
      setLoadStatus({ state: "success" });
    } catch (loadError) { setLoadStatus({ state: "error", message: loadError.message }); }
  }
  useEffect(() => { load(); }, []);
  async function save(item) {
    setSaving(item.negotiation_id);
    setError("");
    try {
      const draft = drafts[item.negotiation_id];
      await request(`/api/negotiation-queue/${item.negotiation_id}`, "PUT", {
        ...draft, next_action: draft.next_action.trim() || null,
        next_action_due: draft.next_action.trim() ? draft.next_action_due || null : null,
        owner_id: Number(draft.owner_id) || null,
      }, locale);
      await load();
    } catch (saveError) { setError(saveError.message); }
    finally { setSaving(null); }
  }
  const advisors = data.advisors || [];
  function update(id, field, value) {
    setDrafts((current) => ({ ...current, [id]: { ...current[id], [field]: value } }));
  }
  return <section className="panel negotiation-queue-panel">
    <div className="panel-head"><div><div className="eyebrow">{t("collaboration")}</div><h2>{t("negotiationQueue")}</h2></div>
      <span className="pill pill-blue">{items.length}</span></div>
    {error && <div className="config-error" role="alert">{error}</div>}
    {(loadStatus.state === "error" || !items.length) && <RequestFeedback status={loadStatus} t={t} onRetry={load}/>}
    {items.map((item) => {
      const draft = drafts[item.negotiation_id];
      if (!draft) return null;
      return <article className={`negotiation-queue-row risk-${item.risk_level}`} key={item.negotiation_id}>
        <div className="negotiation-queue-summary">
          <button className="text-button" onClick={() => {
            const household = data.households.find((record) => record.id === item.household_id);
            if (household) onHousehold(household);
          }}><b>{item.representative_name}</b></button>
          <span>{item.store_name} · {item.partner_name} · {stageLabel(locale, item.stage)}</span>
          <small>{t("last")}: {displayDate(item.last_activity_at)} · {item.household_code}</small>
        </div>
        <div className="negotiation-queue-fields">
          <label>{t("queueAction")}<input maxLength="255" value={draft.next_action}
            onChange={(event) => update(item.negotiation_id, "next_action", event.target.value)}/></label>
          <label>{t("due")}<input type="date" value={draft.next_action_due}
            onChange={(event) => update(item.negotiation_id, "next_action_due", event.target.value)}/></label>
          <label>{t("queueOwner")}<select value={draft.owner_id}
            onChange={(event) => update(item.negotiation_id, "owner_id", event.target.value)}>
            {advisors.map((advisor) => <option key={advisor.id} value={advisor.id}>{advisor.name}</option>)}
          </select></label>
          <label>{t("queueRisk")}<select value={draft.risk_level}
            onChange={(event) => update(item.negotiation_id, "risk_level", event.target.value)}>
            <option value="none">{t("riskNone")}</option><option value="watch">{t("riskWatch")}</option>
            <option value="high">{t("riskHigh")}</option></select></label>
          <button className="secondary-btn" disabled={saving === item.negotiation_id} onClick={() => save(item)}>
            {saving === item.negotiation_id ? "…" : t("saveQueueAction")}</button>
        </div>
      </article>;
    })}
    {!items.length && loadStatus.state === "success" && <div className="empty-state">{t("noNegotiations")}</div>}
  </section>;
}
