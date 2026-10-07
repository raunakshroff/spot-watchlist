import { useMemo, useState } from "react";
import type { WatchlistStock } from "../types";
import { SECTOR_ORDER } from "../types";
import { WatchlistCard } from "./WatchlistCard";
import { shortTicker } from "../utils/format";

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

  const buyZoneCount = filtered.filter((s) => s.buyZone).length;
  const holdingsCount = filtered.filter(
    (s) => s.status === "Holding" || (s.sharesHeld ?? 0) > 0,
  ).length;

  return (
    <section>
      <div className="stats">
        <div className="stat-card">
          <div className="label">Sectors</div>
          <div className="value">{sectors.length}</div>
          <div className="hint">on active watchlist</div>
        </div>
        <div className="stat-card">
          <div className="label">Names shown</div>
          <div className="value">{filtered.length}</div>
          <div className="hint">
            {sectorFilter === "All" ? "all sectors" : sectorFilter}
          </div>
        </div>
        <div className="stat-card">
          <div className="label">Buy-zone</div>
          <div className="value">{buyZoneCount}</div>
          <div className="hint">in current filter</div>
        </div>
        <div className="stat-card">
          <div className="label">Holdings</div>
          <div className="value">{holdingsCount}</div>
          <div className="hint">in current filter</div>
        </div>
      </div>

      <div className="toolbar">
        <input
          className="search"
          placeholder="Search ticker, name, or sector…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="filter-pills">
          <button
            type="button"
            className={`pill ${sectorFilter === "All" ? "active" : ""}`}
            onClick={() => setSectorFilter("All")}
          >
            All ({stocks.length})
          </button>
          {sectors.map((sec) => {
            const count = stocks.filter((s) => s.sector === sec).length;
            return (
              <button
                key={sec}
                type="button"
                className={`pill ${sectorFilter === sec ? "active" : ""}`}
                onClick={() => setSectorFilter(sec)}
              >
                {sec} ({count})
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
            const bz = list.filter((s) => s.buyZone).length;
            return (
              <div key={sector} className="sector-section">
                <div className="sector-header">
                  <div className="sector-title">
                    <span className="sector-badge">{sector}</span>
                    <span className="sector-count">
                      {list.length} name{list.length === 1 ? "" : "s"}
                      {bz > 0 ? ` · ${bz} buy-zone` : ""}
                    </span>
                  </div>
                  <div className="sector-tickers">
                    {list.map((s) => shortTicker(s.ticker)).join(" · ")}
                  </div>
                </div>
                <div className="grid">
                  {list.map((s) => (
                    <WatchlistCard key={s.ticker} stock={s} />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
