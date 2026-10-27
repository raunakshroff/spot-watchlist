import { Fragment, useMemo, useState } from "react";
import type { EventCompany, EventsData, MacroEvent } from "../types";
import { Search, ArrowUpDown, ExternalLink, CalendarDays } from "lucide-react";
import { formatInr, formatPct, formatSignedPct, toneOf } from "../utils/format";

type Key =
  | "ticker"
  | "name"
  | "confidence"
  | "buyZone"
  | "price"
  | "pctSinceEvent"
  | "priceAtEvent"
  | "rsi14";

const COLS: { key: Key; label: string }[] = [
  { key: "ticker", label: "Symbol" },
  { key: "name", label: "Name" },
  { key: "confidence", label: "Link" },
  { key: "buyZone", label: "Buy zone" },
  { key: "price", label: "Current" },
  { key: "pctSinceEvent", label: "% since event" },
  { key: "priceAtEvent", label: "Price @ event" },
  { key: "rsi14", label: "RSI" },
];

const NUM_COLS = new Set<Key>(["price", "pctSinceEvent", "priceAtEvent", "rsi14"]);
const CONF_RANK: Record<string, number> = { high: 3, med: 2, low: 1 };

function sym(c: EventCompany) {
  return c.ticker.replace(/\.(NS|BO)$/, "");
}

function confChip(c: EventCompany) {
  const k = c.confidence;
  return (
    <span className={`tag-chip conf-${k}`} title={`Linkage confidence: ${k}`}>
      {k}
    </span>
  );
}

function bzChip(c: EventCompany) {
  return (
    <span
      className={`zone ${c.buyZone === "Y" ? "zone-buy" : c.buyZone === "N" ? "zone-wait" : "zone-na"}`}
      title={c.buyZoneNote ?? undefined}
    >
      <span className="zone-dot" aria-hidden />
      {c.buyZone === "Y" ? "Buy zone" : c.buyZone === "N" ? "Not yet" : "n/a"}
    </span>
  );
}

export function EventsView({ data, loadError }: { data: EventsData | null; loadError: string | null }) {
  const [eventId, setEventId] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<Key>("pctSinceEvent");
  const [asc, setAsc] = useState(false);
  const [q, setQ] = useState("");
  const [onlyBz, setOnlyBz] = useState(false);
  const [open, setOpen] = useState<string | null>(null);

  const events = data?.events ?? [];
  const selected: MacroEvent | null = useMemo(() => {
    if (!events.length) return null;
    const id = eventId && events.some((e) => e.id === eventId) ? eventId : events[0].id;
    return events.find((e) => e.id === id) ?? events[0];
  }, [events, eventId]);

  const rows = useMemo(() => {
    if (!selected) return [];
    const val = (c: EventCompany): string | number => {
      if (sortKey === "ticker") return sym(c);
      if (sortKey === "buyZone") return c.buyZone === "Y" ? 2 : c.buyZone === "N" ? 1 : 0;
      if (sortKey === "confidence") return CONF_RANK[c.confidence] ?? 0;
      const v = (c as unknown as Record<string, unknown>)[sortKey];
      return typeof v === "number" || typeof v === "string" ? v : -Infinity;
    };
    return selected.companies
      .filter((c) => !onlyBz || c.buyZone === "Y")
      .filter(
        (c) =>
          !q ||
          `${c.name} ${sym(c)} ${c.why} ${(c.packages ?? []).join(" ")}`.toLowerCase().includes(q.toLowerCase()),
      )
      .slice()
      .sort((a, b) => {
        const x = val(a),
          y = val(b);
        const cmp =
          typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
        return asc ? cmp : -cmp;
      });
  }, [selected, sortKey, asc, q, onlyBz]);

  if (loadError) return <div className="empty">Could not load Events: {loadError}</div>;
  if (!data) return <div className="loading">Loading…</div>;
  if (!selected) return <div className="empty">No events yet — seed one under public/data/events.json.</div>;

  const bz = selected.companies.filter((c) => c.buyZone === "Y").length;
  const perf = selected.companies.filter((c) => c.pctSinceEvent != null).map((c) => c.pctSinceEvent as number);
  const avgPerf = perf.length ? perf.reduce((a, b) => a + b, 0) / perf.length : null;
  const winners = perf.filter((x) => x > 0).length;
  const promoted = selected.companies.filter((c) => c.promotedToActive).length;

  const sortBy = (k: Key) => {
    if (sortKey === k) setAsc(!asc);
    else {
      setSortKey(k);
      setAsc(false);
    }
  };

  const detail = (c: EventCompany) => (
    <div className="sv-detail">
      <p>{c.why}</p>
      {c.packages?.length ? (
        <div className="ev-packages">
          {c.packages.map((p) => (
            <span key={p} className="tag-chip">
              {p}
            </span>
          ))}
        </div>
      ) : null}
      <div className="sv-check">
        Buy-zone check: {c.buyZoneNote ?? "n/a"} · 20/50/200 DMA {c.dma20 ?? "n/a"} / {c.dma50 ?? "n/a"} /{" "}
        {c.dma200 ?? "n/a"} · Yahoo {c.ticker} · price as of {c.priceDate ?? "n/a"}
        {c.promotedToActive ? ` · promoted to Active${c.promotedDate ? ` on ${c.promotedDate}` : ""}` : ""}
      </div>
    </div>
  );

  return (
    <section className="stack">
      <div className="panel">
        <div className="panel-head">
          <div>
            <h2 className="panel-title">Events</h2>
            <p className="panel-sub">
              Macro catalysts and the listed names that may benefit · pick an event · daily prices refresh with
              Auto-promote near breakouts to Active
            </p>
          </div>
        </div>
        <div className="ev-list" role="list">
          {events.map((e) => {
            const active = e.id === selected.id;
            return (
              <button
                key={e.id}
                type="button"
                role="listitem"
                className={`ev-card ${active ? "active" : ""}`}
                onClick={() => {
                  setEventId(e.id);
                  setOpen(null);
                }}
                aria-pressed={active}
              >
                <div className="ev-card-top">
                  <CalendarDays size={14} aria-hidden />
                  <span className="mono muted">{e.date}</span>
                  {e.amountCr != null && (
                    <span className="tag-chip">₹{(e.amountCr / 1000).toFixed(e.amountCr >= 100000 ? 0 : 1)}k Cr</span>
                  )}
                  {e.indigenousPct != null && <span className="tag-chip">{e.indigenousPct}% Indian</span>}
                </div>
                <div className="ev-card-title">{e.title}</div>
                <div className="ev-card-meta muted small">
                  {e.companies.length} companies ·{" "}
                  {e.companies.filter((c) => c.buyZone === "Y").length} in buy zone
                </div>
              </button>
            );
          })}
        </div>
      </div>

      <div className="kpis">
        <div className="kpi static">
          <span className="kpi-label">Beneficiaries</span>
          <span className="kpi-value">{selected.companies.length}</span>
          <span className="kpi-hint">listed · Events tab only</span>
        </div>
        <button type="button" className={`kpi kpi-buy ${onlyBz ? "active" : ""}`} onClick={() => setOnlyBz(!onlyBz)}>
          <span className="kpi-label">
            <span className="zone-dot dot-buy" aria-hidden />
            Buy zone now
          </span>
          <span className="kpi-value">{bz}</span>
          <span className="kpi-hint">{onlyBz ? "filter on · tap to clear" : "tap to filter"}</span>
        </button>
        <div className="kpi static">
          <span className="kpi-label">Avg since event</span>
          <span className={`kpi-value ${toneOf(avgPerf)}`}>{formatSignedPct(avgPerf)}</span>
          <span className="kpi-hint">
            {winners} of {perf.length} up
          </span>
        </div>
        <div className="kpi static">
          <span className="kpi-label">Promoted to Active</span>
          <span className="kpi-value">{promoted}</span>
          <span className="kpi-hint">via daily auto rule</span>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <div>
            <h2 className="panel-title">{selected.title}</h2>
            <p className="panel-sub">
              {selected.date}
              {selected.amountCr != null ? ` · ₹${selected.amountCr.toLocaleString("en-IN")} Cr` : ""} · showing{" "}
              {rows.length} of {selected.companies.length}
            </p>
          </div>
          <div className="panel-tools">
            <label className="search-box">
              <Search size={15} aria-hidden />
              <input
                placeholder="Search name, symbol, package"
                value={q}
                onChange={(e) => setQ(e.target.value)}
              />
            </label>
            <button type="button" className={`pill ${onlyBz ? "active" : ""}`} onClick={() => setOnlyBz(!onlyBz)}>
              Buy zone only
            </button>
          </div>
        </div>

        <details className="method" open={false}>
          <summary>Event summary &amp; sources</summary>
          <p>{selected.summary}</p>
          {selected.packages?.length ? (
            <p>
              <strong>Packages:</strong> {selected.packages.join("; ")}
            </p>
          ) : null}
          <ul className="ev-sources">
            {selected.sources.map((s) => (
              <li key={s.url}>
                <a href={s.url} target="_blank" rel="noreferrer">
                  {s.label} <ExternalLink size={12} aria-hidden />
                </a>
              </li>
            ))}
          </ul>
          <p className="muted small">{data.disclaimer}</p>
        </details>

        <details className="method">
          <summary>How buy zone &amp; auto-promote work</summary>
          <p>
            Buy zone (daily, same as Sovrenn): above 200 DMA, within 0 to +4% of 20/50 DMA, RSI 40–60, not more than
            8% above 20 DMA. Auto-promote to Active (Breakout-watch / Watch) when buy-zone Y <em>or</em> near-breakout
            bundle: above 20 &amp; 50 DMA, RSI 45–68, ≥+2% since event, within 3% of 20-session high, ≤12% above 20 DMA.
            Skips names already on Active or Dropped. Does not invent stop/target levels.
          </p>
        </details>

        <div className="sv-sortbar">
          <ArrowUpDown size={14} />
          <select
            value={sortKey}
            onChange={(e) => {
              setSortKey(e.target.value as Key);
              setAsc(false);
            }}
            aria-label="Sort by"
          >
            {COLS.map((c) => (
              <option key={c.key} value={c.key}>
                {c.label}
              </option>
            ))}
          </select>
          <button type="button" className="btn-ghost" onClick={() => setAsc(!asc)}>
            {asc ? "▲ asc" : "▼ desc"}
          </button>
        </div>

        <div className="table-wrap sv-table-wrap">
          <table className="data-table sv-table">
            <thead>
              <tr>
                {COLS.map((c) => (
                  <th
                    key={c.key}
                    className={`sortable ${NUM_COLS.has(c.key) ? "num" : ""} ${sortKey === c.key ? "sorted" : ""} ${c.key === "ticker" ? "sticky-col" : ""}`}
                    onClick={() => sortBy(c.key)}
                  >
                    {c.label}
                    <span className="sort-ind">{sortKey === c.key ? (asc ? "▲" : "▼") : ""}</span>
                  </th>
                ))}
                <th>Why it benefits</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <Fragment key={c.ticker}>
                  <tr
                    className={`clickable ${open === c.ticker ? "open" : ""}`}
                    onClick={() => setOpen(open === c.ticker ? null : c.ticker)}
                  >
                    <td className="sticky-col">
                      <span className="tkr-sym">{sym(c)}</span>
                      {c.promotedToActive && <span className="tag-chip sme">Active</span>}
                    </td>
                    <td className="name-cell">{c.name}</td>
                    <td>{confChip(c)}</td>
                    <td>{bzChip(c)}</td>
                    <td className="num strong">{c.price != null ? formatInr(c.price) : "n/a"}</td>
                    <td className={`num ${toneOf(c.pctSinceEvent)}`}>
                      {c.pctSinceEvent != null ? formatPct(c.pctSinceEvent) : "n/a"}
                    </td>
                    <td className="num muted">{c.priceAtEvent != null ? formatInr(c.priceAtEvent) : "n/a"}</td>
                    <td className="num">{c.rsi14 ?? "n/a"}</td>
                    <td className="reason-cell" title={c.why}>
                      <div className="clamp-2">{c.why}</div>
                    </td>
                  </tr>
                  {open === c.ticker && (
                    <tr className="detail-row">
                      <td colSpan={COLS.length + 1}>{detail(c)}</td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>

        <div className="sv-cards">
          {rows.map((c) => (
            <article key={c.ticker} className={`wcard ${open === c.ticker ? "open" : ""}`}>
              <button
                type="button"
                className="wcard-main"
                onClick={() => setOpen(open === c.ticker ? null : c.ticker)}
              >
                <div className="wcard-top">
                  <div className="wcard-id">
                    <div className="tkr">
                      <span className="tkr-sym">{sym(c)}</span>
                      {confChip(c)}
                      {c.promotedToActive && <span className="tag-chip sme">Active</span>}
                    </div>
                    <div className="tkr-name">{c.name}</div>
                  </div>
                  <div className="wcard-px">
                    <div className="px">{c.price != null ? formatInr(c.price) : "n/a"}</div>
                    <div className={`px-chg ${toneOf(c.pctSinceEvent)}`}>
                      {c.pctSinceEvent != null ? `${formatPct(c.pctSinceEvent)} since` : "n/a"}
                    </div>
                  </div>
                </div>
                <div className="wcard-mid">{bzChip(c)}</div>
                <div className="wcard-grid">
                  <div>
                    <span className="k">@ event</span>
                    <span className="v">{c.priceAtEvent != null ? formatInr(c.priceAtEvent) : "n/a"}</span>
                  </div>
                  <div>
                    <span className="k">RSI</span>
                    <span className="v">{c.rsi14 ?? "n/a"}</span>
                  </div>
                  <div>
                    <span className="k">Link</span>
                    <span className="v">{c.confidence}</span>
                  </div>
                  <div>
                    <span className="k">Pkgs</span>
                    <span className="v">{c.packages?.length ?? 0}</span>
                  </div>
                </div>
                <div className="wcard-trigger clamp-3">{c.why}</div>
              </button>
              {open === c.ticker && detail(c)}
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
