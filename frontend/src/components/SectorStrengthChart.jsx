import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { TrendingUp, TrendingDown } from "lucide-react";
import { getSectorSummary } from "../lib/api";
import { SectionLabel } from "./ui";

const VERDICTS  = ["Strong Buy", "Buy", "Watchlist", "Avoid"];
const V_COLORS  = {
  "Strong Buy": "#0ea070",
  "Buy":        "#5dcaa5",
  "Watchlist":  "#ef9f27",
  "Avoid":      "#e24b4a",
};

function scoreColor(s) {
  if (s >= 65) return "var(--teal)";
  if (s >= 45) return "var(--gold)";
  return "var(--rose)";
}

function StackedBar({ counts }) {
  const total = VERDICTS.reduce((s, v) => s + (counts[v] || 0), 0);
  if (!total) return null;
  return (
    <div className="flex h-2 w-full rounded-full overflow-hidden gap-px">
      {VERDICTS.map(v => {
        const pct = ((counts[v] || 0) / total) * 100;
        if (!pct) return null;
        return (
          <div key={v} style={{ width: `${pct}%`, background: V_COLORS[v] }}
            title={`${v}: ${counts[v]}`} />
        );
      })}
    </div>
  );
}

function SectorRow({ s }) {
  const color = scoreColor(s.sector_score);
  const total = VERDICTS.reduce((acc, v) => acc + (s.verdict_counts?.[v] || 0), 0);

  return (
    <div className="rounded-xl border p-3"
      style={{ background: "var(--surface)", borderColor: "var(--line)" }}>
      <div className="flex items-center gap-3">
        {/* Score circle */}
        <div className="w-12 shrink-0 text-center">
          <div className="font-mono text-xl font-bold" style={{ color }}>
            {Math.round(s.sector_score)}
          </div>
          <div className="text-[9px] uppercase tracking-wide" style={{ color: "var(--text-3)" }}>score</div>
        </div>
        {/* Main content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline justify-between mb-2">
            <span className="text-sm font-semibold truncate" style={{ color: "var(--text-1)" }}>{s.sector}</span>
            <span className="text-xs shrink-0 ml-2" style={{ color: "var(--text-3)" }}>{s.stock_count} stocks</span>
          </div>
          {/* Stacked verdict bar */}
          <StackedBar counts={s.verdict_counts} />
          {/* Verdict legend row */}
          {total > 0 && (
            <div className="flex items-center gap-3 mt-1.5">
              {VERDICTS.filter(v => (s.verdict_counts?.[v] || 0) > 0).map(v => (
                <span key={v} className="text-[10px] flex items-center gap-0.5" style={{ color: V_COLORS[v] }}>
                  <span className="inline-block w-2 h-2 rounded-sm" style={{ background: V_COLORS[v] }} />
                  {s.verdict_counts[v]}
                </span>
              ))}
            </div>
          )}
          {/* Best / worst stocks */}
          <div className="flex items-center justify-between mt-2 text-xs border-t pt-2"
            style={{ borderColor: "var(--line)" }}>
            <Link to={`/stock/${s.best_stock.symbol_code}`}
              className="flex items-center gap-1 hover:underline"
              style={{ color: "var(--teal)" }}>
              <TrendingUp size={10} />
              {s.best_stock.symbol_code}
              <span style={{ color: "var(--text-3)" }}>{Math.round(s.best_stock.score)}</span>
            </Link>
            <Link to={`/stock/${s.worst_stock.symbol_code}`}
              className="flex items-center gap-1 hover:underline"
              style={{ color: "var(--rose)" }}>
              <TrendingDown size={10} />
              {s.worst_stock.symbol_code}
              <span style={{ color: "var(--text-3)" }}>{Math.round(s.worst_stock.score)}</span>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function SectorStrengthChart() {
  const [sectors, setSectors] = useState(null);
  const [loading, setLoading]  = useState(true);

  useEffect(() => {
    getSectorSummary()
      .then(d => setSectors(d.sectors || []))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="rounded-2xl border p-5" style={{ background: "var(--surface)", borderColor: "var(--line)" }}>
      <SectionLabel>Sector Strength</SectionLabel>
      <p className="text-xs -mt-3 mb-3" style={{ color: "var(--text-3)" }}>
        Sector index score · Strong Buy / Buy / Watchlist / Avoid breakdown · Best & worst stock
      </p>
      {/* Legend */}
      <div className="flex items-center gap-4 mb-3">
        {VERDICTS.map(v => (
          <span key={v} className="flex items-center gap-1 text-[10px]" style={{ color: "var(--text-3)" }}>
            <span className="inline-block w-2 h-2 rounded-sm" style={{ background: V_COLORS[v] }} /> {v}
          </span>
        ))}
      </div>
      <div className="flex flex-col gap-2 max-h-[500px] overflow-y-auto pr-1"
        style={{ scrollbarWidth: "thin" }}>
        {loading && (
          <div className="text-sm text-center py-8" style={{ color: "var(--text-3)" }}>Loading sector data…</div>
        )}
        {!loading && (!sectors || sectors.length === 0) && (
          <div className="text-sm text-center py-8" style={{ color: "var(--text-3)" }}>
            No sector data yet — analyse some stocks first.
          </div>
        )}
        {!loading && sectors && sectors.map(s => <SectorRow key={s.sector} s={s} />)}
      </div>
    </div>
  );
}