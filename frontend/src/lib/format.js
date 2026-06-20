export function fmtPrice(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `₹${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2, minimumFractionDigits: 2 })}`;
}

export function fmtPct(v, opts = {}) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${Number(v).toFixed(opts.digits ?? 1)}%`;
}

export function fmtNum(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return Number(v).toLocaleString("en-IN");
}

export function fmtScore(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return Math.round(v);
}

export function timeAgo(dateStr) {
  if (!dateStr) return "Never analyzed";
  const then = new Date(dateStr);
  const diffMs = Date.now() - then.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

// Verdict -> token color name (matches index.css theme)
export const VERDICT_COLORS = {
  "Strong Buy": "signal",
  Buy: "signal",
  Watchlist: "amber",
  Avoid: "rose",
  Unknown: "mute",
};

export function changeColor(v) {
  if (v === null || v === undefined) return "text-mute";
  return v >= 0 ? "text-signal" : "text-rose";
}
