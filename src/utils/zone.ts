import type { WatchlistStock } from "../types";
import { inEntryRange, parseStop } from "./summary";

/** Price within this % above the stop counts as "near stop" for the zone chip. */
export const ZONE_NEAR_STOP_PCT = 1;

export type ZoneKind = "below" | "near" | "buy" | "wait";

export interface Zone {
  kind: ZoneKind;
  label: string;
  stop: number | null;
  /** + = above stop, − = below stop; null when the stop text has no single level */
  distPct: number | null;
}

export const ZONE_LABEL: Record<ZoneKind, string> = {
  below: "Below stop",
  near: "Near stop",
  buy: "Buy zone",
  wait: "Waiting on trigger",
};

/** Lower = more urgent. Used for default sort. */
export const ZONE_RANK: Record<ZoneKind, number> = { below: 0, near: 1, buy: 2, wait: 3 };

export function computeZone(s: WatchlistStock): Zone {
  const stop = parseStop(s.stop);
  const distPct = stop != null && s.price != null ? ((s.price - stop) / stop) * 100 : null;
  let kind: ZoneKind = "wait";
  if (distPct != null && distPct < 0) kind = "below";
  else if (distPct != null && distPct <= ZONE_NEAR_STOP_PCT) kind = "near";
  else if (s.buyZone || inEntryRange(s)) kind = "buy";
  return { kind, label: ZONE_LABEL[kind], stop, distPct };
}

/** First number in a free-text level, e.g. "1583 (50DMA)" → 1583. */
export function firstLevel(txt: string | null | undefined): number | null {
  if (!txt) return null;
  const m = txt.match(/([\d,]+(?:\.\d+)?)/);
  if (!m) return null;
  const n = parseFloat(m[1].replace(/,/g, ""));
  return Number.isFinite(n) ? n : null;
}
