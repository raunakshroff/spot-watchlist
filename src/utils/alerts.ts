import type { PriceAlert, WatchlistStock } from "../types";

export function alertLevels(a: PriceAlert): string {
  if (a.type === "range") return `${a.low}–${a.high}`;
  if (a.type === "closeAbove") return `close >${a.level}`;
  return `close <${a.level}`;
}

export const alertCounts = (s: WatchlistStock) => {
  const list = s.alerts ?? [];
  return { armed: list.filter((a) => a.status !== "triggered").length, hit: list.filter((a) => a.status === "triggered").length };
};
