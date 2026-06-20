import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowDown, ArrowUp, ArrowUpDown, Loader2, Sparkles } from "lucide-react";
import VerdictBadge from "./VerdictBadge";
import ConvictionMeter from "./ConvictionMeter";
import { changeColor, fmtNum, fmtPct, fmtPrice, timeAgo } from "../lib/format";

const COLS = [
  { key: "symbol_code", label: "Symbol",   sortable: true },
  { key: "symbol_name", label: "Company",  sortable: true },
  { key: "sector",      label: "Sector",   sortable: true },
  { key: "last_price",  label: "Price",    sortable: true, align: "right" },
  { key: "change_pct",  label: "Chg %",   sortable: true, align: "right" },
  { key: "overall_score", label: "Score", sortable: true },
  { key: "verdict",     label: "Signal",   sortable: true },
  { key: "report_age_minutes", label: "Analyzed", sortable: true },
  { key: "actions",    label: "",          sortable: false },
];

export default function StockTable({ items, selected, onToggleSelect, onToggleSelectAll, onAnalyzeOne, analyzingSet }) {
  const [sortKey, setSortKey] = useState("overall_score");
  const [sortDir, setSortDir] = useState("desc");

  const sorted = useMemo(() => {
    return [...items].sort((a, b) => {
      let av = a[sortKey], bv = b[sortKey];
      if (av == null) av = sortDir === "asc" ? Infinity : -Infinity;
      if (bv == null) bv = sortDir === "asc" ? Infinity : -Infinity;
      if (typeof av === "string") return sortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
      return sortDir === "asc" ? av - bv : bv - av;
    });
  }, [items, sortKey, sortDir]);

  const toggleSort = k => {
    if (sortKey === k) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortKey(k); setSortDir("desc"); }
  };

  const allSelected = items.length > 0 && items.every(i => selected.has(i.symbol_code));

  return (
    <div className="rounded-2xl border overflow-hidden" style={{ background: "var(--surface)", borderColor: "var(--line)" }}>
      <div className="overflow-x-auto" style={{ scrollbarWidth: "thin" }}>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b" style={{ background: "var(--surface-2)", borderColor: "var(--line)" }}>
              <th className="px-4 py-3 w-10">
                <input type="checkbox" checked={allSelected} onChange={e => onToggleSelectAll(e.target.checked)}
                  className="rounded" style={{ accentColor: "var(--gold)" }} />
              </th>
              {COLS.map(col => (
                <th key={col.key}
                  onClick={() => col.sortable && toggleSort(col.key)}
                  className={`px-3 py-3 text-xs font-display uppercase tracking-wider select-none whitespace-nowrap ${col.align === "right" ? "text-right" : "text-left"} ${col.sortable ? "cursor-pointer" : ""}`}
                  style={{ color: sortKey === col.key ? "var(--gold)" : "var(--text-3)" }}
                >
                  <span className="inline-flex items-center gap-1">
                    {col.label}
                    {col.sortable && (sortKey === col.key
                      ? sortDir === "asc" ? <ArrowUp size={10} style={{ color: "var(--gold)" }} /> : <ArrowDown size={10} style={{ color: "var(--gold)" }} />
                      : <ArrowUpDown size={10} style={{ opacity: 0.3 }} />
                    )}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((s, idx) => {
              const isAnalyzing = analyzingSet.has(s.symbol_code);
              return (
                <tr key={s.id}
                  className="border-b transition-colors last:border-b-0"
                  style={{
                    borderColor: "var(--line)",
                    background: idx % 2 === 0 ? "transparent" : "var(--surface-2)",
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = "var(--surface-3)"}
                  onMouseLeave={e => e.currentTarget.style.background = idx % 2 === 0 ? "transparent" : "var(--surface-2)"}
                >
                  <td className="px-4 py-2.5">
                    <input type="checkbox" checked={selected.has(s.symbol_code)} onChange={() => onToggleSelect(s.symbol_code)}
                      className="rounded" style={{ accentColor: "var(--gold)" }} />
                  </td>
                  <td className="px-3 py-2.5">
                    <Link to={`/stock/${s.symbol_code}`} className="font-mono text-sm font-bold transition-colors"
                      style={{ color: "var(--text-1)" }}
                      onMouseEnter={e => e.currentTarget.style.color = "var(--gold)"}
                      onMouseLeave={e => e.currentTarget.style.color = "var(--text-1)"}
                    >{s.symbol_code}</Link>
                    {s.exchange && (
                      <span className="ml-1.5 text-[10px] border rounded px-1 py-0.5"
                        style={{ color: "var(--text-3)", borderColor: "var(--line)" }}>{s.exchange}</span>
                    )}
                  </td>
                  <td className="px-3 py-2.5">
                    <Link to={`/stock/${s.symbol_code}`} className="text-xs truncate block max-w-[200px]"
                      style={{ color: "var(--text-2)" }}>{s.symbol_name}</Link>
                    {s.industry && <div className="text-[10px] truncate max-w-[200px]" style={{ color: "var(--text-3)" }}>{s.industry}</div>}
                  </td>
                  <td className="px-3 py-2.5">
                    <span className="text-xs" style={{ color: "var(--text-3)" }}>{s.sector || "—"}</span>
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-sm font-semibold" style={{ color: "var(--text-1)" }}>
                    {fmtPrice(s.last_price)}
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-sm"
                    style={{ color: s.change_pct >= 0 ? "var(--teal)" : "var(--rose)" }}>
                    {fmtPct(s.change_pct)}
                  </td>
                  <td className="px-3 py-2.5 min-w-[140px]">
                    <ConvictionMeter scores={{ overall: s.overall_score }} size="compact" />
                  </td>
                  <td className="px-3 py-2.5"><VerdictBadge verdict={s.verdict} /></td>
                  <td className="px-3 py-2.5 text-xs whitespace-nowrap" style={{ color: "var(--text-3)" }}>
                    {s.report_age_minutes != null ? timeAgo(new Date(Date.now() - s.report_age_minutes * 60000).toISOString()) : "Never"}
                  </td>
                  <td className="px-3 py-2.5">
                    <button onClick={() => onAnalyzeOne(s.symbol_code)} disabled={isAnalyzing}
                      className="inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-all disabled:opacity-50 disabled:cursor-wait whitespace-nowrap"
                      style={{ borderColor: "var(--line)", color: "var(--text-2)", background: "transparent" }}
                      onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--gold)"; e.currentTarget.style.color = "var(--gold)"; e.currentTarget.style.background = "var(--gold-dim)"; }}
                      onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--line)"; e.currentTarget.style.color = "var(--text-2)"; e.currentTarget.style.background = "transparent"; }}
                    >
                      {isAnalyzing ? <Loader2 size={11} className="animate-spin" /> : <Sparkles size={11} />}
                      {isAnalyzing ? "Scanning…" : "Analyse"}
                    </button>
                  </td>
                </tr>
              );
            })}
            {!sorted.length && (
              <tr><td colSpan={COLS.length + 1} className="px-4 py-12 text-center text-sm" style={{ color: "var(--text-3)" }}>
                No stocks match your filters.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="px-4 py-2.5 text-xs flex items-center justify-between border-t"
        style={{ borderColor: "var(--line)", background: "var(--surface-2)", color: "var(--text-3)" }}>
        <span>{fmtNum(sorted.length)} stocks</span>
        <span>Click column headers to sort</span>
      </div>
    </div>
  );
}