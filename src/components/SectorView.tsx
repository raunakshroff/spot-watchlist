import { useMemo, useState } from "react";
import type { WatchlistStock } from "../types";
import { SECTOR_ORDER } from "../types";
import { Search } from "lucide-react";
import { WatchTable } from "./WatchTable";
import { formatSignedPct, shortTicker, toneOf } from "../utils/format";
import { computeZone } from "../utils/zone";

interface Props {
  stocks: WatchlistStock[];
}

function sectorSortKey(sector: string): number {
  const idx = (SECTOR_ORDER as readonly string[]).indexOf(sector);
  return idx === -1 ? 999 : idx;
}

export function SectorView({ stocks }: Props) {
  const [sectorFilter, setSectorFilter] = useState("All");
  const [search, setSearch] = useState("");

  const sectors = useMemo(() => {
    const set = new Set(stocks.map((s) => s.sector || "Other"));
    return Array.from(set).sort((a, b) => sectorSortKey(a) - sectorSortKey(b) || a.localeCompare(b));
  }, [stocks]);

  const q = search.trim().toLowerCase();

  const filtered = useMemo(() => {
    return stocks.filter((s) => {
      const matchSector = sectorFilter === "All" || s.sector === sectorFilter;
      const matchQ =
        !q ||
        s.ticker.toLowerCase().includes(q) ||
        s.name.toLowerCase().includes(q) ||
        shortTicker(s.ticker).toLowerCase().includes(q) ||
        (s.sector ?? "").toLowerCase().includes(q);
      return matchSector && matchQ;
    });
  }, [stocks, sectorFilter, q]);

  const groups = useMemo(() => {
    const map = new Map<string, WatchlistStock[]>();
    for (const s of filtered) {
      const key = s.sector || "Other";
      const list = map.get(key) ?? [];
      list.push(s);
      map.set(key, list);
    }
    return Array.from(map.entries()).sort(
      ([a], [b]) => sectorSortKey(a) - sectorSortKey(b) || a.localeCompare(b),
    );
  }, [filtered]);

  const zoneCounts = useMemo(() => {
    const c = { buy: 0, near: 0, below: 0, wait: 0 };
    for (const s of filtered) c[computeZone(s).kind]++;
    return c;
  }, [filtered]);
  const holdingsCount = filtered.filter((s) => s.status === "Holding" || (s.sharesHeld ?? 0) > 0).length;

  return (
    <section className="stack">
      <div className="kpis">
        <div className="kpi static">
          <span className="kpi-label">Sectors</span>
          <span className="kpi-value">{sectors.length}</span>
          <span className="kpi-hint">on active watchlist</span>
        </div>
        <div className="kpi static">
          <span className="kpi-label">Names shown</span>
          <span className="kpi-value">{filtered.length}</span>
          <span className="kpi-hint">{sectorFilter === "All" ? "all sectors" : sectorFilter}</span>
        </div>
        <div className="kpi static kpi-buy">
          <span className="kpi-label"><span className="zone-dot dot-buy" aria-hidden />Buy zone</span>
          <span className="kpi-value">{zoneCounts.buy}</span>
          <span className="kpi-hint">in current filter</span>
        </div>
        <div className="kpi static kpi-near">
          <span className="kpi-label"><span className="zone-dot dot-near" aria-hidden />Near / below stop</span>
          <span className="kpi-value">{zoneCounts.near + zoneCounts.below}</span>
          <span className="kpi-hint">{zoneCounts.near} near · {zoneCounts.below} below</span>
        </div>
        <div className="kpi static">
          <span className="kpi-label">Holdings</span>
          <span className="kpi-value">{holdingsCount}</span>
          <span className="kpi-hint">in current filter</span>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <div>
            <h2 className="panel-title">By sector</h2>
            <p className="panel-sub">Watchlist grouped by sector · tap a row for thesis &amp; levels</p>
          </div>
          <label className="search-box">
            <Search size={15} aria-hidden />
            <input placeholder="Search ticker, name, or sector" value={search} onChange={(e) => setSearch(e.target.value)} />
          </label>
        </div>
        <div className="pill-row scroll-x">
          <button type="button" className={`pill ${sectorFilter === "All" ? "active" : ""}`} onClick={() => setSectorFilter("All")}>
            All <span className="pill-n">{stocks.length}</span>
          </button>
          {sectors.map((sec) => {
            const count = stocks.filter((s) => s.sector === sec).length;
            return (
              <button key={sec} type="button" className={`pill ${sectorFilter === sec ? "active" : ""}`} onClick={() => setSectorFilter(sec)}>
                {sec} <span className="pill-n">{count}</span>
              </button>
            );
          })}
        </div>
      </div>

      {groups.length === 0 ? (
        <div className="empty">No names match this sector filter.</div>
      ) : (
        <div className="sector-sections">
          {groups.map(([sector, list]) => {
            const bz = list.filter((s) => computeZone(s).kind === "buy").length;
            const withPct = list.filter((s) => s.dailyPct != null);
            const avg = withPct.length ? withPct.reduce((a, s) => a + (s.dailyPct ?? 0), 0) / withPct.length : null;
            return (
              <div key={sector} className="panel sector-section">
                <div className="sector-header">
                  <div className="sector-title">
                    <h3>{sector}</h3>
                    <span className="sector-count">
                      {list.length} name{list.length === 1 ? "" : "s"}
                      {bz > 0 ? ` · ${bz} in buy zone` : ""}
                    </span>
                  </div>
                  <div className={`sector-avg ${toneOf(avg)}`} title="Equal-weight average day change of these names">
                    avg {formatSignedPct(avg)} today
                  </div>
                </div>
                <WatchTable stocks={list} />
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
