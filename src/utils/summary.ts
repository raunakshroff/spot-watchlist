import type { IndicesData, IndexUniverseRow, WatchlistStock } from "../types";
import { shortTicker } from "./format";

export type Period = "daily" | "weekly";

/** Distance (as % of stop) at or below which a name counts as "near stop". */
export const NEAR_STOP_PCT = 2;

/** Statuses where `stop` is a live trade stop; others treat it as an invalidation level. */
export const LIVE_STOP_STATUSES = new Set(["Active", "Holding"]);

export interface Mover {
  name: string;
  ret: number | null;
  vs: number | null;
}

export interface StopWatch {
  ticker: string;
  price: number;
  stop: number;
  distPct: number; // + = above stop, − = below (past stop)
  live: boolean; // true = trade stop (Active/Holding); false = invalidation level
}

export interface Summary {
  asOf: string;
  period: Period;
  periodLabel: string;
  nifty: { last: number | null; dailyPct: number | null; weeklyPct: number | null; ret: number | null };
  sensex: { last: number | null; dailyPct: number | null; weeklyPct: number | null; ret: number | null } | null;
  total: number;
  beat: number;
  lagged: number;
  inLine: number;
  leaders: Mover[];
  laggards: Mover[];
  watch: {
    total: number;
    inZone: string[];
    nearStop: StopWatch[];
    pastStop: StopWatch[];
    nearInvalidation: StopWatch[];
    closest: StopWatch | null;
    gainer: { ticker: string; pct: number } | null;
    loser: { ticker: string; pct: number } | null;
    asOf: string | null;
  };
  takeaway: string;
}

function shortIndexName(name: string): string {
  return name.replace(/^Nifty (India )?/, "").replace(/^BSE /, "");
}

function joinNames(xs: string[]): string {
  if (xs.length <= 1) return xs.join("");
  return `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`;
}

/** First "entry A-B" range(s) in buyZoneLevels; true if price sits inside any. */
export function inEntryRange(s: WatchlistStock): boolean {
  if (s.price == null || !s.buyZoneLevels) return false;
  const re = /entry\s+([\d,]+(?:\.\d+)?)\s*[-–]\s*([\d,]+(?:\.\d+)?)/gi;
  let m: RegExpExecArray | null;
  while ((m = re.exec(s.buyZoneLevels))) {
    const lo = parseFloat(m[1].replace(/,/g, ""));
    const hi = parseFloat(m[2].replace(/,/g, ""));
    if (s.price >= Math.min(lo, hi) && s.price <= Math.max(lo, hi)) return true;
  }
  return false;
}

/** Single stop level from e.g. "close <4680"; ambiguous multi-level stops return null. */
export function parseStop(stop: string | null): number | null {
  if (!stop) return null;
  const nums = [...stop.matchAll(/<\s*([\d,]+(?:\.\d+)?)/g)].map((m) => parseFloat(m[1].replace(/,/g, "")));
  return nums.length === 1 ? nums[0] : null;
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

export function buildSummary(
  data: IndicesData,
  watchlist: WatchlistStock[],
  period: Period,
): Summary {
  const rows: IndexUniverseRow[] = data.indices ?? [];
  const pick = (r: IndexUniverseRow) => ({
    ret: period === "daily" ? r.dailyPct : r.weeklyPct,
    vs: period === "daily" ? r.vsNiftyDaily : r.vsNiftyWeekly,
  });

  const peers = rows.filter((r) => !r.isBenchmark);
  const scored = peers
    .map((r) => ({ name: r.name, ...pick(r) }))
    .filter((x) => x.vs != null);
  const sorted = [...scored].sort((a, b) => (b.vs ?? 0) - (a.vs ?? 0));
  const beat = scored.filter((x) => (x.vs ?? 0) > 0).length;
  const lagged = scored.filter((x) => (x.vs ?? 0) < 0).length;
  const inLine = scored.length - beat - lagged;
  const leaders = sorted.slice(0, 3);
  const laggards = sorted.slice(-3).reverse();

  const b = data.benchmark;
  const niftyRet = period === "daily" ? b.dailyPct : b.weeklyPct;
  const sx = rows.find((r) => r.yahooSymbol === "^BSESN");
  const sensex = sx
    ? { last: sx.last, dailyPct: sx.dailyPct, weeklyPct: sx.weeklyPct, ret: pick(sx).ret }
    : null;

  // Watchlist snapshot (always as of the latest close in watchlist.json)
  const inZone = watchlist.filter(inEntryRange).map((s) => shortTicker(s.ticker));
  const stops: StopWatch[] = watchlist
    .map((s) => {
      const st = parseStop(s.stop);
      if (st == null || s.price == null) return null;
      return {
        ticker: shortTicker(s.ticker),
        price: s.price,
        stop: st,
        distPct: round2(((s.price - st) / st) * 100),
        live: LIVE_STOP_STATUSES.has(s.status),
      };
    })
    .filter((x): x is StopWatch => x != null)
    .sort((a, c) => a.distPct - c.distPct);
  const live = stops.filter((x) => x.live);
  const pastStop = live.filter((x) => x.distPct < 0);
  const nearStop = live.filter((x) => x.distPct >= 0 && x.distPct <= NEAR_STOP_PCT);
  const nearInvalidation = stops.filter((x) => !x.live && x.distPct <= NEAR_STOP_PCT);
  const withPct = watchlist.filter((s) => s.dailyPct != null);
  const bySorted = [...withPct].sort((a, c) => (c.dailyPct ?? 0) - (a.dailyPct ?? 0));
  const gainer = bySorted[0]
    ? { ticker: shortTicker(bySorted[0].ticker), pct: bySorted[0].dailyPct as number }
    : null;
  const loser = bySorted.length
    ? {
        ticker: shortTicker(bySorted[bySorted.length - 1].ticker),
        pct: bySorted[bySorted.length - 1].dailyPct as number,
      }
    : null;
  const wlDates = watchlist.map((s) => s.lastUpdated).filter(Boolean).sort();

  // Template takeaway — purely derived from the numbers above
  const total = scored.length;
  const share = total ? beat / total : 0;
  const breadth =
    share >= 0.65
      ? "Broad outperformance"
      : share <= 0.35
        ? "Broad underperformance"
        : "Mixed breadth";
  const pLabel = period === "daily" ? "today" : "this week";
  const niftyMove =
    niftyRet == null
      ? "Nifty 50 n/a"
      : `Nifty 50 ${niftyRet >= 0 ? "+" : ""}${niftyRet.toFixed(2)}% ${pLabel}`;
  const parts = [
    `${breadth}: ${beat} of ${total} beat Nifty, ${lagged} lagged${inLine ? `, ${inLine} in line` : ""}`,
    niftyMove,
  ];
  if (leaders.length) parts.push(`${joinNames(leaders.map((x) => shortIndexName(x.name)))} led`);
  if (laggards.length) parts.push(`${joinNames(laggards.map((x) => shortIndexName(x.name)))} dragged`);
  const takeaway = parts.join("; ") + ".";

  return {
    asOf: data.asOf,
    period,
    periodLabel: period === "daily" ? "Day" : `Week (since ${data.weekRefDate ?? "1 wk ago"})`,
    nifty: { last: b.last, dailyPct: b.dailyPct, weeklyPct: b.weeklyPct, ret: niftyRet },
    sensex,
    total,
    beat,
    lagged,
    inLine,
    leaders,
    laggards,
    watch: {
      total: watchlist.length,
      inZone,
      nearStop,
      pastStop,
      nearInvalidation,
      closest: live[0] ?? null,
      gainer,
      loser,
      asOf: wlDates.length ? wlDates[wlDates.length - 1] : null,
    },
    takeaway,
  };
}
