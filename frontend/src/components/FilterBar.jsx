import { useEffect, useState } from "react";
import { listSectors, listIndustries } from "../lib/api";

const VERDICTS   = ["Strong Buy", "Buy", "Watchlist", "Avoid"];
const CATEGORIES = ["EQUITY", "ETF", "MF"];
const V_COLORS   = {
  "Strong Buy": { color: "var(--teal)",  bg: "var(--teal-dim)",  border: "rgba(15,217,160,0.3)" },
  "Buy":        { color: "var(--teal)",  bg: "var(--teal-dim)",  border: "rgba(15,217,160,0.3)" },
  "Watchlist":  { color: "var(--amber)", bg: "var(--amber-dim)", border: "rgba(245,158,11,0.3)" },
  "Avoid":      { color: "var(--rose)",  bg: "var(--rose-dim)",  border: "rgba(240,82,112,0.3)" },
};
const ss = { background: "var(--surface-2)", color: "var(--text-2)", borderColor: "var(--line)" };

export default function FilterBar({ verdict, setVerdict, exchange, setExchange, sector, setSector, industry, setIndustry, category, setCategory }) {
  const [sectors,    setSectors]    = useState([]);
  const [industries, setIndustries] = useState([]);

  useEffect(() => {
    listSectors().then(setSectors).catch(() => {});
  }, []);

  useEffect(() => {
    setIndustry(null);
    if (sector) listIndustries(sector).then(setIndustries).catch(() => {});
    else listIndustries().then(setIndustries).catch(() => {});
  }, [sector]);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs font-display font-semibold uppercase tracking-wider" style={{ color: "var(--text-3)" }}>Filter</span>

      {/* Verdict pills */}
      <div className="flex items-center gap-1 rounded-xl border p-1" style={{ background: "var(--surface-2)", borderColor: "var(--line)" }}>
        <button onClick={() => setVerdict(null)}
          className="px-3 py-1 rounded-lg text-xs font-medium transition-all"
          style={{ background: !verdict ? "var(--surface)" : "transparent", color: !verdict ? "var(--gold)" : "var(--text-2)", border: !verdict ? "1px solid var(--gold-dim)" : "1px solid transparent" }}>
          All
        </button>
        {VERDICTS.map(v => {
          const c = V_COLORS[v]; const active = verdict === v;
          return (
            <button key={v} onClick={() => setVerdict(active ? null : v)}
              className="px-3 py-1 rounded-lg text-xs font-medium transition-all"
              style={{ background: active ? c.bg : "transparent", color: active ? c.color : "var(--text-2)", border: active ? `1px solid ${c.border}` : "1px solid transparent" }}>
              {v}
            </button>
          );
        })}
      </div>

      {/* Sector */}
      <select value={sector || ""} onChange={e => setSector(e.target.value || null)}
        className="rounded-xl border px-3 py-1.5 text-xs outline-none" style={ss}>
        <option value="">All Sectors</option>
        {sectors.map(s => <option key={s} value={s}>{s}</option>)}
      </select>

      {/* Industry — only shown when sector selected */}
      {industries.length > 0 && (
        <select value={industry || ""} onChange={e => setIndustry(e.target.value || null)}
          className="rounded-xl border px-3 py-1.5 text-xs outline-none max-w-[180px]" style={ss}>
          <option value="">All Industries</option>
          {industries.map(i => <option key={i} value={i}>{i}</option>)}
        </select>
      )}

      {/* Exchange */}
      <select value={exchange || ""} onChange={e => setExchange(e.target.value || null)}
        className="rounded-xl border px-3 py-1.5 text-xs outline-none" style={ss}>
        <option value="">NSE + BSE</option>
        <option value="NSE">NSE</option>
        <option value="BSE">BSE</option>
      </select>

      {/* Category */}
      <select value={category || ""} onChange={e => setCategory(e.target.value || null)}
        className="rounded-xl border px-3 py-1.5 text-xs outline-none" style={ss}>
        <option value="">Equity Only</option>
        <option value="ALL">All Categories</option>
        {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
      </select>
    </div>
  );
}