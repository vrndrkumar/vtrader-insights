import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Loader2, Sparkles, TrendingUp, TrendingDown, Minus, Cpu, Lock } from "lucide-react";
import { analyzeStock, getStock } from "../lib/api";
import ConvictionMeter from "../components/ConvictionMeter";
import VerdictBadge from "../components/VerdictBadge";
import PriceLevelLadder from "../components/PriceLevelLadder";
import { Card, Tabs, BulletList, StatItem, Pill, AIBadge } from "../components/ui";
import { fmtPct, fmtPrice, fmtScore, timeAgo } from "../lib/format";

const TABS = [
  { key: "swing",     label: "Swing Trade (3–6M)" },
  { key: "longterm",  label: "Long-Term View (1–3Y)" },
  { key: "breakdown", label: "Full Breakdown" },
];

export default function StockReport() {
  const { symbolCode } = useParams();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState("swing");

  const load = async () => {
    setLoading(true); setError(null); setNotFound(false);
    try { setReport(await getStock(symbolCode)); }
    catch (e) { if (e?.response?.status === 404) setNotFound(true); else setError(e.message); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [symbolCode]);

  const handleAnalyze = async () => {
    setAnalyzing(true); setError(null);
    try { setReport(await analyzeStock(symbolCode)); setNotFound(false); }
    catch (e) { setError(e?.response?.data?.detail || e.message); }
    finally { setAnalyzing(false); }
  };

  if (loading) return (
    <div className="flex items-center justify-center py-24 gap-2 text-sm" style={{ color: "var(--text-3)" }}>
      <Loader2 className="animate-spin" size={18} /> Loading…
    </div>
  );

  const quote   = report?.raw_quote;
  const tech    = report?.technical_detail;
  const price   = quote?.ltp ?? tech?.current_price;
  const chgPct  = quote?.change_pct;
  const aiReady = report?.fundamental_detail?.rating && report.fundamental_detail.rating !== "Average";

  return (
    <div className="flex flex-col gap-5">
      <Link to="/" className="inline-flex items-center gap-1.5 text-sm w-fit transition-colors"
        style={{ color: "var(--text-3)" }}
        onMouseEnter={e => e.currentTarget.style.color = "var(--gold)"}
        onMouseLeave={e => e.currentTarget.style.color = "var(--text-3)"}>
        <ArrowLeft size={15} /> Back to Dashboard
      </Link>

      {/* Header card */}
      <div className="rounded-2xl border p-5" style={{ background: "var(--surface)", borderColor: "var(--line)" }}>
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-5">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <h1 className="font-mono text-2xl font-bold" style={{ color: "var(--text-1)" }}>{symbolCode}</h1>
              {report?.exchange && (
                <span className="text-xs border rounded px-2 py-0.5 font-semibold"
                  style={{ borderColor: "var(--line)", color: "var(--text-3)" }}>{report.exchange}</span>
              )}
              {report ? <VerdictBadge verdict={report.verdict} size="lg" /> : <VerdictBadge />}
              <AIBadge available={aiReady} />
            </div>
            <p className="text-sm font-medium" style={{ color: "var(--text-2)" }}>{report?.symbol_name || "—"}</p>
            {(report?.sector || report?.industry) && (
              <div className="flex items-center gap-2 mt-1 flex-wrap">
                {report.sector   && <span className="text-xs px-2 py-0.5 rounded-full border" style={{ color: "var(--gold)", borderColor: "var(--gold-dim)", background: "var(--gold-dim)" }}>{report.sector}</span>}
                {report.industry && <span className="text-xs px-2 py-0.5 rounded-full border" style={{ color: "var(--text-3)", borderColor: "var(--line)", background: "var(--surface-2)" }}>{report.industry}</span>}
              </div>
            )}
            {report?.description && (
              <p className="text-xs mt-2 leading-relaxed max-w-lg" style={{ color: "var(--text-3)" }}>{report.description}</p>
            )}

            <div className="flex items-baseline gap-3 mt-3">
              <span className="font-mono text-3xl font-bold" style={{ color: "var(--text-1)" }}>{fmtPrice(price)}</span>
              {chgPct != null && (
                <span className="flex items-center gap-1 font-mono text-sm"
                  style={{ color: chgPct >= 0 ? "var(--teal)" : "var(--rose)" }}>
                  {chgPct > 0 ? <TrendingUp size={14} /> : chgPct < 0 ? <TrendingDown size={14} /> : <Minus size={14} />}
                  {fmtPct(chgPct)}
                </span>
              )}
            </div>

            {report && (
              <div className="flex flex-wrap items-center gap-4 mt-3 text-xs" style={{ color: "var(--text-3)" }}>
                <span>Confidence: <span style={{ color: "var(--text-1)" }}>{report.confidence}</span></span>
                <span>3–6M Probability: <span className="font-mono" style={{ color: "var(--text-1)" }}>{report.probability_3_6m}%</span></span>
                <span>Analysed {timeAgo(report.generated_at)}</span>
              </div>
            )}
          </div>

          <div className="flex flex-col gap-3 w-full md:w-72 shrink-0">
            {report && (
              <>
                <ConvictionMeter scores={{
                  overall: report.overall_score, fundamental: report.fundamental_score,
                  technical: report.technical_score, sector: report.sector_score, momentum: report.momentum_score,
                }} />
                <div className="grid grid-cols-4 gap-1">
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
              </>
            )}
            <button onClick={handleAnalyze} disabled={analyzing}
              className="flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition-all disabled:opacity-70 disabled:cursor-wait"
              style={{ background: "linear-gradient(135deg,var(--gold),var(--gold-2))", color: "var(--bg)" }}>
              {analyzing ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}
              {analyzing ? "Running analysis…" : report ? "Re-analyse Now" : "Analyse Now"}
            </button>
            {analyzing && <p className="text-xs text-center" style={{ color: "var(--text-3)" }}>
              Fetching price history · Computing patterns · AI research — usually 20–60s
            </p>}
          </div>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border px-4 py-3 text-sm" style={{ background: "var(--rose-dim)", borderColor: "rgba(240,82,112,0.3)", color: "var(--rose)" }}>
          {error}
        </div>
      )}

      {notFound && !report && (
        <Card>
          <p className="text-sm" style={{ color: "var(--text-2)" }}>
            Not analysed yet. Click <span style={{ color: "var(--gold)" }}>Analyse Now</span> to generate a full technical, pattern and AI-powered report.
          </p>
        </Card>
      )}

      {report && (
        <>
          <Tabs tabs={TABS} active={tab} onChange={setTab} />
          {tab === "swing"     && <SwingTab     report={report} />}
          {tab === "longterm"  && <LongTermTab  report={report} />}
          {tab === "breakdown" && <BreakdownTab report={report} />}
        </>
      )}
    </div>
  );
}

function SwingTab({ report }) {
  const swing = report.swing_view || {};
  const setup = swing.trade_setup || {};
  const tech  = report.technical_detail || {};

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
      <Card title="Trade Setup" subtitle="Price-action levels from pattern engine"
        className="lg:col-span-2"
        right={swing.chart_structure && (
          <Pill tone={swing.chart_structure.includes("Downtrend")||swing.chart_structure.includes("Extended") ? "rose" : swing.chart_structure.includes("Choppy") ? "amber" : "signal"}>
            {swing.chart_structure.split("—")[0].trim()}
          </Pill>
        )}>
        <PriceLevelLadder setup={setup} technical={tech} />
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-2">
          <StatItem label="Entry Zone"       value={`${fmtPrice(setup.entry_zone_low)} – ${fmtPrice(setup.entry_zone_high)}`} />
          <StatItem label="Breakout Trigger" value={fmtPrice(setup.breakout_trigger)} valueColor="var(--amber)" />
          <StatItem label="Stop Loss"        value={fmtPrice(setup.stop_loss)}        valueColor="var(--rose)" />
          <StatItem label="Risk : Reward"    value={setup.risk_reward_ratio ? `${setup.risk_reward_ratio} : 1` : "—"} />
          <StatItem label="Target 1 (Conservative)" value={fmtPrice(setup.target1)} valueColor="var(--teal)" />
          <StatItem label="Target 2 (Expected)"     value={fmtPrice(setup.target2)} valueColor="var(--teal)" />
          <StatItem label="Target 3 (Aggressive)"   value={fmtPrice(setup.target3)} valueColor="var(--teal)" />
          <StatItem label="Expected Return"  value={fmtPct(setup.expected_return_pct)} valueColor="var(--teal)" />
        </div>
        {swing.trade_setup_commentary && (
          <p className="text-sm leading-relaxed mt-4 pt-4 border-t" style={{ borderColor: "var(--line)", color: "var(--text-2)" }}>
            {swing.trade_setup_commentary}
          </p>
        )}
      </Card>

      <Card title="Technical Snapshot">
        <div className="grid grid-cols-2 gap-3">
          <StatItem label="Trend"          value={tech.trend} />
          <StatItem label="RSI (14)"       value={tech.rsi14} valueColor={tech.rsi14 > 70 ? "var(--rose)" : tech.rsi14 < 35 ? "var(--amber)" : "var(--teal)"} />
          <StatItem label="52W High"       value={fmtPrice(tech.week52_high)} />
          <StatItem label="52W Low"        value={fmtPrice(tech.week52_low)} />
          <StatItem label="% from 52W High" value={fmtPct(tech.pct_from_52w_high)} valueColor={tech.pct_from_52w_high > -5 ? "var(--amber)" : "var(--teal)"} />
          <StatItem label="Volume Ratio"   value={tech.volume_ratio_10d_vs_50d ? `${tech.volume_ratio_10d_vs_50d}×` : "—"} />
        </div>
        <div className="mt-4 pt-4 border-t" style={{ borderColor: "var(--line)" }}>
          {[["Support", tech.support_levels, "signal"], ["Resistance", tech.resistance_levels, "rose"]].map(([label, levels, tone]) => (
            <div key={label} className="mb-3">
              <div className="text-[10px] uppercase tracking-wider mb-1.5" style={{ color: "var(--text-3)" }}>{label} Levels</div>
              <div className="flex gap-1.5 flex-wrap">
                {(levels||[]).map((l,i) => <Pill key={i} tone={tone}>{fmtPrice(l)}</Pill>)}
                {!(levels||[]).length && <span className="text-sm" style={{ color: "var(--text-3)" }}>—</span>}
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card title="Why This Stock" subtitle="Pattern & indicator signals driving the recommendation">
        <BulletList items={swing.why_recommended} icon="check" emptyText="No specific bullish signals detected at current levels." />
      </Card>
      <Card title="Risks & Caveats" subtitle="Flags and warnings to consider before entering">
        <BulletList items={swing.why_not_or_caveats} icon="warn" emptyText="No significant red flags detected." />
      </Card>
      <Card title="Key Risk Factors">
        <BulletList items={report.risk_factors} icon="risk" emptyText="No specific risks identified." />
      </Card>
    </div>
  );
}

function LongTermTab({ report }) {
  const lt = report.long_term_view || {};
  const aiReady = lt.thesis && !lt.thesis.includes("unavailable");
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
      <Card title="1–3 Year Investment Thesis" className="lg:col-span-2"
        right={<AIBadge available={aiReady} />}>
        {aiReady ? (
          <>
            <p className="text-sm leading-relaxed mb-4" style={{ color: "var(--text-2)" }}>{lt.thesis}</p>
            {lt.valuation_view && (
              <div className="pt-4 border-t" style={{ borderColor: "var(--line)" }}>
                <div className="text-xs uppercase tracking-wider mb-1" style={{ color: "var(--text-3)" }}>Valuation View</div>
                <p className="text-sm leading-relaxed" style={{ color: "var(--text-2)" }}>{lt.valuation_view}</p>
              </div>
            )}
          </>
        ) : (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <Lock size={20} className="mb-2" style={{ color: "var(--text-3)" }} />
            <p className="font-semibold text-sm mb-1" style={{ color: "var(--text-1)" }}>AI Research Not Available</p>
            <p className="text-xs" style={{ color: "var(--text-3)" }}>Connect AI credits to unlock long-term thesis, valuation analysis, and structural growth assessment.</p>
          </div>
        )}
      </Card>
      <Card title="Structural Score">
        <div className="flex flex-col items-center py-2">
          <div className="font-mono text-4xl font-bold" style={{ color: lt.structural_score >= 65 ? "var(--teal)" : lt.structural_score >= 50 ? "var(--gold)" : "var(--rose)" }}>
            {fmtScore(lt.structural_score)}<span className="text-sm" style={{ color: "var(--text-3)" }}>/100</span>
          </div>
          <div className="h-1.5 w-40 rounded-full overflow-hidden mt-3" style={{ background: "var(--surface-3)" }}>
            <div className="h-full rounded-full" style={{
              width: `${Math.max(2, lt.structural_score || 0)}%`,
              background: (lt.structural_score || 0) >= 65 ? "var(--teal)" : (lt.structural_score || 0) >= 50 ? "var(--gold)" : "var(--rose)"
            }} />
          </div>
          <div className="mt-4">
            {lt.suitable_for_long_term === true  && <Pill tone="signal">Suitable for long-term hold</Pill>}
            {lt.suitable_for_long_term === false && <Pill tone="rose">Not ideal for long-term</Pill>}
            {lt.suitable_for_long_term == null  && <Pill tone="neutral">Not yet assessed</Pill>}
          </div>
        </div>
      </Card>
      <Card title="Structural Growth Drivers">
        <BulletList items={lt.growth_drivers} icon="check" emptyText="AI research needed for this section." />
      </Card>
      <Card title="Long-Term Risks" className="lg:col-span-2">
        <BulletList items={lt.long_term_risks} icon="risk" emptyText="AI research needed for this section." />
      </Card>
    </div>
  );
}

function BreakdownTab({ report }) {
  const f = report.fundamental_detail || {};
  const t = report.technical_detail   || {};
  const s = report.sector_detail      || {};
  const m = report.momentum_detail    || {};
  const pd = t.pattern_data || {};

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <Card title="Fundamental Analysis" right={f.rating && <Pill tone={f.rating==="Strong"?"signal":f.rating==="Good"?"blue":f.rating==="Weak"?"rose":"amber"}>{f.rating}</Pill>}>
        {[["Business Quality", f.business_quality_notes], ["Financial Health", f.financial_health_notes], ["Ownership & Holding", f.ownership_notes], ["Valuation", f.valuation_notes]].map(([label, val]) => val && (
          <div key={label} className="mb-3">
            <div className="text-xs font-semibold mb-0.5" style={{ color: "var(--text-3)" }}>{label}</div>
            <p className="text-sm leading-relaxed" style={{ color: "var(--text-2)" }}>{val}</p>
          </div>
        ))}
        {f.red_flags?.length > 0 && (
          <div className="mt-3 pt-3 border-t" style={{ borderColor: "var(--line)" }}>
            <div className="text-xs font-semibold mb-1.5" style={{ color: "var(--rose)" }}>Red Flags</div>
            <BulletList items={f.red_flags} icon="risk" />
          </div>
        )}
      </Card>

      <Card title="Sector & Industry" right={s.sector_trend && <Pill tone={s.sector_trend==="Bullish"?"signal":s.sector_trend==="Bearish"?"rose":"amber"}>{s.sector_trend}</Pill>}>
        <div className="flex items-center gap-2 mb-3">
          <span className="font-display font-semibold text-sm" style={{ color: "var(--text-1)" }}>{s.sector_name || "Unclassified"}</span>
          <span className="font-mono text-xs" style={{ color: "var(--text-3)" }}>Score {fmtScore(s.sector_strength_score)}/100</span>
        </div>
        <p className="text-sm leading-relaxed mb-4" style={{ color: "var(--text-2)" }}>{s.sector_outlook || "AI research needed."}</p>
        <div className="grid grid-cols-2 gap-4">
          <div><div className="text-xs uppercase tracking-wider mb-1.5" style={{ color: "var(--text-3)" }}>Growth Drivers</div><BulletList items={s.growth_drivers} icon="check" /></div>
          <div><div className="text-xs uppercase tracking-wider mb-1.5" style={{ color: "var(--text-3)" }}>Risks</div><BulletList items={s.risks} icon="risk" /></div>
        </div>
      </Card>

      <Card title="Pattern Detection Results">
        <div className="grid grid-cols-3 gap-3 mb-4">
          {[["Structure (T1)", t.tier1_score, 35], ["Candles (T2)", t.tier2_score, 20], ["SMC (T3)", t.tier3_score, 15], ["Indicators (T4)", t.tier4_score, 30], ["Pattern Total", t.pattern_score, 70], ["Final Technical", t.technical_score, 100]].map(([l, v, mx]) => (
            <StatItem key={l} label={l} value={`${v ?? "—"}/${mx}`} valueColor={v >= mx*0.7 ? "var(--teal)" : v >= mx*0.4 ? "var(--gold)" : "var(--rose)"} />
          ))}
        </div>
        {(pd.patterns||[]).filter(p=>p.detected).map((p,i) => (
          <div key={i} className="mb-2 p-3 rounded-xl border" style={{ background: "var(--surface-2)", borderColor: "var(--line)" }}>
            <div className="flex items-center justify-between gap-2 mb-0.5">
              <span className="text-xs font-semibold" style={{ color: "var(--teal)" }}>✓ {p.name}</span>
              <div className="flex items-center gap-2">
                <Pill tone="neutral">{p.confidence}</Pill>
                <span className="text-xs font-mono" style={{ color: "var(--gold)" }}>+{p.score_contribution}pts</span>
              </div>
            </div>
            <p className="text-xs" style={{ color: "var(--text-2)" }}>{p.description}</p>
          </div>
        ))}
        {(pd.patterns||[]).filter(p=>!p.detected).map((p,i) => (
          <div key={i} className="flex items-center justify-between py-1.5 border-b text-xs" style={{ borderColor: "var(--line)" }}>
            <span style={{ color: "var(--text-3)" }}>✗ {p.name}</span>
          </div>
        ))}
        {pd.pattern_narrative && (
          <p className="text-xs mt-3 pt-3 border-t leading-relaxed" style={{ borderColor: "var(--line)", color: "var(--text-2)" }}>{pd.pattern_narrative}</p>
        )}
      </Card>

      <Card title="Momentum & Relative Strength">
        <StatItem label="Momentum Score" value={`${fmtScore(m.momentum_score)}/100`} />
        <div className="mt-4 space-y-3 text-sm" style={{ color: "var(--text-2)" }}>
          {m.relative_strength_assessment && <div><span className="font-semibold" style={{ color: "var(--text-1)" }}>Relative Strength: </span>{m.relative_strength_assessment}</div>}
          {m.accumulation_distribution && <div><span className="font-semibold" style={{ color: "var(--text-1)" }}>Accumulation: </span>{m.accumulation_distribution}</div>}
        </div>
        {t.tier4_breakdown?.length > 0 && (
          <div className="mt-4 pt-4 border-t" style={{ borderColor: "var(--line)" }}>
            <div className="text-xs uppercase tracking-wider mb-2" style={{ color: "var(--text-3)" }}>Indicator Breakdown (Tier 4)</div>
            {t.tier4_breakdown.map((b,i) => (
              <div key={i} className="flex items-center justify-between py-1.5 text-xs border-b" style={{ borderColor: "var(--line)" }}>
                <span style={{ color: "var(--text-2)" }}>{b.signal} — <span style={{ color: "var(--text-3)" }}>{b.reason}</span></span>
                <span className="font-mono font-bold ml-2" style={{ color: b.points >= 0 ? "var(--teal)" : "var(--rose)" }}>{b.points >= 0 ? "+" : ""}{b.points}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}