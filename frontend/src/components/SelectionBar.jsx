import { Loader2, Sparkles, X } from "lucide-react";
export default function SelectionBar({ count, onClear, onAnalyze, isRunning }) {
  if (!count) return null;
  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 rounded-2xl border px-5 py-3 shadow-2xl"
      style={{ background: "var(--surface)", borderColor: "var(--line)", boxShadow: "var(--shadow-lg), 0 0 0 1px var(--gold-dim)" }}>
      <span className="text-sm" style={{ color: "var(--text-1)" }}>
        <span className="font-mono font-bold" style={{ color: "var(--gold)" }}>{count}</span> stock{count > 1 ? "s" : ""} selected
      </span>
      <button onClick={onAnalyze} disabled={isRunning}
        className="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-bold gradient-gold disabled:opacity-60"
        style={{ color: "var(--bg)" }}>
        {isRunning ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
        Analyse Selected
      </button>
      <button onClick={onClear} style={{ color: "var(--text-3)" }} className="hover:opacity-80"><X size={16} /></button>
    </div>
  );
}