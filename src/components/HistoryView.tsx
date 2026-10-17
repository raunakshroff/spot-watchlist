import { useMemo, useState } from "react";
import type { HistoryEntry } from "../types";
import { StatusBadge } from "./StatusBadge";
import { formatPct, formatPrice, formatRsi, shortTicker } from "../utils/format";

export function HistoryView({ history }: { history: HistoryEntry[] }) {
  const dates = useMemo(() => {
    const set = new Set(history.map((h) => h.date));
    return Array.from(set).sort((a, b) => b.localeCompare(a));
  }, [history]);

  const [selected, setSelected] = useState(dates[0] ?? "");

  const rows = history
    .filter((h) => h.date === selected)
    .sort((a, b) => a.ticker.localeCompare(b.ticker));

  const droppedCount = rows.filter((r) => r.droppedThatDay || r.status === "Dropped").length;

  return (
    <section className="stack">
      <div className="panel">
      <div className="panel-head">
        <div>
          <h2 className="panel-title">Daily history</h2>
          <p className="panel-sub">Snapshot of every tracked name per market day ({dates.length} days logged)</p>
        </div>
        <label className="select-box">
          <span>Market day</span>
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
          >
            {dates.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
      </div>

      {dates.map((d) => {
        if (d !== selected) return null;
        return (
          <div key={d} className="history-date">
            <h3>
              <span className="date-chip">{d}</span>
              <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>
                {rows.length} names
                {droppedCount > 0 ? ` · ${droppedCount} dropped` : ""}
              </span>
            </h3>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Ticker</th>
                    <th>Name</th>
                    <th>Status</th>
                    <th className="num">Close</th>
                    <th className="num">Day %</th>
                    <th className="num">RSI</th>
                    <th>Support</th>
                    <th>Resistance</th>
                    <th>Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr
                      key={`${r.date}-${r.ticker}`}
                      className={r.droppedThatDay || r.status === "Dropped" ? "dropped-row" : ""}
                    >
                      <td>
                        <strong style={{ fontFamily: "var(--mono)" }}>
                          {shortTicker(r.ticker)}
                        </strong>
                      </td>
                      <td>{r.name}</td>
                      <td>
                        <StatusBadge status={r.status} />
                      </td>
                      <td className="num strong">₹{formatPrice(r.price)}</td>
                      <td
                        className={
                          r.dailyPct == null ? "" : r.dailyPct >= 0 ? "up" : "down"
                        }
                        style={{ fontFamily: "var(--mono)", textAlign: "right" }}
                      >
                        {formatPct(r.dailyPct)}
                      </td>
                      <td className="num">{formatRsi(r.rsi14)}</td>
                      <td>{r.support ?? "—"}</td>
                      <td>{r.resistance ?? "—"}</td>
                      <td
                        style={{
                          whiteSpace: "normal",
                          maxWidth: 320,
                          color: "var(--text-muted)",
                        }}
                      >
                        {r.notes ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}

      {dates.length === 0 && <div className="empty">No history yet.</div>}
      </div>
    </section>
  );
}
