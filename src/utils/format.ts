export function formatPrice(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("en-IN", {
    minimumFractionDigits: n >= 1000 ? 0 : 2,
    maximumFractionDigits: 2,
  });
}

export function formatPct(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(1)}%`;
}

export function formatRsi(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return Math.round(n).toString();
}

export function shortTicker(ticker: string): string {
  return ticker.replace(/\.NS$/, "").replace(/\.BO$/, "");
}

export function nearBuyZone(stock: {
  buyZone: boolean;
  price: number | null;
  buyZoneLevels: string | null;
}): boolean {
  return stock.buyZone === true;
}

export function rsiTone(rsi: number | null | undefined): "hot" | "cold" | "neutral" {
  if (rsi == null) return "neutral";
  if (rsi >= 70) return "hot";
  if (rsi <= 35) return "cold";
  return "neutral";
}

/** ₹-prefixed Indian-grouped price, e.g. ₹9,144.5 */
export function formatInr(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return `₹${formatPrice(n)}`;
}

/** Signed percent with configurable digits. */
export function formatSignedPct(n: number | null | undefined, digits = 1): string {
  if (n == null || Number.isNaN(n)) return "—";
  const sign = n > 0 ? "+" : n < 0 ? "−" : "";
  return `${sign}${Math.abs(n).toFixed(digits)}%`;
}

export function toneOf(n: number | null | undefined): "up" | "down" | "" {
  if (n == null || Number.isNaN(n) || n === 0) return "";
  return n > 0 ? "up" : "down";
}
