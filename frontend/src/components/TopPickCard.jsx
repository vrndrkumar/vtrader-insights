import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import VerdictBadge from "./VerdictBadge";
import ConvictionMeter from "./ConvictionMeter";
import { fmtPrice, fmtPct, fmtScore } from "../lib/format";

export default function TopPickCard({ report, rank }) {
  const setup  = report.swing_view?.trade_setup || {};
  const sector = report.sector_detail?.sector_name || report.sector;
  const isBuy  = report.verdict === "Strong Buy" || report.verdict === "Buy";

  return (
    <Link
      to={`/stock/${report.symbol_code}`}
      className="group rounded-2xl border flex flex-col gap-4 p-5 card-hover relative overflow-hidden"
      style={{ background: "var(--surface)", borderColor: "var(--line)" }}
    >
      {isBuy && (
        <div className="absolute inset-x-0 top-0 h-0.5"
          style={{ background: "linear-gradient(90deg,transparent,var(--teal),transparent)" }} />
      )}
      {rank && (
        <div className="absolute top-3 right-3 h-6 w-6 rounded-full gradient-gold flex items-center justify-center shadow-sm">
          <span className="text-[10px] font-bold" style={{ color: "var(--bg)" }}>#{rank}</span>
        </div>
      )}

      {/* Header */}
      <div className="pr-8">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-mono text-lg font-bold" style={{ color: "var(--text-1)" }}>{report.symbol_code}</span>
          <VerdictBadge verdict={report.verdict} />
        </div>
        <div className="text-xs mt-0.5 truncate" style={{ color: "var(--text-2)" }}>{report.symbol_name}</div>
        {sector && <div className="text-xs mt-1 font-medium" style={{ color: "var(--gold)" }}>{sector}</div>}
      </div>

      {/* Conviction meter with full breakdown */}
      <ConvictionMeter scores={{
        overall:     report.overall_score,
        fundamental: report.fundamental_score,
        technical:   report.technical_score,
        sector:      report.sector_score,
        momentum:    report.momentum_score,
      }} />

      {/* Score labels row */}
      <div className="grid grid-cols-4 gap-1 -mt-2">
        {[
          { label: "Fund.",  value: report.fundamental_score },
          { label: "Tech.",  value: report.technical_score },
          { label: "Sector", value: report.sector_score },
          { label: "Mom.",   value: report.momentum_score },
        ].map(({ label, value }) => (
          <div key={label} className="text-center rounded-lg py-1.5 border"
            style={{ background: "var(--surface-2)", borderColor: "var(--line)" }}>
            <div className="text-[9px] uppercase tracking-wide" style={{ color: "var(--text-3)" }}>{label}</div>
            <div className="font-mono text-xs font-bold mt-0.5"
              style={{ color: value >= 65 ? "var(--teal)" : value >= 50 ? "var(--gold)" : "var(--rose)" }}>
              {fmtScore(value)}
            </div>
          </div>
        ))}
      </div>

      {/* Trade setup */}
      <div className="grid grid-cols-3 gap-2 rounded-xl p-3"
        style={{ background: "var(--surface-2)" }}>
        {[
          { label: "Entry",  value: fmtPrice(setup.entry_zone_low), color: "var(--text-1)" },
          { label: "Stop",   value: fmtPrice(setup.stop_loss),      color: "var(--rose)" },
          { label: "Target", value: fmtPrice(setup.target2),        color: "var(--teal)" },
        ].map((item, i) => (
          <div key={i} className={`text-center ${i === 1 ? "border-x" : ""}`}
            style={{ borderColor: "var(--line)" }}>
            <div className="text-[10px] uppercase tracking-wide mb-1" style={{ color: "var(--text-3)" }}>{item.label}</div>
            <div className="font-mono text-sm font-semibold" style={{ color: item.color }}>{item.value}</div>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between text-xs border-t pt-3"
        style={{ borderColor: "var(--line)" }}>
        <div className="flex items-center gap-3" style={{ color: "var(--text-2)" }}>
          <span>R:R <span className="font-mono font-semibold" style={{ color: "var(--text-1)" }}>{setup.risk_reward_ratio ?? "—"}:1</span></span>
          <span>Upside <span className="font-mono font-semibold" style={{ color: "var(--teal)" }}>{fmtPct(setup.expected_return_pct)}</span></span>
        </div>
        <span className="flex items-center gap-1 font-medium group-hover:gap-2 transition-all"
          style={{ color: "var(--gold)" }}>
          View Report <ArrowUpRight size={13} />
        </span>
      </div>
    </Link>
  );
}