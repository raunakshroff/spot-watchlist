import type { StockStatus } from "../types";

const CLASS_MAP: Record<string, string> = {
  Active: "badge-Active",
  "Dip-buy": "badge-Dip-buy",
  "Breakout-watch": "badge-Breakout-watch",
  Holding: "badge-Holding",
  "Watch-only": "badge-Watch-only",
  "Wait-RBI": "badge-Wait-RBI",
  Dropped: "badge-Dropped",
};

export function StatusBadge({ status }: { status: StockStatus | string }) {
  const cls = CLASS_MAP[status] ?? "badge-Watch-only";
  return <span className={`badge ${cls}`}>{status}</span>;
}
