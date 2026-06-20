import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, Printer } from "lucide-react";
import { getDashboard, listStocks } from "../lib/api";
import MarketOverviewCard from "../components/MarketOverviewCard";
import ConvictionMeter from "../components/ConvictionMeter";
import VerdictBadge from "../components/VerdictBadge";
import PriceLevelLadder from "../components/PriceLevelLadder";
import { BulletList, Pill, StatItem } from "../components/ui";
import { fmtPct, fmtPrice, fmtScore } from "../lib/format";

export default function FullReport() {
  const [dashboard, setDashboard] = useState(null);
  const [allStocks, setAllStocks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sortKey, setSortKey] = useState("overall_score");
  const [sortDir, setSortDir] = useState("desc");

  useEffect(() => {
    (async () => {
      setLoading(true);
      const [dash, stocks] = await Promise.all([getDashboard(5), listStocks({ limit: 2000 })]);
      setDashboard(dash);
      setAllStocks(stocks.items || []);
      setLoading(false);
    })();
  }, []);

  const analyzed = allStocks.filter((s) => s.overall_score !== null && s.overall_score !== undefined);
  const sorted = [...analyzed].sort((a, b) => {
    const av = a[sortKey] ?? -Infinity;
    const bv = b[sortKey] ?? -Infinity;
    return sortDir === "asc" ? av - bv : bv - av;
  });

  const toggleSort = (key) => {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  if (loading) {
    return <div className="py-24 text-center text-faint">Loading report…</div>;
  }

  return (
    <div className="flex flex-col gap-6 print:text-black">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-display text-xl font-semibold text-paper">Stock Screening &amp; Swing Trade Report</h1>
          <p className="text-sm text-faint mt-0.5">
            {analyzed.length} of {allStocks.length} stocks analyzed · generated {new Date().toLocaleString("en-IN")}
          </p>
        </div>
        <button
          onClick={() => window.print()}
          className="flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-sm text-mute hover:text-paper transition-colors print:hidden"
        >
          <Printer size={14} /> Print / Save PDF
        </button>
      </div>

      {/* ---- Executive Summary --------------------------------------- */}
      <section>
        <h2 className="font-display font-semibold text-paper text-lg mb-3">1. Executive Summary</h2>
        <MarketOverviewCard overview={dashboard?.market_overview} onRefresh={() => {}} refreshing={false} />
      </section>

      {/* ---- Top Recommendations -------------------------------------- */}
      <section>
        <h2 className="font-display font-semibold text-paper text-lg mb-1">2. Top Recommendations</h2>
        <p className="text-sm text-faint mb-4">
          Ranked by overall conviction score. Only stocks scoring 65+ with risk-reward ≥ 2:1 and no unresolved
          fundamental red flags are surfaced here — per capital-preservation rules, this list may be short.
        </p>

        {dashboard?.top_picks?.length ? (
          <div className="flex flex-col gap-5">
            {dashboard.top_picks.map((r, i) => (
              <RecommendationBlock key={r.id} rank={i + 1} report={r} />
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-line bg-surface p-6 text-center text-sm text-faint">
            No qualifying recommendations yet — analyze stocks from the dashboard first.
          </div>
        )}
      </section>

      {/* ---- Summary Table of Top Picks -------------------------------- */}
      {dashboard?.top_picks?.length > 0 && (
        <section>
          <h2 className="font-display font-semibold text-paper text-lg mb-3">3. Summary Table — Top Recommendations</h2>
          <div className="rounded-xl border border-line bg-surface overflow-x-auto scrollbar-thin">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line bg-surface-2/60 text-left text-xs uppercase tracking-wider text-faint">
                  <th className="px-3 py-2.5">Rank</th>
                  <th className="px-3 py-2.5">Stock</th>
                  <th className="px-3 py-2.5">Score</th>
                  <th className="px-3 py-2.5">Confidence</th>
                  <th className="px-3 py-2.5">Sector</th>
                  <th className="px-3 py-2.5">Entry Zone</th>
                  <th className="px-3 py-2.5">Breakout</th>
                  <th className="px-3 py-2.5">Stop Loss</th>
                  <th className="px-3 py-2.5">Target 2</th>
                  <th className="px-3 py-2.5">Exp. Return</th>
                  <th className="px-3 py-2.5">Profit Prob.</th>
                </tr>
              </thead>
              <tbody>
                {dashboard.top_picks.map((r, i) => {
                  const setup = r.swing_view?.trade_setup || {};
                  return (
                    <tr key={r.id} className="border-b border-line/60 last:border-b-0">
                      <td className="px-3 py-2.5 font-mono text-paper">{i + 1}</td>
                      <td className="px-3 py-2.5">
                        <Link to={`/stock/${r.symbol_code}`} className="font-mono text-paper hover:text-steel">{r.symbol_code}</Link>
                        <div className="text-xs text-faint">{r.symbol_name}</div>
                      </td>
                      <td className="px-3 py-2.5 font-mono text-paper">{fmtScore(r.overall_score)}/100</td>
                      <td className="px-3 py-2.5 text-mute">{r.confidence}</td>
                      <td className="px-3 py-2.5 text-mute">{r.sector_detail?.sector_name || "—"}</td>
                      <td className="px-3 py-2.5 font-mono text-mute">{fmtPrice(setup.entry_zone_low)}–{fmtPrice(setup.entry_zone_high)}</td>
                      <td className="px-3 py-2.5 font-mono text-amber">{fmtPrice(setup.breakout_trigger)}</td>
                      <td className="px-3 py-2.5 font-mono text-rose">{fmtPrice(setup.stop_loss)}</td>
                      <td className="px-3 py-2.5 font-mono text-signal">{fmtPrice(setup.target2)}</td>
                      <td className="px-3 py-2.5 font-mono text-signal">{fmtPct(setup.expected_return_pct)}</td>
                      <td className="px-3 py-2.5 font-mono text-paper">{r.probability_3_6m}%</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* ---- Full Screening Table -------------------------------------- */}
      <section>
        <h2 className="font-display font-semibold text-paper text-lg mb-1">4. Full Screening Table</h2>
        <p className="text-sm text-faint mb-3">
          All analyzed stocks. Final Score = 25% Fundamental + 40% Technical + 20% Sector + 15% Momentum. Click a column to sort.
        </p>
        <div className="rounded-xl border border-line bg-surface overflow-x-auto scrollbar-thin">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line bg-surface-2/60 text-left text-xs uppercase tracking-wider text-faint">
                <th className="px-3 py-2.5">Stock</th>
                <th className="px-3 py-2.5">Sector</th>
                {[
                  ["fundamental_score", "Fundamental"],
                  ["technical_score", "Technical"],
                  ["sector_score", "Sector"],
                  ["momentum_score", "Momentum"],
                  ["overall_score", "Final"],
                ].map(([key, label]) => (
                  <th key={key} className="px-3 py-2.5 cursor-pointer hover:text-paper" onClick={() => toggleSort(key)}>
                    {label} {sortKey === key && (sortDir === "asc" ? "↑" : "↓")}
                  </th>
                ))}
                <th className="px-3 py-2.5">Verdict</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((s) => (
                <tr key={s.id} className="border-b border-line/60 last:border-b-0 hover:bg-surface-2/40">
                  <td className="px-3 py-2.5">
                    <Link to={`/stock/${s.symbol_code}`} className="font-mono text-paper hover:text-steel">{s.symbol_code}</Link>
                    <div className="text-xs text-faint truncate max-w-[160px]">{s.symbol_name}</div>
                  </td>
                  <td className="px-3 py-2.5 text-mute">{s.sector || "—"}</td>
                  <td className="px-3 py-2.5 font-mono">{fmtScore(s.fundamental_score)}</td>
                  <td className="px-3 py-2.5 font-mono">{fmtScore(s.technical_score)}</td>
                  <td className="px-3 py-2.5 font-mono">{fmtScore(s.sector_score)}</td>
                  <td className="px-3 py-2.5 font-mono">{fmtScore(s.momentum_score)}</td>
                  <td className="px-3 py-2.5 font-mono text-paper font-medium">{fmtScore(s.overall_score)}</td>
                  <td className="px-3 py-2.5"><VerdictBadge verdict={s.verdict} /></td>
                </tr>
              ))}
              {sorted.length === 0 && (
                <tr><td colSpan={8} className="px-3 py-8 text-center text-faint">No stocks analyzed yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
        {allStocks.length - analyzed.length > 0 && (
          <p className="text-xs text-faint mt-2">
            {allStocks.length - analyzed.length} stock(s) not yet analyzed — run "Analyze All" from the dashboard to include them here.
          </p>
        )}
      </section>
    </div>
  );
}

function RecommendationBlock({ rank, report }) {
  const swing = report.swing_view || {};
  const setup = swing.trade_setup || {};
  const sector = report.sector_detail || {};

  return (
    <div className="rounded-xl border border-line bg-surface p-5">
      <div className="flex items-start justify-between gap-3 flex-wrap mb-3">
        <div className="flex items-center gap-3">
          <span className="font-mono text-faint text-sm">#{rank}</span>
          <div>
            <Link to={`/stock/${report.symbol_code}`} className="font-mono text-lg text-paper hover:text-steel inline-flex items-center gap-1.5">
              {report.symbol_code} <ArrowUpRight size={14} />
            </Link>
            <div className="text-xs text-faint">{report.symbol_name}</div>
          </div>
          <VerdictBadge verdict={report.verdict} size="lg" />
        </div>
        <div className="text-right text-xs text-faint">
          <div>Confidence: <span className="text-paper">{report.confidence}</span></div>
          <div>3–6M Profit Probability: <span className="text-paper font-mono">{report.probability_3_6m}%</span></div>
        </div>
      </div>

      <ConvictionMeter
        scores={{
          overall: report.overall_score,
          fundamental: report.fundamental_score,
          technical: report.technical_score,
          sector: report.sector_score,
          momentum: report.momentum_score,
        }}
        className="mb-4"
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2">
          <PriceLevelLadder setup={setup} technical={report.technical_detail} />
          <div className="grid grid-cols-3 sm:grid-cols-4 gap-4">
            <StatItem label="Entry Zone" value={`${fmtPrice(setup.entry_zone_low)}–${fmtPrice(setup.entry_zone_high)}`} />
            <StatItem label="Breakout" value={fmtPrice(setup.breakout_trigger)} valueClassName="text-amber" />
            <StatItem label="Stop Loss" value={fmtPrice(setup.stop_loss)} valueClassName="text-rose" />
            <StatItem label="R:R" value={setup.risk_reward_ratio ? `${setup.risk_reward_ratio}:1` : "—"} />
            <StatItem label="Target 1" value={fmtPrice(setup.target1)} valueClassName="text-signal" />
            <StatItem label="Target 2" value={fmtPrice(setup.target2)} valueClassName="text-signal" />
            <StatItem label="Target 3" value={fmtPrice(setup.target3)} valueClassName="text-signal" />
            <StatItem label="Exp. Return" value={fmtPct(setup.expected_return_pct)} valueClassName="text-signal" />
          </div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wider text-faint mb-1.5">Sector</div>
          <div className="flex items-center gap-2 mb-2">
            <span className="font-display text-paper text-sm font-medium">{sector.sector_name || "—"}</span>
            {sector.sector_trend && <Pill tone={sector.sector_trend === "Bullish" ? "signal" : sector.sector_trend === "Bearish" ? "rose" : "amber"}>{sector.sector_trend}</Pill>}
          </div>
          <p className="text-sm text-mute leading-relaxed">{sector.sector_outlook}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 mt-4 pt-4 border-t border-line">
        <div>
          <div className="text-[10px] uppercase tracking-wider text-signal mb-1.5">Why It Was Selected</div>
          <BulletList items={swing.why_recommended} icon="check" />
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wider text-rose mb-1.5">Risk Factors</div>
          <BulletList items={report.risk_factors} icon="risk" />
        </div>
      </div>
    </div>
  );
}
