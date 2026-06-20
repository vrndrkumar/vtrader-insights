import { fmtPrice } from "../lib/format";
export default function PriceLevelLadder({ setup, technical }) {
  const pts = [
    { key: "stop",     label: "Stop",    value: setup.stop_loss,                              color: "var(--rose)" },
    { key: "entry",    label: "Entry",   value: setup.entry_zone_low,                         color: "var(--blue)" },
    { key: "current",  label: "Current", value: technical?.current_price ?? setup.current_price, color: "var(--text-1)" },
    { key: "breakout", label: "Break",   value: setup.breakout_trigger,                       color: "var(--amber)" },
    { key: "t1",       label: "T1",      value: setup.target1,                                color: "var(--teal)" },
    { key: "t2",       label: "T2",      value: setup.target2,                                color: "var(--teal)" },
    { key: "t3",       label: "T3",      value: setup.target3,                                color: "var(--teal)" },
  ].filter(p => p.value != null);
  if (!pts.length) return null;
  const vals = pts.map(p => p.value);
  const min  = Math.min(...vals) * 0.985;
  const max  = Math.max(...vals) * 1.015;
  const rng  = max - min || 1;
  const pos  = v => ((v - min) / rng) * 100;
  const cp   = technical?.current_price ?? setup.current_price;
  const stop = setup.stop_loss;
  const t2   = setup.target2;

  return (
    <div className="pt-2 pb-10">
      <div className="relative h-1.5 rounded-full" style={{ background: "var(--surface-3)" }}>
        {stop && cp && (
          <div className="absolute h-full rounded-full" style={{
            left: `${pos(stop)}%`, width: `${Math.max(0, pos(cp) - pos(stop))}%`,
            background: "rgba(240,82,112,0.2)"
          }} />
        )}
        {cp && t2 && (
          <div className="absolute h-full rounded-full" style={{
            left: `${pos(cp)}%`, width: `${Math.max(0, pos(t2) - pos(cp))}%`,
            background: "rgba(15,217,160,0.15)"
          }} />
        )}
        {pts.map((p, i) => (
          <div key={p.key} className="absolute top-1/2 -translate-y-1/2" style={{ left: `${pos(p.value)}%` }}>
            <div className="h-3.5 w-1 rounded-full -translate-x-1/2 border" style={{ background: p.color, borderColor: "var(--bg)" }} />
            <div className="absolute -translate-x-1/2 text-center whitespace-nowrap" style={{ top: i % 2 === 0 ? "10px" : "-36px" }}>
              <div className="text-[9px] uppercase tracking-wide" style={{ color: "var(--text-3)" }}>{p.label}</div>
              <div className="font-mono text-xs font-semibold" style={{ color: p.color }}>{fmtPrice(p.value)}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}