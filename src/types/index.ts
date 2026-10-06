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
