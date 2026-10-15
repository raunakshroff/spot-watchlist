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
  "Private Bank",
  "Financial Services",
  "Capital Markets / Exchanges",
  "Healthcare / Diagnostics",
  "Chemicals",
  "FMCG",
] as const;

export interface IndexBenchmark {
  name: string;
  symbol: string;
  last: number | null;
  dailyPct: number | null;
  weeklyPct: number | null;
  m1Pct?: number | null;
  m3Pct?: number | null;
  m6Pct?: number | null;
  y1Pct?: number | null;
  y5Pct?: number | null;
  source: "official" | "watchlist";
  dataSource?: "nse" | "yahoo";
  nseSymbol?: string;
  bars?: number;
}

export type IndexGroup = "Broad Market" | "Sectoral" | "Thematic" | "Strategy" | "BSE";

export type IndexHorizon = "daily" | "weekly" | "m1" | "m3" | "m6" | "y1" | "y5";

export interface IndexUniverseRow {
  id: string;
  name: string;
  nseSymbol: string | null;
  yahooSymbol: string | null;
  group: IndexGroup | string;
  dataSource: "nse" | "yahoo";
  last: number | null;
  dailyPct: number | null;
  weeklyPct: number | null;
  m1Pct?: number | null;
  m3Pct?: number | null;
  m6Pct?: number | null;
  y1Pct?: number | null;
  y5Pct?: number | null;
  vsNiftyDaily: number | null;
  vsNiftyWeekly: number | null;
  vsNiftyM1?: number | null;
  vsNiftyM3?: number | null;
  vsNiftyM6?: number | null;
  vsNiftyY1?: number | null;
  vsNiftyY5?: number | null;
  watchlistSectors: string[];
  watchlistTickers: string[];
  isBenchmark?: boolean;
}

export interface IndexSectorRow {
  sector: string;
  indexName: string | null;
  symbol: string | null;
  nseSymbol?: string | null;
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
  primarySource?: "nse" | "yahoo";
  weekRefDate?: string;
  weeklyBasis?: string;
  horizonBasis?: {
    asOfArchive?: string;
    lookbacksCalendarDays?: Record<string, number>;
    sources?: string;
    missingLongHistory?: string[];
  };
  benchmark: IndexBenchmark;
  groups?: { group: string; count: number }[];
  indices?: IndexUniverseRow[];
  sectors: IndexSectorRow[];
  skipped?: { nseSymbol?: string; yahooSymbol?: string; reason: string }[];
  notTracked?: string[];
  disclaimer: string;
}

export interface IndexHistoryData {
  asOf: string;
  timezone: string;
  benchmarkId: string;
  builtUtc?: string;
  source?: string;
  daily: { dates: string[]; series: Record<string, (number | null)[]> };
  weekly: { dates: string[]; series: Record<string, (number | null)[]> };
  coverage?: Record<
    string,
    { dailyBars: number; weeklyBars: number; firstDaily: string | null; firstWeekly: string | null }
  >;
}

export interface SovrennMention {
  date: string;
  tag: string | null;
  filing: string | null;
  outlook: string | null;
  sovrennMcap: string | null;
  sovrennPe: string | null;
}

export interface SovrennEntry {
  key: string;
  name: string;
  ticker: string | null;
  sme: boolean;
  firstHighlighted: string;
  firstCoveredBySovrenn: string | null;
  timesMentioned: number;
  latestDate: string;
  latestTag: string | null;
  latestReason: string | null;
  latestOutlook: string | null;
  sovrennMcap: string | null;
  sovrennPe: string | null;
  mentions: SovrennMention[];
  price?: number | null;
  priceDate?: string;
  priceAtHighlight?: number | null;
  priceAtHighlightDate?: string | null;
  pctSinceHighlight?: number | null;
  mcapCr?: number | null;
  rsi14?: number | null;
  dma20?: number | null;
  dma50?: number | null;
  dma200?: number | null;
  buyZone?: "Y" | "N" | "n/a";
  buyZoneNote?: string;
}
