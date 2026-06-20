const VERDICTS = [
  { key: "Strong Buy", color: "var(--teal)",  bg: "var(--teal-dim)",  border: "rgba(15,217,160,0.25)" },
  { key: "Buy",        color: "var(--teal)",  bg: "var(--teal-dim)",  border: "rgba(15,217,160,0.2)" },
  { key: "Watchlist",  color: "var(--amber)", bg: "var(--amber-dim)", border: "rgba(245,158,11,0.25)" },
  { key: "Avoid",      color: "var(--rose)",  bg: "var(--rose-dim)",  border: "rgba(240,82,112,0.25)" },
];

export default function VerdictDistribution({ counts = {}, total = 0 }) {
  const analyzed   = VERDICTS.reduce((s, v) => s + (counts[v.key] || 0), 0);
  const unanalyzed = Math.max(0, total - analyzed);
  const segments   = [
    ...VERDICTS.map(v => ({ ...v, value: counts[v.key] || 0 })),
    { key: "Not Analyzed", color: "var(--line-2)", bg: "var(--surface-3)", border: "var(--line)", value: unanalyzed },
  ].filter(s => s.value > 0);

  return (
    <div className="rounded-2xl border p-5" style={{ background: "var(--surface)", borderColor: "var(--line)" }}>
      <div className="flex items-center justify-between mb-1">
        <h2 className="font-display font-bold text-sm" style={{ color: "var(--text-1)" }}>Coverage & Verdicts</h2>
        <span className="font-mono text-xs" style={{ color: "var(--text-3)" }}>{analyzed}/{total} analyzed</span>
      </div>
      <div className="h-2.5 w-full rounded-full overflow-hidden flex mt-3 mb-5" style={{ background: "var(--surface-3)" }}>
        {segments.map(s => (
          <div key={s.key} style={{ width: `${total ? (s.value/total)*100 : 0}%`, background: s.color }} title={`${s.key}: ${s.value}`} />
        ))}
      </div>
      <div className="grid grid-cols-2 gap-2">
        {[...VERDICTS, { key: "Not Analyzed", color: "var(--text-3)", bg: "var(--surface-3)", border: "var(--line)", value: unanalyzed }]
          .map(v => (
          <div key={v.key} className="flex items-center justify-between rounded-xl px-3 py-2.5 border" style={{ background: v.bg, borderColor: v.border }}>
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full" style={{ background: v.color }} />
              <span className="text-xs font-medium" style={{ color: v.color }}>{v.key}</span>
            </div>
            <span className="font-mono text-sm font-bold" style={{ color: v.color }}>
              {v.key === "Not Analyzed" ? unanalyzed : (counts[v.key] || 0)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}