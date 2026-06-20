import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, RefreshCcw, BarChart2, TrendingUp, Shield, AlertOctagon, ChevronLeft, ChevronRight, Search, X } from "lucide-react";
import { analyzeStock, getDashboard, listStocks, refreshMarketOverview } from "../lib/api";
import { useJob } from "../lib/JobContext";
import MarketOverviewCard from "../components/MarketOverviewCard";
import VerdictDistribution from "../components/VerdictDistribution";
import SectorStrengthChart from "../components/SectorStrengthChart";
import TopPickCard from "../components/TopPickCard";
import FilterBar from "../components/FilterBar";
import StockTable from "../components/StockTable";
import SelectionBar from "../components/SelectionBar";
import { SectionLabel } from "../components/ui";
import { fmtNum } from "../lib/format";

const PAGE_SIZE = 50;

function StatCard({ label, value, sub, icon: Icon, color }) {
  return (
    <div className="rounded-2xl border p-4 flex items-center gap-4"
      style={{ background: "var(--surface)", borderColor: "var(--line)", boxShadow: "var(--shadow-sm)" }}>
      <div className="h-11 w-11 rounded-xl flex items-center justify-center shrink-0"
        style={{ background: `${color}18`, border: `1px solid ${color}30` }}>
        <Icon size={20} style={{ color }} />
      </div>
      <div>
        <div className="font-mono text-2xl font-bold" style={{ color: "var(--text-1)" }}>{value}</div>
        <div className="text-xs" style={{ color: "var(--text-3)" }}>{label}</div>
        {sub && <div className="text-xs font-medium mt-0.5" style={{ color }}>{sub}</div>}
      </div>
    </div>
  );
}

function Pagination({ page, totalPages, totalItems, onPage }) {
  if (totalPages <= 1) return null;
  const pages = [];
  const start = Math.max(1, page - 2);
  const end   = Math.min(totalPages, page + 2);
  for (let i = start; i <= end; i++) pages.push(i);

  return (
    <div className="flex items-center justify-between mt-3">
      <span className="text-xs" style={{ color: "var(--text-3)" }}>
        {fmtNum(totalItems)} stocks · Page {page} of {totalPages}
      </span>
      <div className="flex items-center gap-1">
        <button onClick={() => onPage(page - 1)} disabled={page === 1}
          className="h-8 w-8 flex items-center justify-center rounded-lg border transition-all disabled:opacity-30"
          style={{ borderColor: "var(--line)", color: "var(--text-2)" }}>
          <ChevronLeft size={14} />
        </button>
        {start > 1 && <>
          <button onClick={() => onPage(1)} className="h-8 w-8 flex items-center justify-center rounded-lg border text-xs transition-all"
            style={{ borderColor: "var(--line)", color: "var(--text-2)" }}>1</button>
          {start > 2 && <span className="px-1 text-xs" style={{ color: "var(--text-3)" }}>…</span>}
        </>}
        {pages.map(p => (
          <button key={p} onClick={() => onPage(p)}
            className="h-8 w-8 flex items-center justify-center rounded-lg border text-xs font-medium transition-all"
            style={{ borderColor: p === page ? "var(--gold)" : "var(--line)", color: p === page ? "var(--gold)" : "var(--text-2)", background: p === page ? "var(--gold-dim)" : "transparent" }}>
            {p}
          </button>
        ))}
        {end < totalPages && <>
          {end < totalPages - 1 && <span className="px-1 text-xs" style={{ color: "var(--text-3)" }}>…</span>}
          <button onClick={() => onPage(totalPages)} className="h-8 w-8 flex items-center justify-center rounded-lg border text-xs transition-all"
            style={{ borderColor: "var(--line)", color: "var(--text-2)" }}>{totalPages}</button>
        </>}
        <button onClick={() => onPage(page + 1)} disabled={page === totalPages}
          className="h-8 w-8 flex items-center justify-center rounded-lg border transition-all disabled:opacity-30"
          style={{ borderColor: "var(--line)", color: "var(--text-2)" }}>
          <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [dashboard, setDashboard]   = useState(null);
  const [allStocks, setAllStocks]   = useState([]);   // full unfiltered list for pagination
  const [totalCount, setTotalCount] = useState(0);
  const [loadingStocks, setLS]      = useState(true);
  const [refreshingOv, setROv]      = useState(false);
  const [analyzingSet, setAS]       = useState(new Set());
  const [selected, setSel]          = useState(new Set());

  // Filters
  const [verdict, setVerdict]   = useState(null);
  const [exchange, setExchange] = useState(null);
  const [sector, setSector]     = useState(null);
  const [industry, setIndustry] = useState(null);
  const [category, setCategory] = useState(null);

  // Search (global — hits backend, ignores pagination filter)
  const [searchQ, setSearchQ]       = useState("");
  const [searchResults, setSearchR] = useState(null);  // null = not in search mode
  const [searchLoading, setSL]      = useState(false);
  const searchRef                    = useRef(null);

  // Pagination
  const [page, setPage] = useState(1);

  const { job, isRunning, startBatchJob } = useJob();

  // ── Load paginated stock list ──────────────────────────────────────
  const loadStocks = useCallback(async (pg = 1) => {
    setLS(true);
    try {
      const d = await listStocks({
        verdict:  verdict  || undefined,
        exchange: exchange || undefined,
        sector:   sector   || undefined,
        industry: industry || undefined,
        category: category ? (category === "ALL" ? "ALL" : category) : undefined,
        limit:  PAGE_SIZE,
        offset: (pg - 1) * PAGE_SIZE,
      });
      setAllStocks(d.items || []);
      setTotalCount(d.total || 0);
    } finally { setLS(false); }
  }, [verdict, exchange, sector, industry, category]);

  const loadDashboard = useCallback(async () => {
    const d = await getDashboard(6);
    setDashboard(d);
  }, []);

  useEffect(() => { loadDashboard(); }, [loadDashboard]);
  useEffect(() => { setPage(1); loadStocks(1); }, [loadStocks]);

  const prevStatus = useMemo(() => job?.status, [job?.status]);
  useEffect(() => {
    if (prevStatus === "completed") { loadStocks(page); loadDashboard(); }
  }, [prevStatus]);

  // ── Global search ──────────────────────────────────────────────────
  useEffect(() => {
    if (!searchQ.trim()) { setSearchR(null); return; }
    setSL(true);
    const t = setTimeout(async () => {
      try {
        const d = await listStocks({ q: searchQ, limit: 200 });
        setSearchR(d.items || []);
      } finally { setSL(false); }
    }, 300);
    return () => clearTimeout(t);
  }, [searchQ]);

  const clearSearch = () => { setSearchQ(""); setSearchR(null); };

  // Displayed stocks: search results OR paginated list
  const displayStocks = searchResults !== null ? searchResults : allStocks;
  const totalPages    = Math.ceil(totalCount / PAGE_SIZE);

  const onPageChange = (pg) => {
    setPage(pg);
    loadStocks(pg);
    document.getElementById("stock-universe")?.scrollIntoView({ behavior: "smooth" });
  };

  // ── Analyse handlers ───────────────────────────────────────────────
  const onAnalyzeOne = async code => {
    setAS(prev => new Set(prev).add(code));
    try { await analyzeStock(code); await Promise.all([loadStocks(page), loadDashboard()]); }
    catch (e) { alert(`Analysis failed for ${code}: ${e?.response?.data?.detail || e.message}`); }
    finally { setAS(prev => { const n = new Set(prev); n.delete(code); return n; }); }
  };

  const onToggle    = code => setSel(prev => { const n = new Set(prev); n.has(code) ? n.delete(code) : n.add(code); return n; });
  const onToggleAll = checked => setSel(checked ? new Set(displayStocks.map(s => s.symbol_code)) : new Set());

  const counts = dashboard?.verdict_counts || {};
  const total  = dashboard?.total_stocks  || 0;

  return (
    <div className="flex flex-col gap-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold" style={{ color: "var(--text-1)" }}>
            Stock Intelligence Dashboard
          </h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-3)" }}>
            {dashboard ? `${dashboard.analyzed_stocks} of ${total} stocks analysed · insights.vtrader.in` : "Loading…"}
          </p>
        </div>
        <Link to="/report" className="flex items-center gap-1.5 text-sm font-medium"
          style={{ color: "var(--gold)" }}>
          Research Report <ArrowUpRight size={15} />
        </Link>
      </div>

      {/* Stat row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard label="Total Universe"   value={fmtNum(total)}                                          sub={`${dashboard?.analyzed_stocks || 0} analysed`} icon={BarChart2}     color="var(--blue)"  />
        <StatCard label="Buy Signals"      value={(counts["Strong Buy"]||0)+(counts["Buy"]||0)}           sub="High conviction picks"                          icon={TrendingUp}   color="var(--teal)"  />
        <StatCard label="On Watchlist"     value={counts["Watchlist"]||0}                                 sub="Monitor closely"                                icon={Shield}       color="var(--amber)" />
        <StatCard label="Avoid"            value={counts["Avoid"]||0}                                     sub="Skip for now"                                   icon={AlertOctagon} color="var(--rose)"  />
      </div>

      {/* AI Market Intelligence */}
      <MarketOverviewCard
        overview={dashboard?.market_overview}
        onRefresh={async () => { setROv(true); try { await refreshMarketOverview(); await loadDashboard(); } finally { setROv(false); } }}
        refreshing={refreshingOv}
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <VerdictDistribution counts={counts} total={total} />
        <SectorStrengthChart data={dashboard?.sector_strength || []} />
      </div>

      {/* Top Picks */}
      <div>
        <SectionLabel action={isRunning && <span className="text-xs animate-pulse" style={{ color: "var(--amber)" }}>Scanning in progress…</span>}>
          Top Conviction Picks
        </SectionLabel>
        {dashboard?.top_picks?.length ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {dashboard.top_picks.map((r, i) => <TopPickCard key={r.id} report={r} rank={i + 1} />)}
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed p-12 text-center"
            style={{ borderColor: "var(--line)", background: "var(--surface)" }}>
            <div className="text-4xl mb-3">📊</div>
            <p className="font-display font-semibold text-sm mb-1" style={{ color: "var(--text-1)" }}>No analysis yet</p>
            <p className="text-xs" style={{ color: "var(--text-3)" }}>
              Click <span style={{ color: "var(--gold)" }}>Run Full Scan</span> in the header, or analyse individual stocks below.
            </p>
          </div>
        )}
      </div>

      {/* Stock Universe */}
      <div id="stock-universe" className="flex flex-col gap-3">
        <SectionLabel action={
          <div className="flex items-center gap-2 flex-wrap">
            <FilterBar
              verdict={verdict}   setVerdict={setVerdict}
              exchange={exchange} setExchange={setExchange}
              sector={sector}     setSector={setSector}
              industry={industry} setIndustry={setIndustry}
              category={category} setCategory={setCategory}
            />
            <button onClick={() => loadStocks(page)}
              className="flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-medium transition-all"
              style={{ borderColor: "var(--line)", color: "var(--text-2)" }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--gold)"; e.currentTarget.style.color = "var(--gold)"; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--line)"; e.currentTarget.style.color = "var(--text-2)"; }}>
              <RefreshCcw size={12} className={loadingStocks ? "animate-spin" : ""} /> Refresh
            </button>
          </div>
        }>
          Stock Universe
        </SectionLabel>

        {/* Global search bar */}
        <div className="flex items-center gap-2 rounded-xl border px-3 py-2.5"
          style={{ background: "var(--surface)", borderColor: "var(--line)" }}>
          <Search size={15} style={{ color: "var(--text-3)" }} className="shrink-0" />
          <input
            ref={searchRef}
            value={searchQ}
            onChange={e => setSearchQ(e.target.value)}
            placeholder="Search across all stocks by name, symbol, sector or industry…"
            className="flex-1 bg-transparent text-sm outline-none"
            style={{ color: "var(--text-1)" }}
          />
          {searchLoading && <span className="text-xs" style={{ color: "var(--text-3)" }}>Searching…</span>}
          {searchQ && !searchLoading && (
            <button onClick={clearSearch} style={{ color: "var(--text-3)" }}>
              <X size={14} />
            </button>
          )}
          {searchResults !== null && (
            <span className="text-xs font-mono px-2 py-0.5 rounded-full"
              style={{ background: "var(--gold-dim)", color: "var(--gold)" }}>
              {searchResults.length} results
            </span>
          )}
        </div>

        {searchResults !== null && (
          <p className="text-xs" style={{ color: "var(--text-3)" }}>
            Showing global search results for "<span style={{ color: "var(--text-1)" }}>{searchQ}</span>" — filters above not applied during search.
            <button onClick={clearSearch} className="ml-2 underline" style={{ color: "var(--gold)" }}>Clear search</button>
          </p>
        )}

        <StockTable
          items={displayStocks}
          selected={selected}
          onToggleSelect={onToggle}
          onToggleSelectAll={onToggleAll}
          onAnalyzeOne={onAnalyzeOne}
          analyzingSet={analyzingSet}
        />

        {/* Pagination — only when not searching */}
        {searchResults === null && (
          <Pagination
            page={page}
            totalPages={totalPages}
            totalItems={totalCount}
            onPage={onPageChange}
          />
        )}
      </div>

      <SelectionBar
        count={selected.size}
        onClear={() => setSel(new Set())}
        onAnalyze={async () => { await startBatchJob([...selected]); setSel(new Set()); }}
        isRunning={isRunning}
      />
    </div>
  );
}