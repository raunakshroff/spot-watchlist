import type { DroppedStock } from "../types";
import { formatPrice, shortTicker } from "../utils/format";

export function DroppedView({ dropped }: { dropped: DroppedStock[] }) {
  if (!dropped.length) {
    return <div className="empty">No dropped names yet.</div>;
  }

  return (
    <section className="stack">
      <div className="panel">
        <div className="panel-head">
          <div>
            <h2 className="panel-title">Dropped names</h2>
            <p className="panel-sub">{dropped.length} names removed from the active list · newest first</p>
          </div>
        </div>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Name</th>
              <th>Sector</th>
              <th>Dropped</th>
              <th className="num">Last price</th>
              <th>Prior status</th>
              <th>Reason</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>
            {dropped
              .slice()
              .sort((a, b) => b.droppedDate.localeCompare(a.droppedDate))
              .map((d) => (
                <tr key={`${d.ticker}-${d.droppedDate}`} className="dropped-row">
                  <td>
                    <strong style={{ fontFamily: "var(--mono)" }}>
                      {shortTicker(d.ticker)}
                    </strong>
                  </td>
                  <td>{d.name}</td>
                  <td>
                    <span className="sector-chip">{d.sector ?? "—"}</span>
                  </td>
                  <td style={{ fontFamily: "var(--mono)" }}>{d.droppedDate}</td>
                  <td className="num strong">₹{formatPrice(d.lastPrice)}</td>
                  <td>{d.priorStatus ?? "—"}</td>
                  <td style={{ whiteSpace: "normal", maxWidth: 360 }}>{d.reason}</td>
                  <td
                    style={{
                      whiteSpace: "normal",
                      maxWidth: 280,
                      color: "var(--text-muted)",
                    }}
                  >
                    {d.notes ?? "—"}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
      </div>
    </section>
  );
}
