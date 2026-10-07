import { useMemo, useState } from "react";
import type { IndicesData, IndexSectorRow } from "../types";
import { shortTicker } from "../utils/format";

interface Props {
  data: IndicesData | null;
  loadError?: string | null;
}

type Period = "daily" | "weekly";

function fmtPct(n: number | null | undefined, digits = 2): string {
  if (n == null || Number.isNaN(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(digits)}%`;
}

function sourceLabel(row: IndexSectorRow, period: Period): string {
  const src = period === "daily" ? row.dailySource : row.weeklySource;
  if (src === "official" && row.indexName) return row.indexName;
  if (src === "official") return row.symbol ?? "Official index";
  return "Watchlist avg";
}

function RowCard({
  row,
  period,
  niftyPct,
}: {
  row: IndexSectorRow;
  period: Period;
  niftyPct: number | null;
}) {
  const sectorPct = period === "daily" ? row.dailyPct : row.weeklyPct;
  const vs = period === "daily" ? row.vsNiftyDaily : row.vsNiftyWeekly;
  const above = (vs ?? 0) >= 0;
  const tickers = (row.watchlistTickers ?? []).map(shortTicker).join(" · ");

  return (
    <article className={`index-row ${above ? "above" : "below"}`}>
      <div className="index-row-main">
        <div className="index-row-title">
          <span className="sector-badge">{row.sector}</span>
          <span className={`index-source-chip ${row.source}`}>
            {sourceLabel(row, period)}
          </span>
        </div>
        <div className="index-row-tickers">{tickers || "no watchlist names"}</div>
        {row.note && <div className="index-row-note">{row.note}</div>}
      </div>
      <div className="index-row-metrics">
        <div className="index-metric">
          <div className="label">Sector</div>
          <div className={`value ${(sectorPct ?? 0) >= 0 ? "up" : "down"}`}>
            {fmtPct(sectorPct)}
          </div>
        </div>
        <div className="index-metric">
          <div className="label">Nifty 50</div>
          <div className={`value ${(niftyPct ?? 0) >= 0 ? "up" : "down"}`}>
            {fmtPct(niftyPct)}
          </div>
        </div>
        <div className="index-metric spread">
          <div className="label">vs Nifty</div>
          <div className={`value ${(vs ?? 0) >= 0 ? "up" : "down"}`}>{fmtPct(vs)}</div>
        </div>
      </div>
      <div className="index-bar-wrap" aria-hidden>
        <div
          className={`index-bar ${above ? "up" : "down"}`}
          style={{
            width: `${Math.min(100, Math.abs(vs ?? 0) * 12)}%`,
          }}
        />
      </div>
    </article>
  );
}

export function IndexView({ data, loadError }: Props) {
  const [period, setPeriod] = useState<Period>("daily");

  const niftyPct = useMemo(() => {
    if (!data) return null;
    return period === "daily" ? data.benchmark.dailyPct : data.benchmark.weeklyPct;
  }, [data, period]);

  const { above, below } = useMemo(() => {
    if (!data) return { above: [] as IndexSectorRow[], below: [] as IndexSectorRow[] };
    const rows = [...data.sectors];
    const withVs = rows.map((r) => ({
      row: r,
      vs: period === "daily" ? r.vsNiftyDaily : r.vsNiftyWeekly,
    }));
    const ab = withVs
      .filter((x) => x.vs != null && x.vs >= 0)
      .sort((a, b) => (b.vs ?? 0) - (a.vs ?? 0))
      .map((x) => x.row);
    const bl = withVs
      .filter((x) => x.vs == null || x.vs < 0)
      .sort((a, b) => (a.vs ?? 0) - (b.vs ?? 0))
      .map((x) => x.row);
    return { above: ab, below: bl };
  }, [data, period]);

  if (loadError) {
    return (
      <section>
        <div className="empty">Failed to load index data: {loadError}</div>
      </section>
    );
  }

  if (!data) {
    return (
      <section>
        <div className="empty">Loading index data…</div>
      </section>
    );
  }

  const officialCount = data.sectors.filter((s) => s.dailySource === "official" || s.weeklySource === "official").length;

  return (
    <section>
      <div className="stats">
        <div className="stat-card">
          <div className="label">Nifty 50</div>
          <div className={`value ${(niftyPct ?? 0) >= 0 ? "up" : "down"}`}>{fmtPct(niftyPct)}</div>
          <div className="hint">
            {period === "daily" ? "daily" : "≈5 sessions"} · {data.benchmark.last?.toLocaleString("en-IN")}
          </div>
        </div>
        <div className="stat-card">
          <div className="label">Above Nifty</div>
          <div className="value up">{above.length}</div>
          <div className="hint">sectors beating benchmark</div>
        </div>
        <div className="stat-card">
          <div className="label">Below Nifty</div>
          <div className="value down">{below.length}</div>
          <div className="hint">sectors lagging benchmark</div>
        </div>
        <div className="stat-card">
          <div className="label">As of</div>
          <div className="value" style={{ fontSize: "1.25rem" }}>
            {data.asOf}
          </div>
          <div className="hint">
            {officialCount} with official index · {data.sectors.length} sectors
          </div>
        </div>
      </div>

      <div className="toolbar index-toolbar">
        <div className="period-toggle" role="group" aria-label="Period">
          <button
            type="button"
            className={`pill ${period === "daily" ? "active" : ""}`}
            onClick={() => setPeriod("daily")}
          >
            Daily
          </button>
          <button
            type="button"
            className={`pill ${period === "weekly" ? "active" : ""}`}
            onClick={() => setPeriod("weekly")}
          >
            Weekly
          </button>
        </div>
        <p className="index-help">
          Relative spread = sector return − Nifty 50. Official NSE sector indices via Yahoo when
          available; otherwise equal-weight average of watchlist names in that sector.
        </p>
      </div>

      <div className="index-columns">
        <div className="index-column">
          <div className="index-column-header above">
            <span>Above Nifty</span>
            <span className="sector-count">{above.length}</span>
          </div>
          {above.length === 0 ? (
            <div className="empty compact">No sectors above Nifty this {period}.</div>
          ) : (
            <div className="index-list">
              {above.map((row) => (
                <RowCard key={row.sector} row={row} period={period} niftyPct={niftyPct} />
              ))}
            </div>
          )}
        </div>
        <div className="index-column">
          <div className="index-column-header below">
            <span>Below Nifty</span>
            <span className="sector-count">{below.length}</span>
          </div>
          {below.length === 0 ? (
            <div className="empty compact">No sectors below Nifty this {period}.</div>
          ) : (
            <div className="index-list">
              {below.map((row) => (
                <RowCard key={row.sector} row={row} period={period} niftyPct={niftyPct} />
              ))}
            </div>
          )}
        </div>
      </div>

      <p className="index-disclaimer">{data.disclaimer}</p>
    </section>
  );
}
