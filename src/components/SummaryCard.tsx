import { useMemo } from "react";
import type { IndicesData, WatchlistStock } from "../types";
import { buildSummary, NEAR_STOP_PCT, type Period, type StopWatch } from "../utils/summary";

interface Props {
  data: IndicesData;
  watchlist: WatchlistStock[];
  period: Period;
  compact?: boolean;
  onOpen?: () => void;
}

function pct(n: number | null | undefined, digits = 2): string {
  if (n == null || Number.isNaN(n)) return "—";
  return `${n > 0 ? "+" : ""}${n.toFixed(digits)}%`;
}

function pp(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return `${n > 0 ? "+" : ""}${n.toFixed(2)}pp`;
}

function tone(n: number | null | undefined): string {
  if (n == null) return "";
  return n > 0 ? "up" : n < 0 ? "down" : "";
}

function lvl(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function stopTxt(s: StopWatch): string {
  return s.distPct < 0
    ? `${s.ticker} ${Math.abs(s.distPct).toFixed(1)}% below ₹${lvl(s.stop)}`
    : `${s.ticker} ${s.distPct.toFixed(1)}% above ₹${lvl(s.stop)}`;
}

function pastTxt(s: StopWatch): string {
  return `${s.ticker} ${Math.abs(s.distPct).toFixed(1)}% below ₹${lvl(s.stop)}`;
}

export function SummaryCard({ data, watchlist, period, compact, onOpen }: Props) {
  const s = useMemo(() => buildSummary(data, watchlist, period), [data, watchlist, period]);
  const w = s.watch;
  const stopLine =
    w.pastStop.length > 0
      ? `Past stop: ${w.pastStop.map(pastTxt).join(", ")}`
      : w.nearStop.length > 0
        ? `Near stop (≤${NEAR_STOP_PCT}%): ${w.nearStop.map(stopTxt).join(", ")}`
        : w.closest
          ? `No stop within ${NEAR_STOP_PCT}% · closest ${stopTxt(w.closest)}`
          : "No parseable stops";

  return (
    <section className={`summary-card ${compact ? "compact" : ""}`} aria-label="Today's summary">
      <div className="summary-head">
        <div className="summary-title">
          <span className="summary-kicker">{period === "daily" ? "Today's summary" : "This week's summary"}</span>
          <span className="summary-date">as of {s.asOf}</span>
        </div>
        {onOpen && (
          <button type="button" className="pill" onClick={onOpen}>
            Open vs Nifty →
          </button>
        )}
      </div>

      <p className="summary-takeaway">{s.takeaway}</p>

      <div className="summary-grid">
        <div className="summary-block">
          <div className="summary-label">Nifty 50</div>
          <div className="summary-big">{lvl(s.nifty.last)}</div>
          <div className="summary-sub">
            <span className={tone(s.nifty.dailyPct)}>{pct(s.nifty.dailyPct)} day</span>
            <span className="dot">·</span>
            <span className={tone(s.nifty.weeklyPct)}>{pct(s.nifty.weeklyPct)} week</span>
          </div>
          {s.sensex && (
            <div className="summary-sub muted">
              Sensex {lvl(s.sensex.last)} ·{" "}
              <span className={tone(s.sensex.dailyPct)}>{pct(s.sensex.dailyPct)}</span> /{" "}
              <span className={tone(s.sensex.weeklyPct)}>{pct(s.sensex.weeklyPct)}</span>
            </div>
          )}
        </div>

        <div className="summary-block">
          <div className="summary-label">Breadth vs Nifty · {s.periodLabel}</div>
          <div className="summary-big">
            <span className="up">{s.beat}</span>
            <span className="muted"> / </span>
            <span className="down">{s.lagged}</span>
          </div>
          <div className="summary-sub muted">
            beat / lagged of {s.total}
            {s.inLine ? ` · ${s.inLine} in line` : ""}
          </div>
          <div className="summary-breadth" aria-hidden>
            <span className="up" style={{ flex: s.beat || 0.0001 }} />
            <span className="flat" style={{ flex: s.inLine || 0.0001 }} />
            <span className="down" style={{ flex: s.lagged || 0.0001 }} />
          </div>
        </div>

        {!compact && (
          <div className="summary-block">
            <div className="summary-label">Leaders</div>
            <ol className="summary-list">
              {s.leaders.map((x) => (
                <li key={x.name}>
                  <span className="nm">{x.name}</span>
                  <span className={`v ${tone(x.vs)}`}>{pp(x.vs)}</span>
                </li>
              ))}
            </ol>
          </div>
        )}
        {!compact && (
          <div className="summary-block">
            <div className="summary-label">Laggards</div>
            <ol className="summary-list">
              {s.laggards.map((x) => (
                <li key={x.name}>
                  <span className="nm">{x.name}</span>
                  <span className={`v ${tone(x.vs)}`}>{pp(x.vs)}</span>
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>

      <div className="summary-watch">
        <span className="summary-label">Watchlist{w.asOf ? ` · ${w.asOf} close` : ""}</span>
        <span>
          <strong>{w.inZone.length}</strong> of {w.total} priced inside entry range
          {w.inZone.length ? ` (${w.inZone.join(", ")})` : ""}
        </span>
        <span className={w.pastStop.length ? "down" : w.nearStop.length ? "warn" : ""}>{stopLine}</span>
        {w.nearInvalidation.length > 0 && (
          <span>
            Near invalidation (watch names): {w.nearInvalidation.map(stopTxt).join(", ")}
          </span>
        )}
        {w.gainer && (
          <span>
            Top gainer <strong>{w.gainer.ticker}</strong>{" "}
            <span className={tone(w.gainer.pct)}>{pct(w.gainer.pct)}</span>
          </span>
        )}
        {w.loser && (
          <span>
            Top loser <strong>{w.loser.ticker}</strong>{" "}
            <span className={tone(w.loser.pct)}>{pct(w.loser.pct)}</span>
          </span>
        )}
      </div>
    </section>
  );
}
