import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

function colorFor(s) {
  if (s >= 70) return "var(--teal)";
  if (s >= 55) return "var(--gold)";
  if (s >= 40) return "var(--amber)";
  return "var(--rose)";
}

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-xl border px-3 py-2 text-xs shadow-lg"
      style={{ background: "var(--surface)", borderColor: "var(--line)", boxShadow: "var(--shadow-md)" }}>
      <div className="font-semibold mb-1" style={{ color: "var(--text-1)" }}>{d.sector}</div>
      <div style={{ color: "var(--text-2)" }}>Avg Score: <span className="font-mono">{d.avg_score}</span></div>
      <div style={{ color: "var(--text-2)" }}>Stocks: <span className="font-mono">{d.count}</span></div>
    </div>
  );
};

export default function SectorStrengthChart({ data = [] }) {
  const chartData = data.slice(0, 12);
  return (
    <div className="rounded-2xl border p-5" style={{ background: "var(--surface)", borderColor: "var(--line)" }}>
      <h2 className="font-display font-bold text-sm mb-1" style={{ color: "var(--text-1)" }}>Sector Strength</h2>
      <p className="text-xs mb-4" style={{ color: "var(--text-3)" }}>Average score across analyzed stocks per sector</p>
      {!chartData.length
        ? <div className="flex items-center justify-center h-32 text-sm" style={{ color: "var(--text-3)" }}>No sector data — run analysis first.</div>
        : (
          <ResponsiveContainer width="100%" height={Math.max(200, chartData.length * 36)}>
            <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 32, top: 4, bottom: 4 }}>
              <XAxis type="number" domain={[0, 100]} hide />
              <YAxis type="category" dataKey="sector" width={140}
                tick={{ fill: "var(--text-2)", fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
              <Bar dataKey="avg_score" radius={[0, 6, 6, 0]} barSize={14}>
                {chartData.map((d, i) => <Cell key={i} fill={colorFor(d.avg_score)} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
    </div>
  );
}