import type { WatchlistStock } from "../types";
import { WatchlistCard } from "./WatchlistCard";
import { shortTicker } from "../utils/format";

const STATUSES = [
  "All",
  "Active",
  "Dip-buy",
  "Breakout-watch",
  "Holding",
  "Watch-only",
  "Wait-RBI",
] as const;

interface Props {
  stocks: WatchlistStock[];
  search: string;
  setSearch: (v: string) => void;
  statusFilter: string;
  setStatusFilter: (v: string) => void;
}

export function Overview({
  stocks,
  search,
  setSearch,
  statusFilter,
  setStatusFilter,
}: Props) {
  const active = stocks.filter((s) => s.status !== "Watch-only").length;
  const holdings = stocks.filter((s) => s.status === "Holding" || (s.sharesHeld ?? 0) > 0);
  const buyZone = stocks.filter((s) => s.buyZone);
  const alerts = stocks.filter((s) => s.buyZone || (s.rsi14 != null && (s.rsi14 >= 70 || s.rsi14 <= 35)));

  const q = search.trim().toLowerCase();
  const filtered = stocks.filter((s) => {
    const matchStatus = statusFilter === "All" || s.status === statusFilter;
    const matchQ =
      !q ||
      s.ticker.toLowerCase().includes(q) ||
      s.name.toLowerCase().includes(q) ||
      shortTicker(s.ticker).toLowerCase().includes(q);
    return matchStatus && matchQ;
  });

  return (
    <section>
      <div className="stats">
        <div className="stat-card">
          <div className="label">Tracked</div>
          <div className="value">{stocks.length}</div>
          <div className="hint">{active} non-watch-only</div>
        </div>
        <div className="stat-card">
          <div className="label">Holdings</div>
          <div className="value">{holdings.length}</div>
          <div className="hint">
            {holdings.map((h) => shortTicker(h.ticker)).join(", ") || "none"}
          </div>
        </div>
        <div className="stat-card">
          <div className="label">Buy-zone</div>
          <div className="value">{buyZone.length}</div>
          <div className="hint">names flagged YES</div>
        </div>
        <div className="stat-card">
          <div className="label">Alerts</div>
          <div className="value">{alerts.length}</div>
          <div className="hint">buy-zone or RSI extremes</div>
        </div>
      </div>

      {alerts.length > 0 && (
        <div className="alert-list">
          {alerts.slice(0, 6).map((s) => (
            <div key={s.ticker} className="alert-item">
              <strong>{shortTicker(s.ticker)}</strong>
              <span>
                {s.buyZone ? "In / near buy zone. " : ""}
                {s.rsi14 != null && s.rsi14 >= 70 ? `RSI elevated (${Math.round(s.rsi14)}). ` : ""}
                {s.rsi14 != null && s.rsi14 <= 35 ? `RSI washed-out (${Math.round(s.rsi14)}). ` : ""}
                {s.stop ? `Stop: ${s.stop}` : ""}
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="toolbar">
        <input
          className="search"
          placeholder="Search ticker or name…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="filter-pills">
          {STATUSES.map((s) => (
            <button
              key={s}
              type="button"
              className={`pill ${statusFilter === s ? "active" : ""}`}
              onClick={() => setStatusFilter(s)}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <div className="grid">
        {filtered.length === 0 ? (
          <div className="empty">No names match this filter.</div>
        ) : (
          filtered.map((s) => <WatchlistCard key={s.ticker} stock={s} />)
        )}
      </div>
    </section>
  );
}
