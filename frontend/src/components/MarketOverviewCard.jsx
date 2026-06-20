import { RefreshCw, TrendingDown, TrendingUp, AlertTriangle, Lightbulb, Sparkles, Lock } from "lucide-react";
import { AIBadge } from "./ui";

export default function MarketOverviewCard({ overview, onRefresh, refreshing }) {
  const hasRealData = overview?.market_view && !overview.market_view.includes("unavailable");

  return (
    <div className="rounded-2xl border overflow-hidden" style={{ background: "var(--surface)", borderColor: "var(--line)", boxShadow: "var(--shadow-sm)" }}>
      <div className="px-5 py-4 flex items-start justify-between gap-3 border-b" style={{ background: "var(--surface-2)", borderColor: "var(--line)" }}>
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl flex items-center justify-center" style={{ background: "var(--violet-dim)", border: "1px solid rgba(167,139,250,0.3)" }}>
            <Sparkles size={16} style={{ color: "var(--violet)" }} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-display font-bold text-sm" style={{ color: "var(--text-1)" }}>AI Market Intelligence</h2>
              <AIBadge available={hasRealData} />
            </div>
            <p className="text-xs mt-0.5" style={{ color: "var(--text-3)" }}>
              {hasRealData && overview?.generated_at
                ? `Updated ${new Date(overview.generated_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}`
                : "Powered by Claude AI with live web research"}
            </p>
          </div>
        </div>
        <button
          onClick={onRefresh}
          disabled={refreshing}
          className="flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-all disabled:opacity-60"
          style={{ borderColor: "var(--line)", color: "var(--text-2)", background: "var(--surface)" }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--gold)"; e.currentTarget.style.color = "var(--gold)"; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--line)"; e.currentTarget.style.color = "var(--text-2)"; }}
        >
          <RefreshCw size={12} className={refreshing ? "animate-spin" : ""} />
          {refreshing ? "Researching markets…" : "Refresh Insights"}
        </button>
      </div>

      <div className="p-5">
        {!hasRealData ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <div className="h-12 w-12 rounded-2xl flex items-center justify-center mb-3" style={{ background: "var(--violet-dim)", border: "1px solid rgba(167,139,250,0.2)" }}>
              <Lock size={20} style={{ color: "var(--violet)" }} />
            </div>
            <p className="font-display font-semibold text-sm mb-1" style={{ color: "var(--text-1)" }}>AI Insights Not Available</p>
            <p className="text-xs max-w-sm" style={{ color: "var(--text-3)" }}>
              Connect your AI credits to unlock live market intelligence — sector rotation analysis, institutional flow signals, macro outlook and more.
            </p>
            <button
              onClick={onRefresh}
              disabled={refreshing}
              className="mt-4 flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium"
              style={{ background: "var(--violet-dim)", color: "var(--violet)", border: "1px solid rgba(167,139,250,0.3)" }}
            >
              <Sparkles size={14} />
              {refreshing ? "Connecting…" : "Try AI Insights"}
            </button>
          </div>
        ) : (
          <>
            <p className="text-sm leading-relaxed mb-5" style={{ color: "var(--text-2)" }}>{overview.market_view}</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {[
                { key: "favoured_sectors", label: "Favoured Sectors",   icon: TrendingUp,    color: "var(--teal)",  bg: "var(--teal-dim)",  border: "rgba(15,217,160,0.2)" },
                { key: "avoid_sectors",    label: "Sectors to Avoid",   icon: TrendingDown,  color: "var(--rose)",  bg: "var(--rose-dim)",  border: "rgba(240,82,112,0.2)" },
                { key: "key_risks",        label: "Key Market Risks",   icon: AlertTriangle, color: "var(--amber)", bg: "var(--amber-dim)", border: "rgba(245,158,11,0.2)" },
                { key: "key_opportunities",label: "Key Opportunities",  icon: Lightbulb,     color: "var(--blue)",  bg: "var(--blue-dim)",  border: "rgba(78,142,247,0.2)" },
              ].map(({ key, label, icon: Icon, color, bg, border }) => (
                <div key={key} className="rounded-xl p-4" style={{ background: bg, border: `1px solid ${border}` }}>
                  <div className="flex items-center gap-2 text-xs uppercase tracking-wider font-semibold mb-3" style={{ color }}>
                    <Icon size={13} />{label}
                  </div>
                  <ul className="space-y-1.5">
                    {(overview[key] || []).map((item, i) => (
                      <li key={i} className="text-sm" style={{ color: "var(--text-2)" }}>
                        {typeof item === "object" ? <><span className="font-medium" style={{ color: "var(--text-1)" }}>{item.sector}</span>{item.rationale && <span style={{ color: "var(--text-3)" }}> — {item.rationale}</span>}</> : item}
                      </li>
                    ))}
                    {!(overview[key] || []).length && <li className="text-sm" style={{ color: "var(--text-3)" }}>—</li>}
                  </ul>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}