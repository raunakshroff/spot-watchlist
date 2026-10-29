import { Fragment, useMemo, useState } from "react";
import { ChevronDown, ArrowUpDown } from "lucide-react";
import type { WatchlistStock } from "../types";
import { StatusBadge } from "./StatusBadge";
import { Sparkline } from "./Sparkline";
import { ZoneChip } from "./ZoneChip";
import { AlertChips } from "./AlertChips";
import { computeZone, firstLevel, ZONE_RANK, type Zone } from "../utils/zone";
import { formatInr, formatRsi, formatSignedPct, rsiTone, shortTicker, toneOf } from "../utils/format";

type SortKey = "zone" | "ticker" | "price" | "day" | "dist" | "rsi";

const SORT_LABEL: Record<SortKey, string> = {
  zone: "Urgency (zone)",
  ticker: "Ticker A–Z",
  price: "Price",
  day: "Day %",
  dist: "Distance to stop",
  rsi: "RSI",
};

interface Row {
  s: WatchlistStock;
  z: Zone;
  t1: number | null;
}

function sortRows(rows: Row[], key: SortKey, asc: boolean): Row[] {
  const v = (r: Row): number | string => {
    switch (key) {
      case "ticker":
        return shortTicker(r.s.ticker);
      case "price":
        return r.s.price ?? -Infinity;
      case "day":
        return r.s.dailyPct ?? -Infinity;
      case "dist":
        return r.z.distPct ?? Infinity;
      case "rsi":
        return r.s.rsi14 ?? -Infinity;
      default:
        return ZONE_RANK[r.z.kind] * 1000 + (r.z.distPct ?? 999);
    }
  };
  return [...rows].sort((a, b) => {
    const x = v(a);
    const y = v(b);
    const c = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
    return asc ? c : -c;
  });
}

/** Default direction when a column is first clicked. */
const DEFAULT_ASC: Record<SortKey, boolean> = { zone: true, ticker: true, price: false, day: false, dist: true, rsi: false };

function DistBar({ pct }: { pct: number | null }) {
  if (pct == null) return null;
  const w = Math.min(100, (Math.abs(pct) / 10) * 100);
  const cls = pct < 0 ? "below" : pct <= 1 ? "near" : pct <= 3 ? "mid" : "safe";
  return (
    <span className="dist-bar" aria-hidden>
      <span className={`dist-fill ${cls}`} style={{ width: `${Math.max(4, w)}%` }} />
    </span>
  );
}

function Detail({ s, z }: { s: WatchlistStock; z: Zone }) {
  const pnl = s.sharesHeld && s.avgCost && s.price != null ? (s.price - s.avgCost) * s.sharesHeld : null;
  const pnlPct = s.avgCost && s.price != null ? ((s.price - s.avgCost) / s.avgCost) * 100 : null;
  const levels: [string, string | null][] = [
    ["Entry / triggers", s.buyZoneLevels],
    ["Stop", s.stop],
    ["Target 1", s.target1],
    ["Target 2", s.target2],
    ["Support", s.support],
    ["Resistance", s.resistance],
  ];
  return (
    <div className="wt-detail">
      <div className="wt-detail-col">
        <div className="eyebrow">Thesis</div>
        <p>{s.thesis}</p>
        {s.notes && (
          <>
            <div className="eyebrow">Notes</div>
            <p>{s.notes}</p>
          </>
        )}
        <div className="wt-detail-tags">
          <StatusBadge status={s.status} />
          {s.sector && <span className="sector-chip">{s.sector}</span>}
          <span className="muted small">Added {s.addedDate} · updated {s.lastUpdated}</span>
        </div>
      </div>
      <div className="wt-detail-col">
        <div className="eyebrow">Levels</div>
        <dl className="kv">
          {levels.map(([k, v]) => (
            <Fragment key={k}>
              <dt>{k}</dt>
              <dd>{v ?? "—"}</dd>
            </Fragment>
          ))}
          <dt>Distance to stop</dt>
          <dd className={z.distPct == null ? "" : z.distPct < 0 ? "down" : z.distPct <= 1 ? "warn" : ""}>
            {z.distPct == null ? "—" : `${formatSignedPct(z.distPct, 2)} vs ${formatInr(z.stop)}`}
          </dd>
          {s.alerts?.length ? (
            <>
              <dt>Price alerts</dt>
              <dd>
                {s.alerts.map((a) => (
                  <div key={a.id} className={a.status === "triggered" ? "warn" : ""}>
                    {a.label} · {a.status === "triggered" ? `triggered ${a.triggeredDate} @ ${formatInr(a.triggeredPrice ?? null)}` : `armed since ${a.createdDate}`}
                  </div>
                ))}
              </dd>
            </>
          ) : null}
          <dt>Volume vs 20d</dt>
          <dd>{s.volVs20d == null ? "—" : `${s.volVs20d.toFixed(2)}×`}</dd>
          {s.sharesHeld ? (
            <>
              <dt>Position</dt>
              <dd>
                {s.sharesHeld} sh{s.avgCost ? ` @ ${formatInr(s.avgCost)}` : ""}
                {pnl != null && (
                  <span className={toneOf(pnl)}>
                    {" "}
                    · {pnl >= 0 ? "+" : "−"}₹{Math.abs(Math.round(pnl)).toLocaleString("en-IN")} ({formatSignedPct(pnlPct)})
                  </span>
                )}
              </dd>
            </>
          ) : null}
        </dl>
      </div>
    </div>
  );
}

export function WatchTable({ stocks, emptyText = "No names match this filter." }: { stocks: WatchlistStock[]; emptyText?: string }) {
  const [sortKey, setSortKey] = useState<SortKey>("zone");
  const [asc, setAsc] = useState(true);
  const [open, setOpen] = useState<string | null>(null);

  const rows = useMemo(
    () => sortRows(stocks.map((s) => ({ s, z: computeZone(s), t1: firstLevel(s.target1) })), sortKey, asc),
    [stocks, sortKey, asc],
  );

  const clickSort = (k: SortKey) => {
    if (k === sortKey) setAsc(!asc);
    else {
      setSortKey(k);
      setAsc(DEFAULT_ASC[k]);
    }
  };
  const th = (k: SortKey, label: string, cls = "") => (
    <th className={`sortable ${cls} ${sortKey === k ? "sorted" : ""}`} onClick={() => clickSort(k)} aria-sort={sortKey === k ? (asc ? "ascending" : "descending") : "none"}>
      {label}
      <span className="sort-ind">{sortKey === k ? (asc ? "▲" : "▼") : ""}</span>
    </th>
  );

  if (!stocks.length) return <div className="empty">{emptyText}</div>;

  return (
    <div className="wt">
      {/* Mobile sort control (desktop uses column headers) */}
      <div className="wt-sortbar">
        <ArrowUpDown size={14} />
        <select value={sortKey} onChange={(e) => { const k = e.target.value as SortKey; setSortKey(k); setAsc(DEFAULT_ASC[k]); }} aria-label="Sort by">
          {(Object.keys(SORT_LABEL) as SortKey[]).map((k) => (
            <option key={k} value={k}>{SORT_LABEL[k]}</option>
          ))}
        </select>
        <button type="button" className="btn-ghost" onClick={() => setAsc(!asc)} aria-label="Toggle direction">
          {asc ? "▲ asc" : "▼ desc"}
        </button>
      </div>

      <table className="wt-table">
        <thead>
          <tr>
            {th("ticker", "Stock")}
            {th("zone", "Zone")}
            {th("price", "Price", "num")}
            {th("day", "Day", "num")}
            <th className="num">Stop</th>
            {th("dist", "To stop", "num")}
            <th>Entry / trigger</th>
            <th className="num">Target 1</th>
            {th("rsi", "RSI", "num")}
            <th className="trend-col">20d</th>
            <th aria-label="Expand" />
          </tr>
        </thead>
        <tbody>
          {rows.map(({ s, z, t1 }) => {
            const isOpen = open === s.ticker;
            const up = (s.dailyPct ?? 0) >= 0;
            return (
              <Fragment key={s.ticker}>
                <tr className={`wt-row zone-row-${z.kind} ${isOpen ? "open" : ""}`} onClick={() => setOpen(isOpen ? null : s.ticker)} data-expand>
                  <td>
                    <div className="tkr">
                      <span className="tkr-sym">{shortTicker(s.ticker)}</span>
                      {s.sharesHeld ? <span className="held-chip">{s.sharesHeld} sh</span> : null}
                    </div>
                    <div className="tkr-name">{s.name}</div>
                    <AlertChips alerts={s.alerts} />
                  </td>
                  <td>
                    <ZoneChip kind={z.kind} />
                    <div className="sub-status">{s.status}</div>
                  </td>
                  <td className="num strong">{formatInr(s.price)}</td>
                  <td className={`num ${toneOf(s.dailyPct)}`}>{formatSignedPct(s.dailyPct)}</td>
                  <td className="num muted">{formatInr(z.stop)}</td>
                  <td className="num">
                    <span className={z.kind === "below" ? "down" : z.kind === "near" ? "warn" : ""}>{formatSignedPct(z.distPct)}</span>
                    <DistBar pct={z.distPct} />
                  </td>
                  <td className="lvl-cell" title={s.buyZoneLevels ?? ""}>{s.buyZoneLevels ?? "—"}</td>
                  <td className="num muted">{formatInr(t1)}</td>
                  <td className={`num rsi-${rsiTone(s.rsi14)}`}>{formatRsi(s.rsi14)}</td>
                  <td className="trend-col">
                    <Sparkline data={s.sparkline ?? []} up={up} />
                  </td>
                  <td className="chev-cell">
                    <ChevronDown size={16} className={`chev ${isOpen ? "open" : ""}`} />
                  </td>
                </tr>
                {isOpen && (
                  <tr className="wt-detail-row">
                    <td colSpan={11}>
                      <Detail s={s} z={z} />
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>

      <div className="wt-cards">
        {rows.map(({ s, z, t1 }) => {
          const isOpen = open === s.ticker;
          const up = (s.dailyPct ?? 0) >= 0;
          return (
            <article key={s.ticker} className={`wcard zone-row-${z.kind} ${isOpen ? "open" : ""}`}>
              <button type="button" className="wcard-main" onClick={() => setOpen(isOpen ? null : s.ticker)} aria-expanded={isOpen}>
                <div className="wcard-top">
                  <div className="wcard-id">
                    <div className="tkr">
                      <span className="tkr-sym">{shortTicker(s.ticker)}</span>
                      {s.sharesHeld ? <span className="held-chip">{s.sharesHeld} sh</span> : null}
                    </div>
                    <div className="tkr-name">{s.name} · {s.status}</div>
                  </div>
                  <div className="wcard-px">
                    <div className="px">{formatInr(s.price)}</div>
                    <div className={`px-chg ${toneOf(s.dailyPct)}`}>{formatSignedPct(s.dailyPct)}</div>
                  </div>
                </div>
                <div className="wcard-mid">
                  <ZoneChip kind={z.kind} />
                  <div className="wcard-spark">
                    <Sparkline data={s.sparkline ?? []} up={up} />
                  </div>
                </div>
                <AlertChips alerts={s.alerts} />
                <div className="wcard-grid">
                  <div>
                    <span className="k">Stop</span>
                    <span className="v">{formatInr(z.stop)}</span>
                  </div>
                  <div>
                    <span className="k">To stop</span>
                    <span className={`v ${z.kind === "below" ? "down" : z.kind === "near" ? "warn" : ""}`}>{formatSignedPct(z.distPct)}</span>
                  </div>
                  <div>
                    <span className="k">Target 1</span>
                    <span className="v">{formatInr(t1)}</span>
                  </div>
                  <div>
                    <span className="k">RSI</span>
                    <span className={`v rsi-${rsiTone(s.rsi14)}`}>{formatRsi(s.rsi14)}</span>
                  </div>
                </div>
                <DistBar pct={z.distPct} />
                <div className="wcard-trigger">{s.buyZoneLevels ?? "—"}</div>
                <span className="wcard-more">
                  {isOpen ? "Hide details" : "Details"} <ChevronDown size={14} className={`chev ${isOpen ? "open" : ""}`} />
                </span>
              </button>
              {isOpen && <Detail s={s} z={z} />}
            </article>
          );
        })}
      </div>
    </div>
  );
}
