import { useState } from "react";
import { ChevronDown } from "lucide-react";
import type { WatchlistStock } from "../types";
import { StatusBadge } from "./StatusBadge";
import { Sparkline } from "./Sparkline";
import { formatPct, formatPrice, formatRsi, shortTicker, rsiTone } from "../utils/format";

export function WatchlistCard({ stock }: { stock: WatchlistStock }) {
  const [open, setOpen] = useState(false);
  const pctUp = (stock.dailyPct ?? 0) >= 0;
  const tone = rsiTone(stock.rsi14);

  return (
    <article className="card">
      <button
        type="button"
        className="card-main"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <div className="ticker-cell">
          <div className="sym">{shortTicker(stock.ticker)}</div>
          <div className="name">
            {stock.name}
            {stock.sharesHeld ? ` · ${stock.sharesHeld} sh` : ""}
          </div>
        </div>

        <div className="metric">
          <span className="k">Status</span>
          <StatusBadge status={stock.status} />
        </div>

        <div className="metric">
          <span className="k">Price</span>
          <span className="v">{formatPrice(stock.price)}</span>
        </div>

        <div className="metric">
          <span className="k">Daily %</span>
          <span className={`v ${stock.dailyPct == null ? "" : pctUp ? "up" : "down"}`}>
            {formatPct(stock.dailyPct)}
          </span>
        </div>

        <div className="metric">
          <span className="k">RSI14</span>
          <span className={`v rsi-${tone}`}>{formatRsi(stock.rsi14)}</span>
        </div>

        <div className="metric">
          <span className="k">Buy zone</span>
          <span className={`chip ${stock.buyZone ? "chip-yes" : "chip-no"}`}>
            {stock.buyZone ? "YES" : "NO"}
          </span>
        </div>

        <div className="spark">
          <Sparkline data={stock.sparkline ?? []} up={pctUp} />
        </div>

        <ChevronDown size={18} className={`chev ${open ? "open" : ""}`} />
      </button>

      {open && (
        <div className="card-detail">
          <div className="detail-block">
            <h4>Thesis</h4>
            <p>{stock.thesis}</p>
            {stock.notes && (
              <>
                <h4 style={{ marginTop: 14 }}>Notes</h4>
                <p>{stock.notes}</p>
              </>
            )}
          </div>
          <div className="detail-block">
            <h4>Levels</h4>
            <div className="levels">
              <div className="level-row">
                <span className="lk">Buy / triggers</span>
                <span className="lv">{stock.buyZoneLevels ?? "—"}</span>
              </div>
              <div className="level-row">
                <span className="lk">Stop</span>
                <span className="lv">{stock.stop ?? "—"}</span>
              </div>
              <div className="level-row">
                <span className="lk">Target 1</span>
                <span className="lv">{stock.target1 ?? "—"}</span>
              </div>
              <div className="level-row">
                <span className="lk">Target 2</span>
                <span className="lv">{stock.target2 ?? "—"}</span>
              </div>
              <div className="level-row">
                <span className="lk">Support</span>
                <span className="lv">{stock.support ?? "—"}</span>
              </div>
              <div className="level-row">
                <span className="lk">Resistance</span>
                <span className="lv">{stock.resistance ?? "—"}</span>
              </div>
              <div className="level-row">
                <span className="lk">Vol vs 20d</span>
                <span className="lv">
                  {stock.volVs20d == null ? "—" : `${stock.volVs20d.toFixed(2)}x`}
                </span>
              </div>
              <div className="level-row">
                <span className="lk">Updated</span>
                <span className="lv">{stock.lastUpdated}</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </article>
  );
}
