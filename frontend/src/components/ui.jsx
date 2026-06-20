import { useState } from "react";
import { CheckCircle2, AlertTriangle, ShieldAlert, Info } from "lucide-react";

export function Card({ title, subtitle, right, children, className = "", accent, padding = true }) {
  return (
    <div
      className={`rounded-2xl border ${className}`}
      style={{ background: "var(--surface)", borderColor: "var(--line)", boxShadow: "var(--shadow-sm)" }}
    >
      {(title || right) && (
        <div
          className="flex items-start justify-between gap-3 px-5 py-3.5 border-b"
          style={{ borderColor: "var(--line)", background: "var(--surface-2)", borderRadius: "16px 16px 0 0" }}
        >
          <div>
            {title && (
              <h3 className="font-display font-semibold text-sm" style={{ color: "var(--text-1)" }}>
                {title}
              </h3>
            )}
            {subtitle && <p className="text-xs mt-0.5" style={{ color: "var(--text-3)" }}>{subtitle}</p>}
          </div>
          {right}
        </div>
      )}
      <div className={padding ? "p-5" : ""}>{children}</div>
    </div>
  );
}

export function Tabs({ tabs, active, onChange }) {
  return (
    <div
      className="flex items-center gap-1 rounded-xl border p-1 w-fit overflow-x-auto"
      style={{ background: "var(--surface-2)", borderColor: "var(--line)" }}
    >
      {tabs.map(t => (
        <button
          key={t.key}
          onClick={() => onChange(t.key)}
          className="px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-all"
          style={{
            background: active === t.key ? "var(--surface)" : "transparent",
            color: active === t.key ? "var(--gold)" : "var(--text-2)",
            border: active === t.key ? `1px solid var(--gold-dim)` : "1px solid transparent",
            boxShadow: active === t.key ? "var(--shadow-sm)" : "none",
          }}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function BulletList({ items, icon = "dot", emptyText = "—" }) {
  if (!items || items.length === 0) return (
    <p className="text-sm" style={{ color: "var(--text-3)" }}>{emptyText}</p>
  );
  const iconMap = { check: CheckCircle2, warn: AlertTriangle, risk: ShieldAlert, info: Info };
  const colorMap = { check: "var(--teal)", warn: "var(--amber)", risk: "var(--rose)", info: "var(--blue)", dot: "var(--text-3)" };
  const Icon  = iconMap[icon];
  const color = colorMap[icon] || "var(--text-3)";

  return (
    <ul className="space-y-2.5">
      {items.map((item, i) => (
        <li key={i} className="flex items-start gap-2.5 text-sm leading-relaxed" style={{ color: "var(--text-2)" }}>
          {Icon
            ? <Icon size={14} className="shrink-0 mt-0.5" style={{ color }} />
            : <span className="mt-2 h-1.5 w-1.5 rounded-full shrink-0" style={{ background: "var(--gold)", opacity: 0.7 }} />}
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

export function StatItem({ label, value, valueColor }) {
  return (
    <div
      className="rounded-xl px-3 py-2.5 border"
      style={{ background: "var(--surface-2)", borderColor: "var(--line)" }}
    >
      <div className="text-[10px] uppercase tracking-wider mb-1" style={{ color: "var(--text-3)" }}>{label}</div>
      <div className="font-mono text-sm font-semibold" style={{ color: valueColor || "var(--text-1)" }}>
        {value ?? "—"}
      </div>
    </div>
  );
}

export function Pill({ children, tone = "neutral" }) {
  const styles = {
    neutral: { background: "var(--surface-2)", color: "var(--text-2)", borderColor: "var(--line)" },
    signal:  { background: "var(--teal-dim)",  color: "var(--teal)",   borderColor: "rgba(15,217,160,0.3)" },
    amber:   { background: "var(--amber-dim)", color: "var(--amber)",  borderColor: "rgba(245,158,11,0.3)" },
    rose:    { background: "var(--rose-dim)",  color: "var(--rose)",   borderColor: "rgba(240,82,112,0.3)" },
    gold:    { background: "var(--gold-dim)",  color: "var(--gold)",   borderColor: "rgba(240,180,41,0.3)" },
    blue:    { background: "var(--blue-dim)",  color: "var(--blue)",   borderColor: "rgba(78,142,247,0.3)" },
    violet:  { background: "var(--violet-dim)",color: "var(--violet)", borderColor: "rgba(167,139,250,0.3)" },
  };
  return (
    <span
      className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium"
      style={styles[tone] || styles.neutral}
    >
      {children}
    </span>
  );
}

export function AIBadge({ available = false }) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[10px] font-semibold tracking-wide uppercase"
      style={available
        ? { background: "var(--violet-dim)", color: "var(--violet)", borderColor: "rgba(167,139,250,0.3)" }
        : { background: "var(--surface-2)", color: "var(--text-3)", borderColor: "var(--line)" }
      }
    >
      <span style={{ fontSize: 8 }}>✦</span>
      {available ? "AI Insights Active" : "AI Insights"}
    </span>
  );
}

export function SectionLabel({ children, action }) {
  return (
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-2">
        <span className="h-4 w-0.5 rounded-full" style={{ background: "var(--gold)" }} />
        <h2 className="font-display font-bold text-base" style={{ color: "var(--text-1)" }}>{children}</h2>
      </div>
      {action}
    </div>
  );
}

export function useTabState(defaultKey) {
  return useState(defaultKey);
}