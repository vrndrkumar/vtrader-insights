import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, X } from "lucide-react";
import { listStocks } from "../lib/api";
import VerdictBadge from "./VerdictBadge";

export default function SearchBar({ className = "" }) {
  const [q, setQ]         = useState("");
  const [results, setR]   = useState([]);
  const [open, setOpen]   = useState(false);
  const [loading, setL]   = useState(false);
  const ref               = useRef(null);
  const navigate          = useNavigate();

  useEffect(() => {
    if (!q.trim()) { setR([]); return; }
    setL(true);
    const t = setTimeout(async () => {
      try { const d = await listStocks({ q, limit: 8 }); setR(d.items || []); setOpen(true); }
      finally { setL(false); }
    }, 250);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    const fn = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", fn);
    return () => document.removeEventListener("mousedown", fn);
  }, []);

  const go = code => { setOpen(false); setQ(""); navigate(`/stock/${code}`); };

  return (
    <div ref={ref} className={`relative ${className}`}>
      <div
        className="flex items-center gap-2 rounded-xl border px-3 py-2 transition-all"
        style={{ background: "var(--surface-2)", borderColor: "var(--line)" }}
        onFocus={() => results.length && setOpen(true)}
      >
        <Search size={14} style={{ color: "var(--text-3)" }} className="shrink-0" />
        <input
          value={q}
          onChange={e => setQ(e.target.value)}
          onFocus={() => results.length && setOpen(true)}
          placeholder="Search stocks, symbols…"
          className="w-full bg-transparent text-sm outline-none"
          style={{ color: "var(--text-1)" }}
        />
        {q && <button onClick={() => { setQ(""); setR([]); }} style={{ color: "var(--text-3)" }}><X size={13} /></button>}
      </div>

      {open && (q.trim() || loading) && (
        <div
          className="absolute left-0 right-0 mt-2 rounded-xl border shadow-xl z-50 overflow-hidden"
          style={{ background: "var(--surface)", borderColor: "var(--line)", boxShadow: "var(--shadow-lg)" }}
        >
          {loading && <div className="px-4 py-3 text-xs" style={{ color: "var(--text-3)" }}>Searching…</div>}
          {!loading && !results.length && (
            <div className="px-4 py-3 text-xs" style={{ color: "var(--text-3)" }}>No results for "{q}"</div>
          )}
          {results.map(s => (
            <button key={s.id} onClick={() => go(s.symbol_code)}
              className="w-full flex items-center justify-between gap-3 px-4 py-2.5 text-left border-b transition-colors last:border-b-0"
              style={{ borderColor: "var(--line)" }}
              onMouseEnter={e => e.currentTarget.style.background = "var(--surface-2)"}
              onMouseLeave={e => e.currentTarget.style.background = "transparent"}
            >
              <div className="min-w-0">
                <div className="font-mono text-sm font-semibold" style={{ color: "var(--text-1)" }}>{s.symbol_code}</div>
                <div className="text-xs truncate" style={{ color: "var(--text-3)" }}>{s.symbol_name}</div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {s.exchange && <span className="text-[10px] border rounded px-1.5 py-0.5" style={{ color: "var(--text-3)", borderColor: "var(--line)" }}>{s.exchange}</span>}
                <VerdictBadge verdict={s.verdict} />
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}