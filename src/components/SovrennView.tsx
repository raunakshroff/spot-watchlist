import { Fragment, useMemo, useState } from "react";
import type { SovrennEntry } from "../types";
import { Search, ArrowUpDown } from "lucide-react";
import { formatInr, formatPct, formatSignedPct, toneOf } from "../utils/format";

type Key =
  | "ticker"
  | "name"
  | "firstHighlighted"
  | "timesMentioned"
  | "latestDate"
  | "priceAtHighlight"
  | "price"
  | "pctSinceHighlight"
  | "mcapCr"
  | "rsi14"
  | "buyZone";

const COLS: { key: Key; label: string }[] = [
  { key: "ticker", label: "Symbol" },
  { key: "name", label: "Name" },
  { key: "buyZone", label: "Buy zone" },
  { key: "price", label: "Current" },
  { key: "pctSinceHighlight", label: "% since" },
  { key: "priceAtHighlight", label: "Price @ highlight" },
  { key: "latestDate", label: "Latest" },
  { key: "firstHighlighted", label: "First highlighted" },
  { key: "timesMentioned", label: "Mentions" },
  { key: "mcapCr", label: "MCap (₹ Cr)" },
  { key: "rsi14", label: "RSI" },
];

const NUM_COLS = new Set<Key>(["timesMentioned", "priceAtHighlight", "price", "pctSinceHighlight", "mcapCr", "rsi14"]);

function sym(e: SovrennEntry) {
  return e.ticker ? e.ticker.replace(/\.(NS|BO)$/, "") : e.key;
}

export function SovrennView({ data, loadError }: { data: SovrennEntry[] | null; loadError: string | null }) {
  const [sortKey, setSortKey] = useState<Key>("latestDate");
  const [asc, setAsc] = useState(false);
  const [q, setQ] = useState("");
  const [onlyBz, setOnlyBz] = useState(false);
  const [open, setOpen] = useState<string | null>(null);

  const rows = useMemo(() => {
    if (!data) return [];
    const val = (e: SovrennEntry): string | number => {
      if (sortKey === "ticker") return sym(e);
      if (sortKey === "buyZone") return e.buyZone === "Y" ? 2 : e.buyZone === "N" ? 1 : 0;
      const v = (e as unknown as Record<string, unknown>)[sortKey];
      return typeof v === "number" || typeof v === "string" ? v : -Infinity;
    };
    return data
      .filter((e) => !onlyBz || e.buyZone === "Y")
      .filter((e) => !q || `${e.name} ${sym(e)} ${e.latestTag ?? ""}`.toLowerCase().includes(q.toLowerCase()))
      .slice()
      .sort((a, b) => {
        const x = val(a), y = val(b);
        const c = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
        return asc ? c : -c;
      });
  }, [data, sortKey, asc, q, onlyBz]);

  if (loadError) return <div className="empty">Could not load Sovrenn list: {loadError}</div>;
  if (!data) return <div className="loading">Loading…</div>;

  const bz = data.filter((e) => e.buyZone === "Y").length;
  const latest = data.reduce((m, e) => (e.latestDate > m ? e.latestDate : m), "");
  const fresh = data.filter((e) => e.latestDate === latest).length;
  const perf = data.filter((e) => e.pctSinceHighlight != null).map((e) => e.pctSinceHighlight as number);
  const avgPerf = perf.length ? perf.reduce((a, b) => a + b, 0) / perf.length : null;
  const winners = perf.filter((x) => x > 0).length;

  const sortBy = (k: Key) => {
    if (sortKey === k) setAsc(!asc);
    else {
      setSortKey(k);
      setAsc(false);
    }
  };
  const bzChip = (e: SovrennEntry) => (
    <span className={`zone ${e.buyZone === "Y" ? "zone-buy" : e.buyZone === "N" ? "zone-wait" : "zone-na"}`} title={e.buyZoneNote}>
      <span className="zone-dot" aria-hidden />
      {e.buyZone === "Y" ? "Buy zone" : e.buyZone === "N" ? "Not yet" : "n/a"}
    </span>
  );
  const mentionsBlock = (e: SovrennEntry) => (
    <div className="sv-detail">
      {e.mentions
        .slice()
        .reverse()
        .map((m) => (
          <div key={m.date} className="sv-mention">
            <div className="sv-mention-head">
              <span className="date-chip">{m.date}</span>
              {m.tag && <span className="tag-chip">{m.tag}</span>}
              <span className="muted small">MCap {m.sovrennMcap ?? "n/a"} · PE {m.sovrennPe ?? "n/a"}</span>
            </div>
            <p>{m.filing}</p>
            {m.outlook && (
              <p className="muted">
                <strong>Outlook:</strong> {m.outlook}
              </p>
            )}
          </div>
        ))}
      <div className="sv-check">
        Buy-zone check: {e.buyZoneNote ?? "n/a"} · 20/50/200 DMA {e.dma20 ?? "n/a"} / {e.dma50 ?? "n/a"} / {e.dma200 ?? "n/a"} · Yahoo{" "}
        {e.ticker ?? "unresolved"} · price as of {e.priceDate ?? "n/a"}
      </div>
    </div>
  );

  return (
    <section className="stack">
      <div className="kpis">
        <div className="kpi static">
          <span className="kpi-label">Highlighted</span>
          <span className="kpi-value">{data.length}</span>
          <span className="kpi-hint">companies · separate from watchlist</span>
        </div>
        <button type="button" className={`kpi kpi-buy ${onlyBz ? "active" : ""}`} onClick={() => setOnlyBz(!onlyBz)}>
          <span className="kpi-label"><span className="zone-dot dot-buy" aria-hidden />Buy zone now</span>
          <span className="kpi-value">{bz}</span>
          <span className="kpi-hint">{onlyBz ? "filter on · tap to clear" : "tap to filter"}</span>
        </button>
        <div className="kpi static">
          <span className="kpi-label">Latest edition</span>
          <span className="kpi-value kpi-date">{latest || "—"}</span>
          <span className="kpi-hint">{fresh} name{fresh === 1 ? "" : "s"} featured</span>
        </div>
        <div className="kpi static">
          <span className="kpi-label">Avg since highlight</span>
          <span className={`kpi-value ${toneOf(avgPerf)}`}>{formatSignedPct(avgPerf)}</span>
          <span className="kpi-hint">{winners} of {perf.length} up</span>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <div>
            <h2 className="panel-title">Sovrenn Times picks</h2>
            <p className="panel-sub">
              Showing {rows.length} of {data.length} · tap a row for Sovrenn's text · sort by any column
            </p>
          </div>
          <div className="panel-tools">
            <label className="search-box">
              <Search size={15} aria-hidden />
              <input placeholder="Search name, symbol, tag" value={q} onChange={(e) => setQ(e.target.value)} />
            </label>
            <button type="button" className={`pill ${onlyBz ? "active" : ""}`} onClick={() => setOnlyBz(!onlyBz)}>
              Buy zone only
            </button>
          </div>
        </div>
        <details className="method">
          <summary>How the columns are calculated</summary>
          <p>
            Price @ highlight = close on the edition date. Buy zone (daily): above 200 DMA, within 0 to +4% of 20/50 DMA, RSI 40
            to 60, not more than 8% above 20 DMA. n/a = not enough Yahoo history.
          </p>
        </details>

        <div className="sv-sortbar">
          <ArrowUpDown size={14} />
          <select value={sortKey} onChange={(e) => { setSortKey(e.target.value as Key); setAsc(false); }} aria-label="Sort by">
            {COLS.map((c) => (
              <option key={c.key} value={c.key}>{c.label}</option>
            ))}
          </select>
          <button type="button" className="btn-ghost" onClick={() => setAsc(!asc)}>{asc ? "▲ asc" : "▼ desc"}</button>
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
                <th>Latest reason</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((e) => (
                <Fragment key={e.key}>
                  <tr className={`clickable ${open === e.key ? "open" : ""}`} onClick={() => setOpen(open === e.key ? null : e.key)}>
                    <td className="sticky-col">
                      <span className="tkr-sym">{sym(e)}</span>
                      {e.sme && <span className="tag-chip sme">SME</span>}
                    </td>
                    <td className="name-cell">{e.name}</td>
                    <td>{bzChip(e)}</td>
                    <td className="num strong">{e.price != null ? formatInr(e.price) : "n/a"}</td>
                    <td className={`num ${toneOf(e.pctSinceHighlight)}`}>
                      {e.pctSinceHighlight != null ? formatPct(e.pctSinceHighlight) : "n/a"}
                    </td>
                    <td className="num muted">{e.priceAtHighlight != null ? formatInr(e.priceAtHighlight) : "n/a"}</td>
                    <td className="mono muted">{e.latestDate}</td>
                    <td className="mono muted">{e.firstHighlighted}</td>
                    <td className="num">{e.timesMentioned}</td>
                    <td className="num" title={e.sovrennMcap ? `Sovrenn: ${e.sovrennMcap}` : ""}>
                      {e.mcapCr != null ? e.mcapCr.toLocaleString("en-IN") : "n/a"}
                    </td>
                    <td className="num">{e.rsi14 ?? "n/a"}</td>
                    <td className="reason-cell" title={e.latestReason ?? ""}>
                      <div className="clamp-2">{e.latestReason ?? "n/a"}</div>
                    </td>
                  </tr>
                  {open === e.key && (
                    <tr className="detail-row">
                      <td colSpan={COLS.length + 1}>{mentionsBlock(e)}</td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>

        <div className="sv-cards">
          {rows.map((e) => (
            <article key={e.key} className={`wcard ${open === e.key ? "open" : ""}`}>
              <button type="button" className="wcard-main" onClick={() => setOpen(open === e.key ? null : e.key)}>
                <div className="wcard-top">
                  <div className="wcard-id">
                    <div className="tkr">
                      <span className="tkr-sym">{sym(e)}</span>
                      {e.sme && <span className="tag-chip sme">SME</span>}
                    </div>
                    <div className="tkr-name">{e.name}</div>
                  </div>
                  <div className="wcard-px">
                    <div className="px">{e.price != null ? formatInr(e.price) : "n/a"}</div>
                    <div className={`px-chg ${toneOf(e.pctSinceHighlight)}`}>
                      {e.pctSinceHighlight != null ? `${formatPct(e.pctSinceHighlight)} since` : "n/a"}
                    </div>
                  </div>
                </div>
                <div className="wcard-mid">
                  {bzChip(e)}
                  {e.latestTag && <span className="tag-chip">{e.latestTag}</span>}
                </div>
                <div className="wcard-grid">
                  <div><span className="k">Latest</span><span className="v">{e.latestDate.slice(5)}</span></div>
                  <div><span className="k">Mentions</span><span className="v">{e.timesMentioned}</span></div>
                  <div><span className="k">MCap ₹Cr</span><span className="v">{e.mcapCr != null ? e.mcapCr.toLocaleString("en-IN") : "n/a"}</span></div>
                  <div><span className="k">RSI</span><span className="v">{e.rsi14 ?? "n/a"}</span></div>
                </div>
                <div className="wcard-trigger clamp-3">{e.latestReason ?? "n/a"}</div>
              </button>
              {open === e.key && mentionsBlock(e)}
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
