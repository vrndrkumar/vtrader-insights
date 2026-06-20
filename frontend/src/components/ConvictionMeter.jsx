import { fmtScore } from "../lib/format";

function scoreColor(s) {
  if (s == null) return "var(--text-3)";
  if (s >= 70) return "var(--teal)";
  if (s >= 55) return "var(--gold)";
  if (s >= 40) return "var(--amber)";
  return "var(--rose)";
}

const CATS = [
  { key: "fundamental", label: "Fund.",   weight: 25 },
  { key: "technical",   label: "Tech.",   weight: 40 },
  { key: "sector",      label: "Sector",  weight: 20 },
  { key: "momentum",    label: "Mom.",    weight: 15 },
];

export default function ConvictionMeter({ scores = {}, size = "full", className = "" }) {
  const overall = scores.overall ?? scores.overall_score;
  const color   = scoreColor(overall);

  if (size === "compact") return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div className="h-1.5 w-20 rounded-full overflow-hidden" style={{ background: "var(--surface-3)" }}>
        <div className="h-full rounded-full transition-all"
          style={{ width: `${Math.max(2, overall ?? 0)}%`, background: color, boxShadow: `0 0 6px ${color}60` }} />
      </div>
      <span className="font-mono text-xs tabular-nums" style={{ color: "var(--text-2)" }}>{fmtScore(overall)}</span>
    </div>
  );

  return (
    <div className={className}>
      <div className="flex items-baseline justify-between mb-2">
        <span className="text-xs uppercase tracking-widest font-display font-semibold" style={{ color: "var(--text-3)" }}>
          Conviction Score
        </span>
        <span className="font-mono text-3xl font-bold tabular-nums" style={{ color }}>
          {fmtScore(overall)}<span className="text-sm font-normal" style={{ color: "var(--text-3)" }}>/100</span>
        </span>
      </div>

      <div className="h-2 w-full rounded-full overflow-hidden mb-4" style={{ background: "var(--surface-3)" }}>
        <div className="h-full rounded-full transition-all"
          style={{ width: `${Math.max(2, overall ?? 0)}%`, background: color, boxShadow: `0 0 8px ${color}50` }} />
      </div>

      <div className="flex gap-2">
        {CATS.map(cat => {
          const val = scores[cat.key];
          const c   = scoreColor(val);
          return (
            <div key={cat.key} className="flex flex-col gap-1" style={{ flexGrow: cat.weight, flexBasis: 0 }}>
              <div className="h-1 rounded-full overflow-hidden" style={{ background: "var(--surface-3)" }}>
                <div className="h-full rounded-full" style={{ width: `${Math.max(2, val ?? 0)}%`, background: c }} />
              </div>
              <div className="flex items-baseline justify-between leading-none">
                <span className="text-[10px]" style={{ color: "var(--text-3)" }}>{cat.label}</span>
                <span className="text-[10px] font-mono" style={{ color: "var(--text-2)" }}>{fmtScore(val)}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}