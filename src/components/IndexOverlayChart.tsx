import { useMemo } from "react";
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
  "#5b8cff",
  "#3dd68c",
  "#f5b942",
  "#ff6b7a",
  "#c084fc",
  "#22d3ee",
  "#fb7185",
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

export function IndexOverlayChart({ history, period, selectedIds, namesById }: Props) {
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
    return <div className="empty compact">Loading index history…</div>;
  }
  if (selectedIds.length === 0) {
    return (
      <div className="empty compact">
        Select one or more indices below (click a row) to overlay vs Nifty 50, rebased to 100.
      </div>
    );
  }
  if (!chart) {
    return <div className="empty compact">Not enough history in this window to chart the selection.</div>;
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
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={chart.rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fill: "var(--text-dim)", fontSize: 10 }}
              minTickGap={28}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: "var(--text-dim)", fontSize: 10 }}
              axisLine={false}
              tickLine={false}
              domain={["auto", "auto"]}
              width={42}
            />
            <Tooltip
              contentStyle={{
                background: "var(--bg-card)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                fontSize: 12,
              }}
              labelStyle={{ color: "var(--text-muted)" }}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {chart.series.map((s, i) => (
              <Line
                key={s.id}
                type="monotone"
                dataKey={s.id}
                name={s.name}
                stroke={s.id === history.benchmarkId ? "#9db8ff" : COLORS[i % COLORS.length]}
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
