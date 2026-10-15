import { useMemo, useState } from "react";
import type {
  IndexHistoryData,
  IndexHorizon,
  IndicesData,
  IndexSectorRow,
  IndexUniverseRow,
  WatchlistStock,
} from "../types";
import { SummaryCard } from "./SummaryCard";
import { IndexOverlayChart } from "./IndexOverlayChart";
import { PERIOD_LABEL, pickHorizon } from "../utils/summary";
import { shortTicker } from "../utils/format";

interface Props {
  data: IndicesData | null;
  history?: IndexHistoryData | null;
  loadError?: string | null;
  watchlist?: WatchlistStock[];
}

type Period = IndexHorizon;
type Scope = "all" | "watchlist";
type Side = "all" | "above" | "below";
type Layout = "ranked" | "grouped";

const GROUP_ORDER = ["Broad Market", "Sectoral", "Thematic", "Strategy", "BSE"];
const PERIODS: Period[] = ["daily", "weekly", "m1", "m3", "m6", "y1", "y5"];
const LEADERBOARD_N = 10;

function byReturn(a: Ranked, b: Ranked): number {
  if (a.ret == null && b.ret == null) return a.row.name.localeCompare(b.row.name);
  if (a.ret == null) return 1;
  if (b.ret == null) return -1;
  if (b.ret !== a.ret) return b.ret - a.ret;
  return (b.row.isBenchmark ? 1 : 0) - (a.row.isBenchmark ? 1 : 0);
}

function fmtPct(n: number | null | undefined, digits = 2): string {
  if (n == null || Number.isNaN(n)) return "n/a";
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
  const src = period === "weekly" ? row.weeklySource : row.dailySource;
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
  // Sector cards only have daily/weekly from the feed
  const useWeekly = period === "weekly";
  const sectorPct = useWeekly ? row.weeklyPct : row.dailyPct;
  const vs = useWeekly ? row.vsNiftyWeekly : row.vsNiftyDaily;
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
        {period !== "daily" && period !== "weekly" && (
          <div className="index-row-note">Longer horizons use the All indices board (official index history).</div>
        )}
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
  selectedIds,
  onToggle,
}: {
  items: Ranked[];
  showGroup: boolean;
  maxAbs: number;
  startRank?: number;
  selectedIds: Set<string>;
  onToggle: (id: string) => void;
}) {
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
        const bench = !!r.isBenchmark;
        const width = x.vs == null ? 0 : Math.max(3, (Math.abs(x.vs) / maxAbs) * 100);
        const selected = selectedIds.has(r.id);
        return (
          <div key={r.id} className="ix-row-wrap">
            <button
              type="button"
              className={`ix-tr ix-selectable ${
                bench ? "bench" : x.vs == null ? "na" : x.vs > 0 ? "above" : x.vs < 0 ? "below" : "level"
              } ${selected ? "selected" : ""}`}
              role="row"
              onClick={() => !bench && onToggle(r.id)}
              title={bench ? "Nifty 50 benchmark" : selected ? "Remove from chart" : "Add to overlay chart"}
            >
              <span className="ix-rank">{x.ret == null ? "–" : startRank + i}</span>
              <span className="ix-name">
                <span className="ix-title">
                  {!bench && <span className={`ix-check ${selected ? "on" : ""}`}>{selected ? "✓" : "+"}</span>}
                  {r.name}
                </span>
                <span className="ix-meta">
                  {bench && <span className="ix-chip bench">Benchmark</span>}
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
                  {r.dataSource === "yahoo" && r.nseSymbol && !bench && (
                    <span className="ix-chip warn">Yahoo</span>
                  )}
                </span>
              </span>
              <span className="ix-num ix-last">{fmtLevel(r.last)}</span>
              <span className={`ix-num ${tone(x.ret)}`}>{fmtPct(x.ret)}</span>
              <span className={`ix-num ix-spread ${tone(x.vs)}`}>
                {bench ? "±0.00%" : fmtPct(x.vs)}
                <span className="ix-bar-wrap" aria-hidden>
                  <span
                    className={`ix-bar ${(x.vs ?? 0) >= 0 ? "up" : "down"}`}
                    style={{ width: `${width}%` }}
                  />
                </span>
              </span>
            </button>
          </div>
        );
      })}
    </div>
  );
}

function Leaderboard({
  leaders,
  laggards,
  period,
  onPick,
}: {
  leaders: Ranked[];
  laggards: Ranked[];
  period: Period;
  onPick: (id: string) => void;
}) {
  return (
    <div className="ix-leaderboard">
      <div className="ix-lb-col">
        <div className="ix-lb-head up">Top outperformers · {PERIOD_LABEL[period]}</div>
        {leaders.length === 0 ? (
          <div className="empty compact">No data for this horizon.</div>
        ) : (
          <ol className="ix-lb-list">
            {leaders.map((x, i) => (
              <li key={x.row.id}>
                <button type="button" className="ix-lb-row" onClick={() => onPick(x.row.id)}>
                  <span className="ix-lb-rank">{i + 1}</span>
                  <span className="ix-lb-name">{x.row.name}</span>
                  <span className={`ix-lb-vs up`}>{fmtPct(x.vs)}</span>
                </button>
              </li>
            ))}
          </ol>
        )}
      </div>
      <div className="ix-lb-col">
        <div className="ix-lb-head down">Bottom laggards · {PERIOD_LABEL[period]}</div>
        {laggards.length === 0 ? (
          <div className="empty compact">No data for this horizon.</div>
        ) : (
          <ol className="ix-lb-list">
            {laggards.map((x, i) => (
              <li key={x.row.id}>
                <button type="button" className="ix-lb-row" onClick={() => onPick(x.row.id)}>
                  <span className="ix-lb-rank">{i + 1}</span>
                  <span className="ix-lb-name">{x.row.name}</span>
                  <span className={`ix-lb-vs down`}>{fmtPct(x.vs)}</span>
                </button>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}

export function IndexView({ data, history = null, loadError, watchlist = [] }: Props) {
  const [period, setPeriod] = useState<Period>("daily");
  const [scope, setScope] = useState<Scope>("all");
  const [group, setGroup] = useState<string>("All");
  const [side, setSide] = useState<Side>("all");
  const [layout, setLayout] = useState<Layout>("ranked");
  const [search, setSearch] = useState("");
  const [watchlistOnly, setWatchlistOnly] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  const niftyPct = useMemo(() => {
    if (!data) return null;
    return pickHorizon(
      {
        ...data.benchmark,
        id: "NIFTY 50",
        name: "Nifty 50",
        nseSymbol: "NIFTY 50",
        yahooSymbol: "^NSEI",
        group: "Broad Market",
        dataSource: data.benchmark.dataSource ?? "nse",
        vsNiftyDaily: 0,
        vsNiftyWeekly: 0,
        watchlistSectors: [],
        watchlistTickers: [],
        isBenchmark: true,
      } as IndexUniverseRow,
      period,
    ).ret;
  }, [data, period]);

  const universe = useMemo(() => data?.indices ?? [], [data]);
  const hasUniverse = universe.length > 0;
  const effScope: Scope = hasUniverse ? scope : "watchlist";
  const namesById = useMemo(() => {
    const m: Record<string, string> = {};
    for (const r of universe) m[r.id] = r.name;
    return m;
  }, [universe]);

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

  const benchRow = useMemo<Ranked | null>(() => {
    const b = universe.find((r) => r.isBenchmark);
    if (!b) return null;
    return { row: b, ...pickHorizon(b, period) };
  }, [universe, period]);

  const ranked = useMemo<Ranked[]>(() => {
    const q = search.trim().toLowerCase();
    return universe
      .filter((r) => !r.isBenchmark)
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
      .map((r) => ({ row: r, ...pickHorizon(r, period) }))
      .sort(byReturn);
  }, [universe, group, watchlistOnly, search, period]);

  const scored = useMemo(() => ranked.filter((x) => x.vs != null), [ranked]);
  const leaders = useMemo(
    () => [...scored].sort((a, b) => (b.vs ?? 0) - (a.vs ?? 0)).slice(0, LEADERBOARD_N),
    [scored],
  );
  const laggards = useMemo(
    () => [...scored].sort((a, b) => (a.vs ?? 0) - (b.vs ?? 0)).slice(0, LEADERBOARD_N),
    [scored],
  );

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

  const withBench = (items: Ranked[]): Ranked[] =>
    benchRow ? [...items, benchRow].sort(byReturn) : items;

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);
  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= 6) return [...prev.slice(1), id];
      return [...prev, id];
    });
  };

  const { aboveSectors, belowSectors } = useMemo(() => {
    if (!data) return { aboveSectors: [] as IndexSectorRow[], belowSectors: [] as IndexSectorRow[] };
    const useWeekly = period === "weekly";
    const withVs = data.sectors.map((r) => ({
      row: r,
      vs: useWeekly ? r.vsNiftyWeekly : r.vsNiftyDaily,
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
  const summaryPeriod = period === "weekly" ? "weekly" : "daily";

  return (
    <section>
      {hasUniverse && <SummaryCard data={data} watchlist={watchlist} period={summaryPeriod} />}
      {!isAll && (
        <div className="stats">
          <div className="stat-card">
            <div className="label">Nifty 50</div>
            <div className={`value ${tone(niftyPct)}`}>{fmtPct(niftyPct)}</div>
            <div className="hint">
              {PERIOD_LABEL[period]} · {data.benchmark.last?.toLocaleString("en-IN")}
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
              {unit} lagging benchmark{isAll && naN > 0 ? ` · ${naN} n/a` : ""}
            </div>
          </div>
          <div className="stat-card">
            <div className="label">As of</div>
            <div className="value" style={{ fontSize: "1.25rem" }}>
              {data.asOf}
            </div>
            <div className="hint">
              {hasUniverse
                ? `${universe.length - (benchRow ? 1 : 0)} indices + Nifty 50`
                : `${data.sectors.length} sectors`}
              {sourceTxt ? ` · ${sourceTxt}` : ""}
            </div>
          </div>
        </div>
      )}

      <div className="toolbar index-toolbar">
        <div className="ix-controls">
          <div className="period-toggle" role="group" aria-label="Period">
            {PERIODS.map((p) => (
              <button
                key={p}
                type="button"
                className={`pill ${period === p ? "active" : ""}`}
                onClick={() => setPeriod(p)}
              >
                {PERIOD_LABEL[p]}
              </button>
            ))}
          </div>
          {hasUniverse && (
            <div className="period-toggle" role="group" aria-label="Scope">
              <button
                type="button"
                className={`pill ${effScope === "all" ? "active" : ""}`}
                onClick={() => setScope("all")}
              >
                All indices ({universe.length - (benchRow ? 1 : 0)})
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
            <Leaderboard
              leaders={leaders}
              laggards={laggards}
              period={period}
              onPick={toggleSelect}
            />
            <IndexOverlayChart
              history={history}
              period={period}
              selectedIds={selectedIds}
              namesById={namesById}
            />
            {selectedIds.length > 0 && (
              <div className="ix-selected-bar">
                <span>
                  Charting: {selectedIds.map((id) => namesById[id] ?? id).join(" · ")}
                </span>
                <button type="button" className="pill" onClick={() => setSelectedIds([])}>
                  Clear
                </button>
              </div>
            )}
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
          Relative spread = index return − Nifty 50 (percentage points) over {PERIOD_LABEL[period]}.{" "}
          {period === "weekly"
            ? data.weeklyBasis ?? "1W = close vs close one week earlier."
            : period === "daily"
              ? "1D = today's close vs previous close."
              : `Longer horizons use NSE archive closes (~${
                  { m1: "1 month", m3: "3 months", m6: "6 months", y1: "1 year", y5: "5 years" }[period]
                } lookback); n/a when history is missing.`}{" "}
          {isAll
            ? "Click a row (or a leaderboard name) to overlay it vs Nifty on the chart. Ranked by return — Nifty 50 splits outperformers from underperformers."
            : "Watchlist sectors use their official NSE index; otherwise equal-weight average of watchlist names."}
        </p>
      </div>

      {isAll ? (
        visible.length === 0 ? (
          <div className="empty compact">No indices match these filters.</div>
        ) : layout === "ranked" || group !== "All" ? (
          <UniverseTable
            items={withBench(visible)}
            showGroup={group === "All"}
            maxAbs={maxAbs}
            selectedIds={selectedSet}
            onToggle={toggleSelect}
          />
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
                    <UniverseTable
                      items={withBench(items)}
                      showGroup={false}
                      maxAbs={maxAbs}
                      selectedIds={selectedSet}
                      onToggle={toggleSelect}
                    />
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
              <div className="empty compact">No sectors above Nifty this period.</div>
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
              <div className="empty compact">No sectors below Nifty this period.</div>
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
