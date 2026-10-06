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
    <section>
      <div className="toolbar">
        <label style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
          Market day{" "}
          <select
            className="search"
            style={{ minWidth: 180, marginLeft: 8 }}
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
              <table>
                <thead>
                  <tr>
                    <th>Ticker</th>
                    <th>Name</th>
                    <th>Status</th>
                    <th>Close</th>
                    <th>Daily %</th>
                    <th>RSI14</th>
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
                      <td style={{ fontFamily: "var(--mono)" }}>{formatPrice(r.price)}</td>
                      <td
                        className={
                          r.dailyPct == null ? "" : r.dailyPct >= 0 ? "up" : "down"
                        }
                        style={{ fontFamily: "var(--mono)" }}
                      >
                        {formatPct(r.dailyPct)}
                      </td>
                      <td style={{ fontFamily: "var(--mono)" }}>{formatRsi(r.rsi14)}</td>
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
    </section>
  );
}
