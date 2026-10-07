import type { DroppedStock } from "../types";
import { formatPrice, shortTicker } from "../utils/format";

export function DroppedView({ dropped }: { dropped: DroppedStock[] }) {
  if (!dropped.length) {
    return <div className="empty">No dropped names yet.</div>;
  }

  return (
    <section>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Name</th>
              <th>Sector</th>
              <th>Dropped</th>
              <th>Last price</th>
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
                  <td style={{ fontFamily: "var(--mono)" }}>{formatPrice(d.lastPrice)}</td>
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
    </section>
  );
}
