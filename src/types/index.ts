export type StockStatus =
  | "Active"
  | "Dip-buy"
  | "Breakout-watch"
  | "Holding"
  | "Watch-only"
  | "Wait-RBI"
  | "Dropped";

export interface WatchlistStock {
  ticker: string;
  name: string;
  sector: string;
  status: StockStatus;
  thesis: string;
  buyZone: boolean;
  buyZoneLevels: string | null;
  stop: string | null;
  target1: string | null;
  target2: string | null;
  price: number | null;
  dailyPct: number | null;
  rsi14: number | null;
  volume: number | null;
  volVs20d: number | null;
  support: string | null;
  resistance: string | null;
  sharesHeld: number | null;
  avgCost: number | null;
  addedDate: string;
  lastUpdated: string;
  notes: string | null;
  sparkline?: number[];
}

export interface HistoryEntry {
  date: string;
  ticker: string;
  name: string;
  status: string;
  price: number | null;
  dailyPct: number | null;
  rsi14: number | null;
  volume: number | null;
  volVs20d: number | null;
  support: string | null;
  resistance: string | null;
  buyZoneLevels: string | null;
  stop: string | null;
  notes: string | null;
  droppedThatDay: boolean;
}

export interface DroppedStock {
  ticker: string;
  name: string;
  sector: string;
  droppedDate: string;
  lastPrice: number | null;
  reason: string;
  priorStatus: string | null;
  notes: string | null;
}

export interface Meta {
  title: string;
  timezone: string;
  lastMarketUpdate: string;
  howToAdd: string;
  howToDrop: string;
  repoUrl: string;
  disclaimer: string;
}

/** Preferred display order for sector sections */
export const SECTOR_ORDER = [
  "Pharma",
  "Capital Goods / Industrial",
  "Capital Goods / Infrastructure",
  "Defence / Aerospace",
  "Auto Ancillaries",
  "IT / Cloud / Data center",
  "FMCG",
] as const;

export interface IndexBenchmark {
  name: string;
  symbol: string;
  last: number | null;
  dailyPct: number | null;
  weeklyPct: number | null;
  source: "official" | "watchlist";
  bars?: number;
}

export interface IndexSectorRow {
  sector: string;
  indexName: string | null;
  symbol: string | null;
  source: "official" | "watchlist" | "mixed";
  dailySource: "official" | "watchlist";
  weeklySource: "official" | "watchlist";
  last: number | null;
  dailyPct: number | null;
  weeklyPct: number | null;
  vsNiftyDaily: number | null;
  vsNiftyWeekly: number | null;
  watchlistTickers: string[];
  watchlistCount: number;
  note: string | null;
}

export interface IndicesData {
  asOf: string;
  timezone: string;
  lastRunUtc?: string;
  benchmark: IndexBenchmark;
  sectors: IndexSectorRow[];
  disclaimer: string;
}
