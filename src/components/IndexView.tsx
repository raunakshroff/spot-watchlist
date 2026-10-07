import { useMemo, useState } from "react";
import type { IndicesData, IndexSectorRow, IndexUniverseRow } from "../types";
import { shortTicker } from "../utils/format";

interface Props {
  data: IndicesData | null;
  loadError?: string | null;
}

type Period = "daily" | "weekly";
type Scope = "all" | "watchlist";
type Side = "all" | "above" | "below";
type Layout = "ranked" | "grouped";

const GROUP_ORDER = ["Broad Market", "Sectoral", "Thematic", "Strategy", "BSE"];

function fmtPct(n: number | null | undefined, digits = 2): string {
  if (n == null || Number.isNaN(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(digits)}%`;
}

function fmtLevel(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function tone(n: number | null | undefined): string {
  if (n == null) return "";
  return n >= 0 ? "up" : "down";
}

function sourceLabel(row: IndexSectorRow, period: Period): string {
  const src = period === "daily" ? row.dailySource : row.weeklySource;
  if (src === "official" && row.indexName) return row.indexName;
  if (src === "official") return row.symbol ?? "Official index";
  return "Watchlist avg";
}

function SectorCard({
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
          <span className={`index-source-chip ${row.source}`}>{sourceLabel(row, period)}</span>
        </div>
        <div className="index-row-tickers">{tickers || "no watchlist names"}</div>
        {row.note && <div className="index-row-note">{row.note}</div>}
      </div>
      <div className="index-row-metrics">
        <div className="index-metric">
          <div className="label">Sector</div>
          <div className={`value ${tone(sectorPct)}`}>{fmtPct(sectorPct)}</div>
        </div>
        <div className="index-metric">
          <div className="label">Nifty 50</div>
          <div className={`value ${tone(niftyPct)}`}>{fmtPct(niftyPct)}</div>
        </div>
        <div className="index-metric spread">
          <div className="label">vs Nifty</div>
          <div className={`value ${tone(vs)}`}>{fmtPct(vs)}</div>
        </div>
      </div>
      <div className="index-bar-wrap" aria-hidden>
        <div
          className={`index-bar ${above ? "up" : "down"}`}
          style={{ width: `${Math.min(100, Math.abs(vs ?? 0) * 12)}%` }}
        />
      </div>
    </article>
  );
}

interface Ranked {
  row: IndexUniverseRow;
  ret: number | null;
  vs: number | null;
}

function UniverseTable({
  items,
  showGroup,
  maxAbs,
  startRank = 1,
}: {
  items: Ranked[];
  showGroup: boolean;
  maxAbs: number;
  startRank?: number;
}) {
  const firstBelow = items.findIndex((x) => x.vs == null || x.vs < 0);
  return (
    <div className="ix-table" role="table">
      <div className="ix-tr ix-head" role="row">
        <span className="ix-rank">#</span>
        <span>Index</span>
        <span className="ix-num ix-last">Last</span>
        <span className="ix-num">Return</span>
        <span className="ix-num">vs Nifty</span>
      </div>
      {items.map((x, i) => {
        const r = x.row;
        const showDivider = i === firstBelow && firstBelow > 0;
        const width = x.vs == null ? 0 : Math.max(3, (Math.abs(x.vs) / maxAbs) * 100);
        return (
          <div key={r.id} className="ix-row-wrap">
            {showDivider && (
              <div className="ix-divider">
                <span>Nifty 50 line</span>
              </div>
            )}
            <div
              className={`ix-tr ${x.vs == null ? "na" : x.vs >= 0 ? "above" : "below"}`}
              role="row"
            >
              <span className="ix-rank">{x.vs == null ? "–" : startRank + i}</span>
              <span className="ix-name">
                <span className="ix-title">{r.name}</span>
                <span className="ix-meta">
                  {showGroup && <span className="ix-chip">{r.group}</span>}
                  {r.watchlistSectors.length > 0 && (
                    <span
                      className="ix-chip wl"
                      title={r.watchlistTickers.map(shortTicker).join(", ")}
                    >
                      ★ {r.watchlistTickers.map(shortTicker).join(" · ")}
                    </span>
                  )}
                  <span className="ix-sym">{r.yahooSymbol ?? r.nseSymbol}</span>
                  {r.dataSource === "yahoo" && r.group !== "BSE" && (
                    <span className="ix-chip warn">Yahoo</span>
                  )}
                </span>
              </span>
              <span className="ix-num ix-last">{fmtLevel(r.last)}</span>
              <span className={`ix-num ${tone(x.ret)}`}>{fmtPct(x.ret)}</span>
              <span className={`ix-num ix-spread ${tone(x.vs)}`}>
                {fmtPct(x.vs)}
                <span className="ix-bar-wrap" aria-hidden>
                  <span
                    className={`ix-bar ${(x.vs ?? 0) >= 0 ? "up" : "down"}`}
                    style={{ width: `${width}%` }}
                  />
                </span>
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function IndexView({ data, loadError }: Props) {
  const [period, setPeriod] = useState<Period>("daily");
  const [scope, setScope] = useState<Scope>("all");
  const [group, setGroup] = useState<string>("All");
  const [side, setSide] = useState<Side>("all");
  const [layout, setLayout] = useState<Layout>("ranked");
  const [search, setSearch] = useState("");
  const [watchlistOnly, setWatchlistOnly] = useState(false);

  const niftyPct = useMemo(() => {
    if (!data) return null;
    return period === "daily" ? data.benchmark.dailyPct : data.benchmark.weeklyPct;
  }, [data, period]);

  const universe = useMemo(() => data?.indices ?? [], [data]);
  const hasUniverse = universe.length > 0;
  const effScope: Scope = hasUniverse ? scope : "watchlist";

  const groups = useMemo(() => {
    const counts = new Map<string, number>();
    for (const r of universe) counts.set(r.group, (counts.get(r.group) ?? 0) + 1);
    return [...counts.entries()]
      .sort((a, b) => {
        const ia = GROUP_ORDER.indexOf(a[0]);
        const ib = GROUP_ORDER.indexOf(b[0]);
        return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
      })
      .map(([g, n]) => ({ group: g, count: n }));
  }, [universe]);

  const ranked = useMemo<Ranked[]>(() => {
    const q = search.trim().toLowerCase();
    return universe
      .filter((r) => group === "All" || r.group === group)
      .filter((r) => !watchlistOnly || r.watchlistSectors.length > 0)
      .filter(
        (r) =>
          !q ||
          r.name.toLowerCase().includes(q) ||
          (r.nseSymbol ?? "").toLowerCase().includes(q) ||
          (r.yahooSymbol ?? "").toLowerCase().includes(q) ||
          r.group.toLowerCase().includes(q) ||
          r.watchlistSectors.some((s) => s.toLowerCase().includes(q)),
      )
      .map((r) => ({
        row: r,
        ret: period === "daily" ? r.dailyPct : r.weeklyPct,
        vs: period === "daily" ? r.vsNiftyDaily : r.vsNiftyWeekly,
      }))
      .sort((a, b) => {
        if (a.vs == null && b.vs == null) return a.row.name.localeCompare(b.row.name);
        if (a.vs == null) return 1;
        if (b.vs == null) return -1;
        return b.vs - a.vs;
      });
  }, [universe, group, watchlistOnly, search, period]);

  const aboveN = ranked.filter((x) => x.vs != null && x.vs >= 0).length;
  const belowN = ranked.filter((x) => x.vs != null && x.vs < 0).length;
  const naN = ranked.filter((x) => x.vs == null).length;

  const visible = useMemo(
    () =>
      ranked.filter((x) =>
        side === "all" ? true : side === "above" ? x.vs != null && x.vs >= 0 : x.vs != null && x.vs < 0,
      ),
    [ranked, side],
  );

  const maxAbs = useMemo(
    () => Math.max(0.5, ...visible.map((x) => Math.abs(x.vs ?? 0))),
    [visible],
  );

  const { aboveSectors, belowSectors } = useMemo(() => {
    if (!data) return { aboveSectors: [] as IndexSectorRow[], belowSectors: [] as IndexSectorRow[] };
    const withVs = data.sectors.map((r) => ({
      row: r,
      vs: period === "daily" ? r.vsNiftyDaily : r.vsNiftyWeekly,
    }));
    return {
      aboveSectors: withVs
        .filter((x) => x.vs != null && x.vs >= 0)
        .sort((a, b) => (b.vs ?? 0) - (a.vs ?? 0))
        .map((x) => x.row),
      belowSectors: withVs
        .filter((x) => x.vs == null || x.vs < 0)
        .sort((a, b) => (a.vs ?? 0) - (b.vs ?? 0))
        .map((x) => x.row),
    };
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

  const isAll = effScope === "all";
  const aboveCount = isAll ? aboveN : aboveSectors.length;
  const belowCount = isAll ? belowN : belowSectors.length;
  const unit = isAll ? "indices" : "sectors";
  const sourceTxt =
    data.primarySource === "nse" ? "NSE official" : data.primarySource === "yahoo" ? "Yahoo fallback" : "";

  return (
    <section>
      <div className="stats">
        <div className="stat-card">
          <div className="label">Nifty 50</div>
          <div className={`value ${tone(niftyPct)}`}>{fmtPct(niftyPct)}</div>
          <div className="hint">
            {period === "daily" ? "today" : `since ${data.weekRefDate ?? "1 wk ago"}`} ·{" "}
            {data.benchmark.last?.toLocaleString("en-IN")}
          </div>
        </div>
        <div className="stat-card">
          <div className="label">Above Nifty</div>
          <div className="value up">{aboveCount}</div>
          <div className="hint">{unit} beating benchmark</div>
        </div>
        <div className="stat-card">
          <div className="label">Below Nifty</div>
          <div className="value down">{belowCount}</div>
          <div className="hint">
            {unit} lagging benchmark{isAll && naN > 0 ? ` · ${naN} no data` : ""}
          </div>
        </div>
        <div className="stat-card">
          <div className="label">As of</div>
          <div className="value" style={{ fontSize: "1.25rem" }}>
            {data.asOf}
          </div>
          <div className="hint">
            {hasUniverse ? `${universe.length} indices` : `${data.sectors.length} sectors`}
            {sourceTxt ? ` · ${sourceTxt}` : ""}
          </div>
        </div>
      </div>

      <div className="toolbar index-toolbar">
        <div className="ix-controls">
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
          {hasUniverse && (
            <div className="period-toggle" role="group" aria-label="Scope">
              <button
                type="button"
                className={`pill ${effScope === "all" ? "active" : ""}`}
                onClick={() => setScope("all")}
              >
                All indices ({universe.length})
              </button>
              <button
                type="button"
                className={`pill ${effScope === "watchlist" ? "active" : ""}`}
                onClick={() => setScope("watchlist")}
              >
                My sectors ({data.sectors.length})
              </button>
            </div>
          )}
        </div>

        {isAll && (
          <>
            <div className="ix-controls">
              <input
                className="search ix-search"
                type="search"
                placeholder="Search index, symbol, theme… (e.g. bank, metal, smallcap)"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <div className="period-toggle" role="group" aria-label="Above or below">
                {(["all", "above", "below"] as Side[]).map((s) => (
                  <button
                    key={s}
                    type="button"
                    className={`pill ${side === s ? "active" : ""}`}
                    onClick={() => setSide(s)}
                  >
                    {s === "all" ? "Both" : s === "above" ? `Above (${aboveN})` : `Below (${belowN})`}
                  </button>
                ))}
              </div>
              <div className="period-toggle" role="group" aria-label="Layout">
                <button
                  type="button"
                  className={`pill ${layout === "ranked" ? "active" : ""}`}
                  onClick={() => setLayout("ranked")}
                >
                  Ranked
                </button>
                <button
                  type="button"
                  className={`pill ${layout === "grouped" ? "active" : ""}`}
                  onClick={() => setLayout("grouped")}
                >
                  By group
                </button>
              </div>
            </div>
            <div className="filter-pills">
              <button
                type="button"
                className={`pill ${group === "All" ? "active" : ""}`}
                onClick={() => setGroup("All")}
              >
                All groups
              </button>
              {groups.map((g) => (
                <button
                  key={g.group}
                  type="button"
                  className={`pill ${group === g.group ? "active" : ""}`}
                  onClick={() => setGroup(g.group)}
                >
                  {g.group} ({g.count})
                </button>
              ))}
              <button
                type="button"
                className={`pill ${watchlistOnly ? "active" : ""}`}
                onClick={() => setWatchlistOnly((v) => !v)}
                title="Only indices linked to your watchlist sectors"
              >
                ★ Watchlist-linked
              </button>
            </div>
          </>
        )}

        <p className="index-help">
          Relative spread = index return − Nifty 50 (percentage points).{" "}
          {period === "weekly"
            ? data.weeklyBasis ?? "Weekly = close vs close one week earlier."
            : "Daily = today's close vs previous close."}{" "}
          {isAll
            ? "Levels from NSE's official index feed; BSE rows via Yahoo Finance."
            : "Watchlist sectors use their official NSE index; otherwise equal-weight average of watchlist names."}
        </p>
      </div>

      {isAll ? (
        visible.length === 0 ? (
          <div className="empty compact">No indices match these filters.</div>
        ) : layout === "ranked" || group !== "All" ? (
          <UniverseTable items={visible} showGroup={group === "All"} maxAbs={maxAbs} />
        ) : (
          <div className="ix-groups">
            {GROUP_ORDER.concat(groups.map((g) => g.group).filter((g) => !GROUP_ORDER.includes(g)))
              .map((g) => ({ g, items: visible.filter((x) => x.row.group === g) }))
              .filter(({ items }) => items.length > 0)
              .map(({ g, items }) => {
                const up = items.filter((x) => x.vs != null && x.vs >= 0).length;
                const dn = items.filter((x) => x.vs != null && x.vs < 0).length;
                return (
                  <div key={g} className="ix-group">
                    <div className="ix-group-header">
                      <span>{g}</span>
                      <span className="ix-group-counts">
                        <span className="up">▲ {up}</span>
                        <span className="down">▼ {dn}</span>
                      </span>
                    </div>
                    <UniverseTable items={items} showGroup={false} maxAbs={maxAbs} />
                  </div>
                );
              })}
          </div>
        )
      ) : (
        <div className="index-columns">
          <div className="index-column">
            <div className="index-column-header above">
              <span>Above Nifty</span>
              <span className="sector-count">{aboveSectors.length}</span>
            </div>
            {aboveSectors.length === 0 ? (
              <div className="empty compact">No sectors above Nifty this {period}.</div>
            ) : (
              <div className="index-list">
                {aboveSectors.map((row) => (
                  <SectorCard key={row.sector} row={row} period={period} niftyPct={niftyPct} />
                ))}
              </div>
            )}
          </div>
          <div className="index-column">
            <div className="index-column-header below">
              <span>Below Nifty</span>
              <span className="sector-count">{belowSectors.length}</span>
            </div>
            {belowSectors.length === 0 ? (
              <div className="empty compact">No sectors below Nifty this {period}.</div>
            ) : (
              <div className="index-list">
                {belowSectors.map((row) => (
                  <SectorCard key={row.sector} row={row} period={period} niftyPct={niftyPct} />
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      <p className="index-disclaimer">{data.disclaimer}</p>
    </section>
  );
}
