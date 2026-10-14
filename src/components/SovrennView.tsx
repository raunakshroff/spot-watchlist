import { Fragment, useMemo, useState } from "react";
import type { SovrennEntry } from "../types";
import { formatPct, formatPrice } from "../utils/format";

type Key =
  | "ticker"
  | "name"
  | "firstHighlighted"
  | "timesMentioned"
  | "latestDate"
  | "priceAtHighlight"
  | "price"
  | "pctSinceHighlight"
  | "mcapCr"
  | "rsi14"
  | "buyZone";

const COLS: { key: Key; label: string }[] = [
  { key: "ticker", label: "Symbol" },
  { key: "name", label: "Name" },
  { key: "firstHighlighted", label: "First highlighted" },
  { key: "timesMentioned", label: "Mentions" },
  { key: "latestDate", label: "Latest" },
  { key: "priceAtHighlight", label: "Price @ highlight" },
  { key: "price", label: "Current" },
  { key: "pctSinceHighlight", label: "% since" },
  { key: "mcapCr", label: "MCap (₹ Cr)" },
  { key: "rsi14", label: "RSI" },
  { key: "buyZone", label: "Buy zone" },
];

function sym(e: SovrennEntry) {
  return e.ticker ? e.ticker.replace(/\.(NS|BO)$/, "") : e.key;
}

export function SovrennView({ data, loadError }: { data: SovrennEntry[] | null; loadError: string | null }) {
  const [sortKey, setSortKey] = useState<Key>("latestDate");
  const [asc, setAsc] = useState(false);
  const [q, setQ] = useState("");
  const [onlyBz, setOnlyBz] = useState(false);
  const [open, setOpen] = useState<string | null>(null);

  const rows = useMemo(() => {
    if (!data) return [];
    const val = (e: SovrennEntry): string | number => {
      if (sortKey === "ticker") return sym(e);
      if (sortKey === "buyZone") return e.buyZone === "Y" ? 2 : e.buyZone === "N" ? 1 : 0;
      const v = (e as unknown as Record<string, unknown>)[sortKey];
      return typeof v === "number" || typeof v === "string" ? v : -Infinity;
    };
    return data
      .filter((e) => !onlyBz || e.buyZone === "Y")
      .filter((e) => !q || `${e.name} ${sym(e)} ${e.latestTag ?? ""}`.toLowerCase().includes(q.toLowerCase()))
      .slice()
      .sort((a, b) => {
        const x = val(a), y = val(b);
        const c = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
        return asc ? c : -c;
      });
  }, [data, sortKey, asc, q, onlyBz]);

  if (loadError) return <div className="empty">Could not load Sovrenn list: {loadError}</div>;
  if (!data) return <div className="loading">Loading…</div>;

  const bz = data.filter((e) => e.buyZone === "Y").length;

  return (
    <section>
      <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", margin: "0 0 12px" }}>
        Companies highlighted in Sovrenn Times (daily edition). Separate from the watchlist. {data.length} names ·{" "}
        {bz} in buy zone now. Price @ highlight = close on the edition date. Buy zone (daily): above 200 DMA, within 0
        to +4% of 20/50 DMA, RSI 40 to 60, not more than 8% above 20 DMA. n/a = not enough Yahoo history. Click a row
        for Sovrenn's text.
      </p>
      <div style={{ display: "flex", gap: 12, marginBottom: 12, alignItems: "center", flexWrap: "wrap" }}>
        <input className="search" placeholder="Search name, symbol, tag…" value={q} onChange={(e) => setQ(e.target.value)} />
        <label style={{ fontSize: "0.85rem" }}>
          <input type="checkbox" checked={onlyBz} onChange={(e) => setOnlyBz(e.target.checked)} /> Buy zone only
        </label>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {COLS.map((c) => (
                <th
                  key={c.key}
                  style={{ cursor: "pointer", userSelect: "none" }}
                  onClick={() => {
                    if (sortKey === c.key) setAsc(!asc);
                    else {
                      setSortKey(c.key);
                      setAsc(false);
                    }
                  }}
                >
                  {c.label}
                  {sortKey === c.key ? (asc ? " ▲" : " ▼") : ""}
                </th>
              ))}
              <th>Latest reason</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e) => (
              <Fragment key={e.key}>
                <tr key={e.key} onClick={() => setOpen(open === e.key ? null : e.key)} style={{ cursor: "pointer" }}>
                  <td>
                    <strong style={{ fontFamily: "var(--mono)" }}>{sym(e)}</strong>
                    {e.sme && <span className="chip" style={{ marginLeft: 6 }}>SME</span>}
                  </td>
                  <td>{e.name}</td>
                  <td style={{ fontFamily: "var(--mono)" }}>{e.firstHighlighted}</td>
                  <td style={{ fontFamily: "var(--mono)" }}>{e.timesMentioned}</td>
                  <td style={{ fontFamily: "var(--mono)" }}>{e.latestDate}</td>
                  <td style={{ fontFamily: "var(--mono)" }}>{e.priceAtHighlight != null ? formatPrice(e.priceAtHighlight) : "n/a"}</td>
                  <td style={{ fontFamily: "var(--mono)" }}>{e.price != null ? formatPrice(e.price) : "n/a"}</td>
                  <td
                    style={{ fontFamily: "var(--mono)" }}
                    className={e.pctSinceHighlight == null ? "" : e.pctSinceHighlight >= 0 ? "up" : "down"}
                  >
                    {e.pctSinceHighlight != null ? formatPct(e.pctSinceHighlight) : "n/a"}
                  </td>
                  <td style={{ fontFamily: "var(--mono)" }} title={e.sovrennMcap ? `Sovrenn: ${e.sovrennMcap}` : ""}>
                    {e.mcapCr != null ? e.mcapCr.toLocaleString("en-IN") : "n/a"}
                  </td>
                  <td style={{ fontFamily: "var(--mono)" }}>{e.rsi14 ?? "n/a"}</td>
                  <td title={e.buyZoneNote}>
                    <span className={`badge ${e.buyZone === "Y" ? "badge-Active" : e.buyZone === "N" ? "badge-Dropped" : "badge-Watch-only"}`}>
                      {e.buyZone ?? "n/a"}
                    </span>
                  </td>
                  <td style={{ whiteSpace: "normal", maxWidth: 420 }}>{e.latestReason ?? "n/a"}</td>
                </tr>
                {open === e.key && (
                  <tr key={`${e.key}-d`}>
                    <td colSpan={COLS.length + 1} style={{ whiteSpace: "normal", color: "var(--text-muted)" }}>
                      {e.mentions
                        .slice()
                        .reverse()
                        .map((m) => (
                          <div key={m.date} style={{ marginBottom: 8 }}>
                            <strong>{m.date}</strong> · MCap {m.sovrennMcap ?? "n/a"} · PE {m.sovrennPe ?? "n/a"}
                            <div>{m.filing}</div>
                            {m.outlook && <div style={{ marginTop: 4 }}>Outlook: {m.outlook}</div>}
                          </div>
                        ))}
                      <div>
                        Buy-zone check: {e.buyZoneNote ?? "n/a"} · 20/50/200 DMA {e.dma20 ?? "n/a"} / {e.dma50 ?? "n/a"} /{" "}
                        {e.dma200 ?? "n/a"} · Yahoo {e.ticker ?? "unresolved"} · price as of {e.priceDate ?? "n/a"}
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
