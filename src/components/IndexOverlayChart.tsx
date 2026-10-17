import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { IndexHistoryData, IndexHorizon } from "../types";

const COLORS = [
  "#60a5fa",
  "#34d399",
  "#fbbf24",
  "#f472b6",
  "#a78bfa",
  "#22d3ee",
  "#fb923c",
  "#a3e635",
];

interface Props {
  history: IndexHistoryData | null;
  period: IndexHorizon;
  selectedIds: string[];
  namesById: Record<string, string>;
}

function windowDates(dates: string[], period: IndexHorizon, asOf: string): string[] {
  if (!dates.length) return [];
  const end = asOf || dates[dates.length - 1];
  const endT = Date.parse(end);
  const day = 86400000;
  const lookback: Record<IndexHorizon, number> = {
    daily: 5 * day,
    weekly: 7 * day,
    m1: 31 * day,
    m3: 93 * day,
    m6: 186 * day,
    y1: 370 * day,
    y5: 365 * 5 * day + 14 * day,
  };
  const startT = endT - lookback[period];
  return dates.filter((d) => {
    const t = Date.parse(d);
    return t >= startT && t <= endT;
  });
}

function rebase(vals: (number | null)[]): (number | null)[] {
  const first = vals.find((v) => v != null && v > 0);
  if (first == null) return vals.map(() => null);
  return vals.map((v) => (v == null || v <= 0 ? null : Math.round((v / first) * 10000) / 100));
}

function useNarrow(maxWidth = 640): boolean {
  const q = `(max-width: ${maxWidth}px)`;
  const [narrow, setNarrow] = useState(() => typeof window !== "undefined" && window.matchMedia(q).matches);
  useEffect(() => {
    const mq = window.matchMedia(q);
    const on = () => setNarrow(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [q]);
  return narrow;
}

export function IndexOverlayChart({ history, period, selectedIds, namesById }: Props) {
  const narrow = useNarrow();
  const chart = useMemo(() => {
    if (!history || selectedIds.length === 0) return null;
    const useDaily = period === "daily" || period === "weekly" || period === "m1" || period === "m3";
    const pack = useDaily ? history.daily : history.weekly;
    // Prefer daily for 6M/1Y when dense enough; else weekly
    const pack6 = period === "m6" || period === "y1" ? (history.daily.dates.length >= 100 ? history.daily : history.weekly) : pack;
    const chosen = period === "m6" || period === "y1" ? pack6 : pack;
    const dates = windowDates(chosen.dates, period, history.asOf);
    if (dates.length < 2) return null;
    const idx = dates.map((d) => chosen.dates.indexOf(d));
    const series = selectedIds.map((id) => {
      const raw = chosen.series[id];
      const sliced = raw ? idx.map((i) => (i >= 0 ? raw[i] : null)) : dates.map(() => null);
      return { id, name: namesById[id] ?? id, values: rebase(sliced) };
    });
    // Always include Nifty if not selected
    const benchId = history.benchmarkId;
    if (!selectedIds.includes(benchId) && chosen.series[benchId]) {
      const raw = chosen.series[benchId];
      const sliced = idx.map((i) => (i >= 0 ? raw[i] : null));
      series.unshift({ id: benchId, name: "Nifty 50", values: rebase(sliced) });
    }
    const rows = dates.map((d, i) => {
      const row: Record<string, string | number | null> = { date: d.slice(2) }; // YY-MM-DD compact
      for (const s of series) row[s.id] = s.values[i];
      return row;
    });
    return { rows, series, pointCount: dates.length };
  }, [history, period, selectedIds, namesById]);

  if (!history) {
    return <div className="ix-chart-empty">Loading index history…</div>;
  }
  if (selectedIds.length === 0) {
    return (
      <div className="ix-chart-empty">
        <strong>Overlay chart</strong>
        <span>Tap any index row or leaderboard name to chart it against Nifty 50 (rebased to 100). Up to 6 at once.</span>
      </div>
    );
  }
  if (!chart) {
    return <div className="ix-chart-empty">Not enough history in this window to chart the selection.</div>;
  }

  return (
    <div className="ix-chart-wrap">
      <div className="ix-chart-head">
        <span>Overlay vs Nifty 50</span>
        <span className="ix-chart-meta">
          rebased to 100 · {chart.pointCount} points · {selectedIds.length} selected
        </span>
      </div>
      <div className="ix-chart">
        <ResponsiveContainer width="100%" height={narrow ? 230 : 340}>
          <LineChart data={chart.rows} margin={{ top: 8, right: narrow ? 6 : 16, left: narrow ? -8 : 0, bottom: 0 }}>
            <CartesianGrid stroke="rgba(148,163,184,0.10)" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fill: "var(--text-dim)", fontSize: 10 }}
              minTickGap={narrow ? 36 : 28}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: "var(--text-dim)", fontSize: 10 }}
              axisLine={false}
              tickLine={false}
              domain={["auto", "auto"]}
              width={narrow ? 36 : 44}
            />
            <Tooltip
              contentStyle={{
                background: "var(--surface-2)",
                border: "1px solid var(--border-strong)",
                borderRadius: 10,
                fontSize: 12,
                boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
              }}
              itemStyle={{ padding: 0 }}
              labelStyle={{ color: "var(--text-muted)" }}
            />
            <Legend
              verticalAlign="bottom"
              iconType="plainline"
              wrapperStyle={{ fontSize: narrow ? 10 : 11.5, paddingTop: 6, lineHeight: "16px" }}
            />
            {chart.series.map((s, i) => (
              <Line
                key={s.id}
                type="monotone"
                dataKey={s.id}
                name={s.name}
                stroke={s.id === history.benchmarkId ? "#cbd5e1" : COLORS[i % COLORS.length]}
                strokeWidth={s.id === history.benchmarkId ? 2.2 : 1.7}
                strokeDasharray={s.id === history.benchmarkId ? "5 4" : undefined}
                dot={false}
                connectNulls
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
