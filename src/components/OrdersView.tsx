import { useMemo, useState } from "react";
import { FileText, Search, X } from "lucide-react";
import { formatSignedPct, toneOf } from "../utils/format";

export type Order = {
  id: string;
  ticker: string;
  symbol: string;
  company: string;
  segments: string[];
  date: string;
  announcedAt: string;
  customer: string | null;
  orderType: string;
  scope: string | null;
  valueCr: number | null;
  valueBand?: string | null;
  durationMonths: number | null;
  annualValueCr: number | null;
  summary: string;
  pdf: string;
  source: string;
  textRead: boolean;
  d1: number | null;
  d3: number | null;
  d5: number | null;
  mcapCr: number | null;
  revenueCr: number | null;
  revenueBasis: string | null;
  orderSizePct: number | null;
  pctOfMcap: number | null;
};

export type OrdersData = {
  updatedAt: string;
  windowStart: string;
  trackedCompanies: number;
  sources: string[];
  notes: string;
  orders: Order[];
};

type Key = "company" | "customer" | "orderType" | "date" | "valueCr" | "durationMonths" | "annualValueCr" | "orderSizePct" | "revenueCr" | "mcapCr" | "d1" | "d3" | "d5";
const RANGES: { id: string; label: string; days: number | null }[] = [
  { id: "7", label: "7D", days: 7 },
  { id: "30", label: "30D", days: 30 },
  { id: "90", label: "90D", days: 90 },
  { id: "all", label: "All", days: null },
];
const SEGS = ["All", "Active", "Events", "Sovrenn"];

const cr = (n: number | null | undefined) =>
  n == null ? "Not mentioned" : `₹${n.toLocaleString("en-IN", { maximumFractionDigits: n >= 100 ? 1 : 2 })} Cr`;
const crPlain = (n: number | null | undefined) => (n == null ? "n/a" : `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 1 })} Cr`);
const fmtDate = (d: string) => new Date(d + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
const dur = (m: number | null) => (m == null ? "Not mentioned" : m < 1 ? `${Math.round(m * 30)} days` : `${+m.toFixed(1)} months`);

function sizeClass(p: number | null) {
  if (p == null) return "osz osz-na";
  if (p >= 20) return "osz osz-xl";
  if (p >= 10) return "osz osz-l";
  if (p >= 3) return "osz osz-m";
  return "osz osz-s";
}

export function OrdersView({ data, loadError }: { data: OrdersData | null; loadError: string | null }) {
  const [view, setView] = useState<"orders" | "company">("orders");
  const [company, setCompany] = useState("");
  const [customer, setCustomer] = useState("");
  const [minSize, setMinSize] = useState("");
  const [minMcap, setMinMcap] = useState("");
  const [range, setRange] = useState("90");
  const [seg, setSeg] = useState("All");
  const [sortKey, setSortKey] = useState<Key>("date");
  const [asc, setAsc] = useState(false);

  const companies = useMemo(() => {
    const m = new Map<string, string>();
    data?.orders.forEach((o) => m.set(o.symbol, o.company));
    return [...m.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  }, [data]);

  const filtered = useMemo(() => {
    if (!data) return [];
    const r = RANGES.find((x) => x.id === range);
    const since = r?.days ? new Date(Date.now() - r.days * 864e5).toISOString().slice(0, 10) : "";
    const ms = parseFloat(minSize);
    const mm = parseFloat(minMcap);
    return data.orders.filter(
      (o) =>
        (!company || o.symbol === company) &&
        (!customer || (o.customer ?? "").toLowerCase().includes(customer.toLowerCase())) &&
        (isNaN(ms) || (o.orderSizePct ?? -1) >= ms) &&
        (isNaN(mm) || (o.mcapCr ?? -1) >= mm) &&
        (!since || o.date >= since) &&
        (seg === "All" || o.segments.includes(seg)),
    );
  }, [data, company, customer, minSize, minMcap, range, seg]);

  const rows = useMemo(() => {
    const v = (o: Order): string | number => {
      if (sortKey === "date") return o.announcedAt;
      const x = (o as unknown as Record<string, unknown>)[sortKey];
      return typeof x === "number" || typeof x === "string" ? x : -Infinity;
    };
    return filtered.slice().sort((a, b) => {
      const x = v(a), y = v(b);
      const c = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
      return asc ? c : -c;
    });
  }, [filtered, sortKey, asc]);

  const byCompany = useMemo(() => {
    const m = new Map<string, { symbol: string; company: string; n: number; total: number; annual: number; rev: number | null; mcap: number | null; last: string; segs: string[] }>();
    filtered.forEach((o) => {
      const e = m.get(o.symbol) ?? { symbol: o.symbol, company: o.company, n: 0, total: 0, annual: 0, rev: o.revenueCr, mcap: o.mcapCr, last: o.date, segs: o.segments };
      e.n += 1;
      e.total += o.valueCr ?? 0;
      e.annual += o.annualValueCr ?? 0;
      if (o.date > e.last) e.last = o.date;
      m.set(o.symbol, e);
    });
    return [...m.values()].sort((a, b) => b.total - a.total);
  }, [filtered]);

  if (loadError) return <div className="empty">Could not load orders: {loadError}</div>;
  if (!data) return <div className="loading">Loading…</div>;

  const total = filtered.reduce((s, o) => s + (o.valueCr ?? 0), 0);
  const big = filtered.filter((o) => (o.orderSizePct ?? 0) >= 10).length;
  const latest = data.orders[0]?.date;

  const sortBy = (k: Key) => {
    if (sortKey === k) setAsc(!asc);
    else {
      setSortKey(k);
      setAsc(false);
    }
  };
  const th = (k: Key, label: string, num = false) => (
    <th className={`sortable ${num ? "num" : ""} ${sortKey === k ? "sorted" : ""}`} onClick={() => sortBy(k)}>
      {label}
      <span className="sort-ind">{sortKey === k ? (asc ? "▲" : "▼") : ""}</span>
    </th>
  );
  const pctCell = (n: number | null) => <td className={`num ${toneOf(n)}`}>{n == null ? "—" : formatSignedPct(n)}</td>;
  const clear = () => {
    setCompany("");
    setCustomer("");
    setMinSize("");
    setMinMcap("");
  };

  return (
    <section className="stack">
      <div className="kpis">
        <div className="kpi static">
          <span className="kpi-label">Orders</span>
          <span className="kpi-value">{filtered.length}</span>
          <span className="kpi-hint">in view · {data.orders.length} since {fmtDate(data.windowStart)}</span>
        </div>
        <div className="kpi static">
          <span className="kpi-label">Total value</span>
          <span className="kpi-value">{crPlain(Math.round(total))}</span>
          <span className="kpi-hint">where the filing stated a value</span>
        </div>
        <button type="button" className={`kpi kpi-buy ${minSize === "10" ? "active" : ""}`} onClick={() => setMinSize(minSize === "10" ? "" : "10")}>
          <span className="kpi-label"><span className="zone-dot dot-buy" aria-hidden />Big orders</span>
          <span className="kpi-value">{big}</span>
          <span className="kpi-hint">≥10% of revenue · tap to filter</span>
        </button>
        <div className="kpi static">
          <span className="kpi-label">Latest filing</span>
          <span className="kpi-value kpi-date">{latest ? fmtDate(latest) : "—"}</span>
          <span className="kpi-hint">{byCompany.length} companies in view · of {data.trackedCompanies} tracked</span>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <div>
            <h2 className="panel-title">Order tracker</h2>
            <p className="panel-sub">Order wins, LoAs and contracts from NSE/BSE filings for Active, Events and Sovrenn names · updated {data.updatedAt.replace("T", " ").slice(0, 16)} IST</p>
          </div>
          <div className="panel-tools">
            <div className="period-toggle">
              <button type="button" className={`pill ${view === "orders" ? "active" : ""}`} onClick={() => setView("orders")}>Order view</button>
              <button type="button" className={`pill ${view === "company" ? "active" : ""}`} onClick={() => setView("company")}>Company view</button>
            </div>
          </div>
        </div>

        <div className="ord-filters">
          <label className="select-box ord-company">
            <select value={company} onChange={(e) => setCompany(e.target.value)} aria-label="Company">
              <option value="">All companies</option>
              {companies.map(([s, n]) => (
                <option key={s} value={s}>{n} ({s})</option>
              ))}
            </select>
          </label>
          <label className="search-box">
            <Search size={15} aria-hidden />
            <input placeholder="Customer" value={customer} onChange={(e) => setCustomer(e.target.value)} />
          </label>
          <label className="search-box">
            <input inputMode="decimal" placeholder="Min order size %" value={minSize} onChange={(e) => setMinSize(e.target.value)} />
            <span className="muted small">%</span>
          </label>
          <label className="search-box">
            <input inputMode="decimal" placeholder="Min market cap" value={minMcap} onChange={(e) => setMinMcap(e.target.value)} />
            <span className="muted small">₹ Cr</span>
          </label>
          {(company || customer || minSize || minMcap) && (
            <button type="button" className="pill pill-clear" onClick={clear}><X size={13} /> Clear</button>
          )}
        </div>
        <div className="pill-row">
          {RANGES.map((r) => (
            <button key={r.id} type="button" className={`pill ${range === r.id ? "active" : ""}`} onClick={() => setRange(r.id)}>{r.label}</button>
          ))}
          <span className="ord-sep" />
          {SEGS.map((s) => (
            <button key={s} type="button" className={`pill ${seg === s ? "active" : ""}`} onClick={() => setSeg(s)}>{s}</button>
          ))}
        </div>
        <details className="method">
          <summary>How the columns are calculated</summary>
          <p>
            Values, customers and durations are read from each exchange filing; "Not mentioned" means the filing didn't say or the PDF is a scan.
            Annual value = contract value spread over its duration when that's longer than 12 months. Order size % = annual value ÷ company revenue
            (trailing twelve months where available). 1D/3D/5D = % move from the last close before the filing. A same-day press release that repeats
            an order filing is counted once.
          </p>
        </details>

        {view === "orders" ? (
          <div className="table-wrap">
            <table className="data-table ord-table">
              <thead>
                <tr>
                  {th("company", "Company")}
                  {th("customer", "Customer")}
                  {th("orderType", "Order type")}
                  {th("date", "Date")}
                  {th("valueCr", "Contract value", true)}
                  {th("durationMonths", "Duration")}
                  {th("annualValueCr", "Annual value", true)}
                  {th("orderSizePct", "Order size %", true)}
                  {th("revenueCr", "Company revenue", true)}
                  {th("mcapCr", "Market cap", true)}
                  {th("d1", "1D", true)}
                  {th("d3", "3D", true)}
                  {th("d5", "5D", true)}
                  <th>PDF</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((o) => (
                  <tr key={o.id} title={o.summary}>
                    <td className="ord-co">
                      <button type="button" className="link-btn" onClick={() => setCompany(o.symbol)}>{o.company}</button>
                      <div className="muted small mono">{o.symbol} · {o.segments.join(" / ")}</div>
                    </td>
                    <td className="ord-cust" title={o.customer ?? ""}>{o.customer ?? <span className="muted">Not mentioned</span>}</td>
                    <td className={o.orderType === "Not mentioned" ? "muted" : ""}>{o.orderType}{o.scope === "International" && <span className="tag-chip sme">Intl</span>}</td>
                    <td className="mono nowrap">{fmtDate(o.date)}</td>
                    <td className={`num ${o.valueCr == null ? "muted" : "ord-val"}`} title={o.valueBand ?? ""}>{o.valueCr == null && o.valueBand ? o.valueBand.replace(/ \(.*\)$/, "") : cr(o.valueCr)}</td>
                    <td className={o.durationMonths == null ? "muted" : ""}>{dur(o.durationMonths)}</td>
                    <td className={`num ${o.annualValueCr == null ? "muted" : ""}`}>{cr(o.annualValueCr)}</td>
                    <td className="num"><span className={sizeClass(o.orderSizePct)}>{o.orderSizePct == null ? "n/a" : `${o.orderSizePct.toFixed(2)}%`}</span></td>
                    <td className="num muted nowrap">{o.revenueCr == null ? "n/a" : `${crPlain(o.revenueCr)} (${o.revenueBasis ?? ""})`}</td>
                    <td className="num nowrap">{crPlain(o.mcapCr)}</td>
                    {pctCell(o.d1)}
                    {pctCell(o.d3)}
                    {pctCell(o.d5)}
                    <td>
                      <a className="ord-pdf" href={o.pdf} target="_blank" rel="noreferrer" title={`Open filing (${o.source})`}><FileText size={16} /></a>
                    </td>
                  </tr>
                ))}
                {!rows.length && (
                  <tr><td colSpan={14} className="empty compact">No orders match these filters.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="table-wrap">
            <table className="data-table ord-table">
              <thead>
                <tr>
                  <th>Company</th><th className="num">Orders</th><th className="num">Total value</th><th className="num">Annualised</th>
                  <th className="num">% of revenue</th><th className="num">% of market cap</th><th>Latest order</th>
                </tr>
              </thead>
              <tbody>
                {byCompany.map((c) => (
                  <tr key={c.symbol} className="clickable" onClick={() => { setCompany(c.symbol); setView("orders"); }}>
                    <td className="ord-co"><span className="link-btn">{c.company}</span><div className="muted small mono">{c.symbol} · {c.segs.join(" / ")}</div></td>
                    <td className="num">{c.n}</td>
                    <td className="num ord-val">{crPlain(c.total || null)}</td>
                    <td className="num">{crPlain(c.annual || null)}</td>
                    <td className="num"><span className={sizeClass(c.rev ? (c.annual / c.rev) * 100 : null)}>{c.rev && c.annual ? `${((c.annual / c.rev) * 100).toFixed(1)}%` : "n/a"}</span></td>
                    <td className="num">{c.mcap && c.total ? `${((c.total / c.mcap) * 100).toFixed(1)}%` : "n/a"}</td>
                    <td className="mono">{fmtDate(c.last)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
