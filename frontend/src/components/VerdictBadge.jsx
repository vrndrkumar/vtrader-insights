export default function VerdictBadge({ verdict, size = "md" }) {
  if (!verdict) return (
    <span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium badge-neutral">
      Not Analyzed
    </span>
  );
  const cls = verdict === "Strong Buy" || verdict === "Buy" ? "badge-buy"
    : verdict === "Watchlist" ? "badge-watchlist"
    : verdict === "Avoid" ? "badge-avoid"
    : "badge-neutral";
  const sz = size === "lg" ? "px-3.5 py-1 text-sm" : "px-2.5 py-0.5 text-xs";
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border font-display font-semibold tracking-wide ${cls} ${sz}`}>
      {verdict === "Strong Buy" && <span className="text-[10px]">★</span>}
      {verdict}
    </span>
  );
}