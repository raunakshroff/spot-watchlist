import { LineChart, Line, ResponsiveContainer, YAxis } from "recharts";

interface Props {
  data: number[];
  up?: boolean;
}

export function Sparkline({ data, up = true }: Props) {
  if (!data?.length) return <div className="spark" />;
  const chartData = data.map((v, i) => ({ i, v }));
  const color = up ? "#3dd68c" : "#ff6b7a";
  return (
    <div className="spark">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 4, right: 0, left: 0, bottom: 4 }}>
          <YAxis domain={["dataMin", "dataMax"]} hide />
          <Line
            type="monotone"
            dataKey="v"
            stroke={color}
            strokeWidth={1.75}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
