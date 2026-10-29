import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import type { IndicesData, WatchlistStock } from "../types";
import { SummaryCard } from "./SummaryCard";
import { WatchTable } from "./WatchTable";
import { alertCounts } from "../utils/alerts";
import { BellRing } from "lucide-react";
import { shortTicker } from "../utils/format";
import { computeZone, ZONE_LABEL, ZONE_NEAR_STOP_PCT, type ZoneKind } from "../utils/zone";

const STATUSES = ["All", "Active", "Dip-buy", "Breakout-watch", "Holding", "Watch-only", "Wait-RBI"] as const;

interface Props {
  stocks: WatchlistStock[];
  search: string;
  setSearch: (v: string) => void;
  statusFilter: string;
  setStatusFilter: (v: string) => void;
  indices?: IndicesData | null;
  onOpenIndex?: () => void;
}

const ZONE_HINT: Record<ZoneKind, string> = {
  buy: "inside entry range",
  near: `within ${ZONE_NEAR_STOP_PCT}% of stop`,
  below: "closed under stop",
  wait: "trigger not hit yet",
};

export function Overview({ stocks, search, setSearch, statusFilter, setStatusFilter, indices, onOpenIndex }: Props) {
  const [zoneFilter, setZoneFilter] = useState<ZoneKind | "all">("all");
  const [alertsOnly, setAlertsOnly] = useState(false);
  const alertTotals = stocks.reduce(
    (t, s) => {
      const c = alertCounts(s);
      return { armed: t.armed + c.armed, hit: t.hit + c.hit, names: t.names + (c.armed + c.hit ? 1 : 0) };
    },
    { armed: 0, hit: 0, names: 0 },
  );
  const zones = useMemo(() => new Map(stocks.map((s) => [s.ticker, computeZone(s).kind])), [stocks]);
  const count = (k: ZoneKind) => stocks.filter((s) => zones.get(s.ticker) === k).length;
  const holdings = stocks.filter((s) => s.status === "Holding" || (s.sharesHeld ?? 0) > 0);

  const q = search.trim().toLowerCase();
  const filtered = stocks.filter((s) => {
    const matchStatus = statusFilter === "All" || s.status === statusFilter;
    const matchZone = zoneFilter === "all" || zones.get(s.ticker) === zoneFilter;
    const matchQ =
      !q ||
      s.ticker.toLowerCase().includes(q) ||
      s.name.toLowerCase().includes(q) ||
      shortTicker(s.ticker).toLowerCase().includes(q);
    const matchAlert = !alertsOnly || (s.alerts?.length ?? 0) > 0;
    return matchStatus && matchQ && matchZone && matchAlert;
  });

  const statusCounts = (st: string) => (st === "All" ? stocks.length : stocks.filter((s) => s.status === st).length);

  return (
    <section className="stack">
      {indices?.indices?.length ? (
        <SummaryCard data={indices} watchlist={stocks} period="daily" compact onOpen={onOpenIndex} />
      ) : null}

      <div className="kpis" role="group" aria-label="Filter by zone">
        <button type="button" className={`kpi ${zoneFilter === "all" ? "active" : ""}`} onClick={() => setZoneFilter("all")}>
          <span className="kpi-label">Tracked</span>
          <span className="kpi-value">{stocks.length}</span>
          <span className="kpi-hint">
            {holdings.length} holding{holdings.length === 1 ? "" : "s"}
            {holdings.length ? ` · ${holdings.map((h) => shortTicker(h.ticker)).join(", ")}` : ""}
          </span>
        </button>
        {(["buy", "near", "below", "wait"] as ZoneKind[]).map((k) => (
          <button
            key={k}
            type="button"
            className={`kpi kpi-${k} ${zoneFilter === k ? "active" : ""}`}
            onClick={() => setZoneFilter(zoneFilter === k ? "all" : k)}
          >
            <span className="kpi-label">
              <span className={`zone-dot dot-${k}`} aria-hidden />
              {ZONE_LABEL[k]}
            </span>
            <span className="kpi-value">{count(k)}</span>
            <span className="kpi-hint">{ZONE_HINT[k]}</span>
          </button>
        ))}
      </div>

      <div className="panel">
        <div className="panel-head">
          <div>
            <h2 className="panel-title">Active watchlist</h2>
            <p className="panel-sub">
              Showing {filtered.length} of {stocks.length} · sorted by urgency · tap a row for thesis &amp; levels
            </p>
          </div>
          <label className="search-box">
            <Search size={15} aria-hidden />
            <input placeholder="Search ticker or name" value={search} onChange={(e) => setSearch(e.target.value)} />
          </label>
        </div>
        <div className="pill-row scroll-x" role="group" aria-label="Filter by status">
          {STATUSES.map((s) => {
            const n = statusCounts(s);
            if (s !== "All" && n === 0) return null;
            return (
              <button key={s} type="button" className={`pill ${statusFilter === s ? "active" : ""}`} onClick={() => setStatusFilter(s)}>
                {s} <span className="pill-n">{n}</span>
              </button>
            );
          })}
          {alertTotals.names > 0 && (
            <button
              type="button"
              className={`pill pill-alerts ${alertsOnly ? "active" : ""} ${alertTotals.hit ? "has-hit" : ""}`}
              onClick={() => setAlertsOnly(!alertsOnly)}
              title={`${alertTotals.armed} armed · ${alertTotals.hit} triggered`}
            >
              <BellRing size={12} aria-hidden /> Price alerts <span className="pill-n">{alertTotals.armed}</span>
              {alertTotals.hit ? <span className="pill-hit">{alertTotals.hit} hit</span> : null}
            </button>
          )}
          {zoneFilter !== "all" && (
            <button type="button" className="pill pill-clear" onClick={() => setZoneFilter("all")}>
              Zone: {ZONE_LABEL[zoneFilter]} ✕
            </button>
          )}
        </div>
        <WatchTable stocks={filtered} />
      </div>
    </section>
  );
}
